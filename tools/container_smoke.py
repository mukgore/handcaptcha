"""Generate synthetic codec/timeline/extra-track cases and inspect with ffprobe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset_pipeline.container_inspection import inspect_container
from dataset_pipeline.storage import private_output


def run(output, ffmpeg, ffprobe):
    root=private_output(output);root.mkdir(parents=True,exist_ok=False)
    cases=[('cfr_mpeg4',12,'mpeg4',[],True),
           ('fractional_h264',30000/1001,'libx264',['-bf','0'],True),
           ('bframe_h264',12,'libx264',['-bf','3'],True),
           ('extra_audio',12,'libx264',['-bf','0'],False),
           ('unreviewed_tag',12,'libx264',['-bf','0','-metadata','comment=synthetic_test_only'],False),
           ('vfr_gap',12,'libx264',['-bf','0','-vf','setpts=PTS+0.1/TB*gte(N\\,6)','-fps_mode','vfr'],False)]
    rows=[]
    for name,fps,codec,extra,expected_pass in cases:
        video=root/(name+'.mp4');rate='30000/1001' if name=='fractional_h264' else str(fps)
        command=[str(ffmpeg),'-nostdin','-n','-v','error','-f','lavfi','-i',f'testsrc2=size=64x64:rate={rate}']
        if name=='extra_audio':command+=['-f','lavfi','-i','sine=frequency=440:sample_rate=8000','-c:a','aac','-shortest']
        command+=['-frames:v','12','-c:v',codec,'-threads','1','-pix_fmt','yuv420p','-map_metadata','-1',*extra,str(video)]
        with (root/(name+'_encoder.log')).open('xb') as log:
            subprocess.run(command,stdout=subprocess.DEVNULL,stderr=log,check=True,timeout=30)
        report=inspect_container(video,dict(frame_count=12,width=64,height=64,fps=fps),root/(name+'_probe'),ffprobe=ffprobe)
        rows.append({'case':name,'expected_pass':expected_pass,'passed':report['passed'],
                     'reasons':report['reasons'],'matches_expected':report['passed']==expected_pass})
    summary={'schema_version':1,'scope':'synthetic_container_cases_not_anatomical_or_release_validation',
             'cases':rows,'all_match':all(row['matches_expected'] for row in rows),'release_allowed':False}
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary));return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','ffmpeg','ffprobe'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();sys.exit(0 if run(args.output,args.ffmpeg,args.ffprobe)['all_match'] else 1)
