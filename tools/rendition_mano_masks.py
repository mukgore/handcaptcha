"""Verify private H264 renditions of every analytically accepted MANO pilot."""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.rendition import build_h264_rendition
from dataset_pipeline.storage import private_output


def run(pilots,masks,output,*,ffmpeg,ffprobe):
    pilots=Path(pilots).resolve(strict=True);masks=Path(masks).resolve(strict=True)
    output=private_output(output);output.mkdir(parents=True,exist_ok=False);rows=[]
    summary=json.loads((masks/'summary.json').read_text(encoding='utf8'))
    for case in summary['cases']:
        if not case['accepted']:continue
        name=case['case']
        if not isinstance(name,str) or not re.fullmatch(r'(?:left|right)_pc[0-5]',name):raise ValueError('Known bounded pilot case required')
        report=json.loads((masks/name/'mask_report.json').read_text(encoding='utf8'))
        if not re.fullmatch('[a-f0-9]{64}',report['artifact']['artifact_id']):raise ValueError('Invalid artifact identifier')
        reference=json.loads((pilots/name/'supervised/worker_journal/private_reference.json').read_text(encoding='utf8'))
        parent=masks/name/'candidates'/report['artifact']['artifact_id']
        rendition=build_h264_rendition(parent,reference['frames'],reference['source_info'],report['w3'],PipelineConfig(),output/name,
                                        ffmpeg=ffmpeg,ffprobe=ffprobe,outside_mae_limit=2.0)
        rows.append({'case':name,'state':rendition['state'],'frames':rendition['raster_inspection']['decoded_frames'],
                     'max_outside_mae':rendition['raster_inspection']['max_frame_outside_mae'],
                     'container_passed':rendition['container_inspection']['passed'],'release_allowed':False})
    result={'schema_version':1,'source_cases':len(summary['cases']),'accepted_for_rendition':summary['accepted_cases'],
            'verified_renditions':len(rows),'cases':rows,'release_allowed':False,
            'scope':'private_model_derived_codec_mask_QA_not_human_or_operating_approval'}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pilots','masks','output','ffmpeg','ffprobe'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();run(args.pilots,args.masks,args.output,ffmpeg=args.ffmpeg,ffprobe=args.ffprobe)
