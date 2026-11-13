"""Build private two/three-tip contact fixtures and depth-reflection controls.

Fixed-object control assumes oracle 3D object pose. Joint reflection explicitly
shows ambiguity when that depth is not supplied. No human/AI efficacy claim.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from dataset_pipeline.candidate import build_candidate
from dataset_pipeline.common import LANDMARK_NAMES
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.rendition import build_h264_rendition
from dataset_pipeline.stage6_occlusion import project_occlusion_circle
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.storage import private_output
from .generate import draw_frame,WIDTH,HEIGHT
from .grasp_contacts import KINDS,VERSION,records,reflect_depth,inspect
from .mask_feasibility import inspect as feasible_mask


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_video(path,frames,fps):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'FFV1'),fps,(WIDTH,HEIGHT))
    try:
        if not writer.isOpened():raise ValueError('Fixture encoder unavailable')
        for frame in frames:writer.write(draw_frame(frame))
    finally:writer.release()
    cap=cv2.VideoCapture(str(path));count=0
    try:
        for frame in frames:
            ok,image=cap.read()
            if not ok or not np.array_equal(image,draw_frame(frame)):raise ValueError('Source raster changed')
            pts=float(cap.get(cv2.CAP_PROP_POS_MSEC))
            if abs(pts-frame['source_pts_ms'])>.01:raise ValueError('Source PTS mismatch')
            frame['source_pts_ms']=pts;count+=1
        if cap.read()[0]:raise ValueError('Unexpected source frame')
    finally:cap.release()
    return count


def masked_image(frame,w3):
    image=draw_frame(frame);center,radius=project_occlusion_circle(frame_points(frame,'px'),w3)
    cv2.circle(image,(int(center[0]),int(center[1])),int(radius),(0,0,0),-1)
    return image


def equal_video(a,b,expected):
    caps=[cv2.VideoCapture(str(path)) for path in (a,b)]
    try:
        for _ in range(expected):
            left,image_a=caps[0].read();right,image_b=caps[1].read()
            if not left or not right or not np.array_equal(image_a,image_b):raise ValueError('Projected pair bytes differ after decoding')
        if any(cap.read()[0] for cap in caps):raise ValueError('Unexpected paired frame')
    finally:
        for cap in caps:cap.release()


def build(output,*,seeds=(7,19),frames=24,fps=12,ffmpeg,ffprobe):
    if not isinstance(seeds,(list,tuple)) or not 1<=len(seeds)<=8 or len(set(seeds))!=len(seeds):
        raise ValueError('One to eight explicit distinct recipe seeds required')
    recipes=[(kind,seed,records(kind,seed,frames,fps)) for seed in seeds for kind in KINDS]
    flattened=[{**frame,'frame_idx':i} for i,frame in enumerate(frame for _,_,sequence in recipes for frame in sequence)]
    config=PipelineConfig();interval=feasible_mask(flattened,config)
    if not interval['feasible']:raise ValueError('No shared all-frame mask; gate will not be weakened')
    w3=interval['proposed_w3'];root=private_output(output);root.mkdir(parents=True,exist_ok=False)
    cases=[];projection_checks=masked_checks=encoded_checks=decoded=0;worst=0.
    info={'width':WIDTH,'height':HEIGHT,'fps':fps,'total_frames':frames}
    for kind,seed,original in recipes:
        sequences={'source':original,'hand_reflection':reflect_depth(original,object_too=False),
                   'joint_reflection':reflect_depth(original,object_too=True)}
        group=root/(kind+'_s'+str(seed));group.mkdir();renders={}
        for name,sequence in sequences.items():
            report=inspect(sequence);expected=name!='hand_reflection'
            if report['accepted']!=expected:raise ValueError('Authored contact control violated its declared geometry')
            geometry=gate_clip(sequence,w3,config)
            if not geometry['accepted']:raise ValueError('Projected mask gate failed')
            if name!='source':
                for a,b in zip(original,sequence):
                    if not np.array_equal(draw_frame(a),draw_frame(b)):raise ValueError('Visible scene differs')
                    if not np.array_equal(masked_image(a,w3),masked_image(b,w3)):raise ValueError('Masked scene differs')
                    projection_checks+=1;masked_checks+=1
            out=group/name;out.mkdir();source=out/'source.private.avi'
            decoded+=source_video(source,sequence,fps)
            reference=out/'reference.private.json'
            reference.write_text(json.dumps({'frames':sequence,'source_info':info},allow_nan=False),encoding='utf8')
            source_hash,reference_hash=digest(source),digest(reference)
            row={'kind':kind,'seed':seed,'control':name,'proxy':report,'geometry_gate':geometry,
                 'state':'QUARANTINED_CONTACT_CONTROL','artifact':None,'rendition':None,
                 'source_sha256':source_hash,'reference_sha256':reference_hash,'release_allowed':False}
            if report['accepted']:
                row['artifact']=build_candidate(source,sequence,info,w3,config,out/'candidates')
                parent=out/'candidates'/row['artifact']['artifact_id']
                row['rendition']=build_h264_rendition(parent,sequence,info,w3,config,out/'renditions',
                    ffmpeg=str(ffmpeg),ffprobe=str(ffprobe),outside_mae_limit=2.)
                row['state']='RESEARCH_CONTACT_PROXY_ONLY'
                renders[name]=out/'renditions'/row['rendition']['output_sha256']/'video.mp4'
                worst=max(worst,row['rendition']['raster_inspection']['max_frame_outside_mae'])
            if digest(source)!=source_hash or digest(reference)!=reference_hash:raise ValueError('Generated input changed during processing')
            (out/'report.private.json').write_text(json.dumps(row,indent=2,allow_nan=False),encoding='utf8');cases.append(row)
        equal_video(renders['source'],renders['joint_reflection'],frames);encoded_checks+=frames
    summary={'scope':'authored_contact_proxy_and_orthographic_depth_controls_not_efficacy',
        'generator_version':VERSION,'contact_topologies_n':len(KINDS),'recipe_instances_n':len(recipes),
        'control_cases_n':len(cases),'source_frames_decoded_n':decoded,
        'contact_proxy_accepted_cases_n':sum(r['proxy']['accepted'] for r in cases),
        'quarantined_contact_controls_n':sum(r['artifact'] is None for r in cases),
        'h264_renditions_n':sum(r['rendition'] is not None for r in cases),
        'h264_frames_verified_n':sum(r['rendition']['raster_inspection']['decoded_frames'] for r in cases if r['rendition']),
        'identical_projected_pair_frames_n':projection_checks,'identical_masked_pair_frames_n':masked_checks,
        'identical_encoded_valid_pair_frames_n':encoded_checks,'maximum_visible_region_codec_mae':worst,
        'fixed_object_depth_control':'hand-only reflection fails contact when true 3D object pose is supplied',
        'unknown_object_depth_control':'reflecting hand and object preserves contact and every rendered pixel',
        'same_pixel_human_or_ai_identifiability_proven':False,'force_closure_proven':False,
        'anatomical_or_human_feasibility_verified':False,'new_model_inference':False,'release_allowed':False,
        'limitations':['authored capsule graph, not anatomical mesh or stable grasp physics',
            'first control uses oracle object depth not available from an ordinary 2D image',
            'orthographic equal-pixel controls require multiple permitted 3D explanations',
            'not a human/AI study, independent source count, entropy estimate or operating CAPTCHA']}
    (root/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','ffmpeg','ffprobe'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.output,ffmpeg=args.ffmpeg,ffprobe=args.ffprobe)))
