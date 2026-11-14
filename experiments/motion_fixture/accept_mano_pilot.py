"""Bind a private CPU MANO pilot to the existing research mask renderer."""
import argparse
import json
import math
from pathlib import Path

from dataset_pipeline.release_registry import digest
from dataset_pipeline.storage import private_output

PILOT_INPUTS=(('authored_source.avi','source_video_sha256'),('private_reference.json','reference_sha256'),('private_surface.npz','surface_sha256'))


def build_candidate(*args,**kwargs):
    from dataset_pipeline.candidate import build_candidate as implementation
    return implementation(*args,**kwargs)


def gate_clip(*args,**kwargs):
    from dataset_pipeline.stage7_gate import gate_clip as implementation
    return implementation(*args,**kwargs)


def verify_pilot(pilot,report,binding):
    pilot=Path(pilot)
    if digest(pilot/'mano_report.json')!=binding or any(digest(pilot/name)!=report[key] for name,key in PILOT_INPUTS):
        raise ValueError('Pilot changed during analysis or mask build')


def load_bound_pilot(pilot):
    pilot=Path(pilot).resolve(strict=True);report_path=pilot/'mano_report.json';binding=digest(report_path)
    report=json.loads(report_path.read_text(encoding='utf8'))
    if report.get('state')!='RESEARCH_MANO_PCA_PILOT' or report.get('release_allowed') is not False:
        raise ValueError('Explicit private research MANO pilot required')
    verify_pilot(pilot,report,binding)
    reference=json.loads((pilot/'private_reference.json').read_text(encoding='utf8'))
    frames,info=reference['frames'],reference['source_info']
    if (type(report.get('frames')) is not int or type(info.get('total_frames')) is not int or
            not frames or len(frames)!=report['frames'] or info['total_frames']!=len(frames)):
        raise ValueError('Full rendered frame denominator required')
    return report,reference,binding


def run(pilot, output, *, w3, feasibility_proposal=False):
    # Reading/hash-checking saved pilots must also work in the CPU model
    # runtime, which does not install camera extraction/MediaPipe packages.
    from dataset_pipeline.config import PipelineConfig
    if isinstance(w3,bool) or not isinstance(w3,(int,float)) or not math.isfinite(w3) or w3<=0:
        raise ValueError('Explicit finite positive mask multiplier required')
    if type(feasibility_proposal) is not bool:raise ValueError('Explicit boolean proposal origin required')
    pilot=Path(pilot).resolve(strict=True);output=private_output(output)
    report,reference,binding=load_bound_pilot(pilot)
    frames,info=reference['frames'],reference['source_info'];config=PipelineConfig()
    gate=gate_clip(frames,w3,config);output.mkdir(parents=True,exist_ok=False)
    result={'schema_version':1,'state':'QUARANTINED_GEOMETRY','release_allowed':False,
            'origin_type':'licensed_mano_authored_pca_pilot','pilot_report_sha256':binding,
            'hand':report['hand'],'component':report['component'],'frames':len(frames),
            'gate_pass_frac':gate['pass_frac'],'gate_accepted':gate['accepted'],'w3':w3,'artifact':None,
            'gate_diagnostics':gate['frame_diagnostics'],
            'mask_parameter_origin':'source_specific_analytic_generator_constraint' if feasibility_proposal else 'explicit_engineering_input',
            'limitations':['not observed human motion or Text2HOI output','not anatomical/contact/human/attack approval',
                           'Stage7/Stage6 research rendering, not full Stage1-5 statistical acceptance']}
    if gate['accepted']:
        result['artifact']=build_candidate(pilot/'authored_source.avi',frames,info,w3,config,output/'candidates')
        result['state']='RESEARCH_MASKED_MANO_PILOT'
    verify_pilot(pilot,report,binding)
    with (output/'mask_report.json').open('x',encoding='utf8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot',required=True);parser.add_argument('--output',required=True);parser.add_argument('--w3',type=float,required=True)
    args=parser.parse_args();result=run(args.pilot,args.output,w3=args.w3)
    print(json.dumps({key:result[key] for key in ('state','frames','gate_accepted','gate_pass_frac','release_allowed')}))
