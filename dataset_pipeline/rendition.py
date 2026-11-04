"""Create and independently verify an H.264 rendition of masked pixels only."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

import cv2
import numpy as np

from dataset_pipeline.container_inspection import inspect_container
from dataset_pipeline.release_registry import digest
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.stage6_occlusion import project_occlusion_circle
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.storage import private_output
from dataset_pipeline.timeline import build_frame_map


def validate_raster_pair(source, encoded, masks, width, height, *, outside_mae_limit):
    if isinstance(outside_mae_limit,bool) or not isinstance(outside_mae_limit,(int,float)) or not math.isfinite(outside_mae_limit) or outside_mae_limit<0:
        raise ValueError('Explicit finite nonnegative codec comparison tolerance required')
    before,after=cv2.VideoCapture(str(source)),cv2.VideoCapture(str(encoded))
    worst=0.;count=0
    try:
        if not before.isOpened() or not after.isOpened():raise ValueError('Rendition pair cannot be decoded')
        while True:
            ok_a,a=before.read();ok_b,b=after.read()
            if not ok_a and not ok_b:break
            if not ok_a or not ok_b or count>=len(masks):raise ValueError('Rendition decode counts differ')
            if a.shape[:2]!=(height,width) or b.shape!=a.shape:raise ValueError('Rendition dimensions differ')
            center,radius=masks[count];cx,cy=int(center[0]),int(center[1]);r=int(radius)
            if not 0<=cx<width or not 0<=cy<height or r<1:raise ValueError('Invalid mask raster geometry')
            yy,xx=np.ogrid[:height,:width];distance=(xx-cx)**2+(yy-cy)**2
            interior=distance<=max(0,r-2)**2;outside=distance>=(r+2)**2
            if not interior.any() or not outside.any():raise ValueError('Insufficient mask/visible area for verification')
            if (a[interior]>30).any() or (b[interior]>30).any():raise ValueError('Rendition mask interior differs')
            error=float(np.mean(np.abs(a[outside].astype(np.float32)-b[outside].astype(np.float32))))
            if error>outside_mae_limit:raise ValueError('Visible pixels exceed explicit codec error tolerance')
            worst=max(worst,error);count+=1
        if count!=len(masks):raise ValueError('Missing rendition frames')
    finally:
        before.release();after.release()
    return {'decoded_frames':count,'max_frame_outside_mae':worst,'outside_mae_limit':outside_mae_limit,
            'mask_interior_tolerance':30,'boundary_margin_pixels':2}


def build_h264_rendition(candidate_dir, reference_frames, source_info, w3_new, config, output_root,
                         *, ffmpeg, ffprobe, outside_mae_limit, timeout_seconds=120):
    parent=Path(candidate_dir).resolve(strict=True)
    manifest=json.loads((parent/'artifact.json').read_text(encoding='utf8'))
    if manifest.get('state')!='RESEARCH_CANDIDATE' or manifest.get('release_allowed') is not False:
        raise ValueError('Explicit research candidate manifest required')
    if manifest.get('media_file')!='masked.mp4':raise ValueError('Unexpected candidate media path')
    source=parent/'masked.mp4';parent_hash=manifest['output_sha256']
    if digest(source)!=parent_hash:raise ValueError('Candidate bytes do not match manifest')
    if manifest.get('timeline')!=build_frame_map(reference_frames,source_info) or manifest.get('w3_new')!=w3_new or manifest.get('config')!=config.to_dict():
        raise ValueError('Reference timeline/config differs from candidate')
    if not gate_clip(reference_frames,w3_new,config)['accepted']:raise ValueError('Reference geometry gate rejected')
    width,height=source_info['width'],source_info['height']
    if any(type(x) is not int or x<=0 or x%2 for x in (width,height)) or width*height*3>64*1024*1024:
        raise ValueError('Bounded positive even H.264 dimensions required')
    masks=[]
    for frame in reference_frames:
        points=frame_points(frame,'px')
        if points is None or any(not 0<=p[0]<width or not 0<=p[1]<height for p in points):
            raise ValueError('Visible landmark coordinates leave the video viewport')
        masks.append(project_occlusion_circle(points,w3_new))
    expected={'frame_count':len(reference_frames),'width':width,'height':height,'fps':source_info['fps']}
    root=private_output(output_root);root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.rendition_',dir=root) as temporary:
        temporary=Path(temporary);encoded=temporary/'video.mp4'
        source_check=inspect_container(source,expected,temporary/'source_probe',ffprobe=ffprobe)
        if not source_check['passed']:raise ValueError('Parent container verification failed')
        command=[str(ffmpeg),'-nostdin','-n','-v','error','-i',str(source),'-map','0:v:0','-an','-sn','-dn',
                 '-map_metadata','-1','-c:v','libx264','-pix_fmt','yuv420p','-preset','medium','-crf','18',
                 '-bf','0','-threads','1','-fps_mode','passthrough','-movflags','+faststart',str(encoded)]
        with (temporary/'encoder_stderr.txt').open('xb') as errors:
            result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=errors,timeout=timeout_seconds)
        if result.returncode or not encoded.is_file() or not encoded.stat().st_size:raise ValueError('H.264 encoding failed')
        container=inspect_container(encoded,expected,temporary/'output_probe',ffprobe=ffprobe)
        if not container['passed'] or container['codec']!='h264':raise ValueError('Encoded container verification failed')
        raster=validate_raster_pair(source,encoded,masks,width,height,outside_mae_limit=outside_mae_limit)
        if digest(source)!=parent_hash:raise ValueError('Parent changed during rendition build')
        artifact=digest(encoded)
        report={'schema_version':1,'state':'RESEARCH_RENDITION','release_allowed':False,
                'parent_artifact_id':parent_hash,'output_sha256':artifact,'media_file':'video.mp4',
                'encoder':'libx264','settings':{'crf':18,'pixel_format':'yuv420p','b_frames':0,'threads':1},
                'container_inspection':container,'raster_inspection':raster,
                'limitations':['codec tolerance is an explicit engineering QA setting',
                               'single primary file, no poster or other rendition approval',
                               'no rights, anatomical, human or security release approval']}
        report_path=temporary/'rendition.json';report_path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')
        target=root/artifact;target.mkdir()
        created=[]
        try:
            os.link(encoded,target/'video.mp4');created.append(target/'video.mp4')
            os.link(report_path,target/'rendition.json');created.append(target/'rendition.json')
        except BaseException:
            for path in reversed(created):path.unlink()
            try:target.rmdir()
            except OSError:pass
            raise
    return report
