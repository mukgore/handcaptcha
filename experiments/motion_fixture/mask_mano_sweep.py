"""Evaluate every completed MANO pilot with analytic generator-only radii."""
import argparse
import json
import re
from pathlib import Path

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.storage import private_output
from .mask_feasibility import inspect
from .accept_mano_pilot import run as mask_pilot


def run(source,output):
    source=Path(source).resolve(strict=True);output=private_output(output);output.mkdir(parents=True,exist_ok=False)
    original=json.loads((source/'sweep_report.json').read_text(encoding='utf8'));rows=[]
    for case in original['cases']:
        name=case['case']
        if not isinstance(name,str) or not re.fullmatch(r'(?:left|right)_pc[0-5]',name):raise ValueError('Known bounded pilot case required')
        pilot=source/name/'supervised'/'worker_journal'
        if not case['completed']:
            rows.append({'case':name,'state':'SOURCE_FAILED','accepted':False});continue
        frames=json.loads((pilot/'private_reference.json').read_text(encoding='utf8'))['frames']
        feasible=inspect(frames,PipelineConfig())
        report_path=output/(name+'_feasibility.json');report_path.write_text(json.dumps(feasible,indent=2)+'\n',encoding='utf8')
        row={'case':name,'feasible':feasible['feasible'],'minimum_w3':feasible['minimum_w3'],
             'maximum_w3':feasible['maximum_w3'],'proposed_w3':feasible['proposed_w3'],'accepted':False}
        if feasible['feasible']:
            actual=mask_pilot(pilot,output/name,w3=feasible['proposed_w3'],feasibility_proposal=True)
            row.update(state=actual['state'],accepted=actual['artifact'] is not None,gate_pass_frac=actual['gate_pass_frac'])
        else:row['state']='QUARANTINED_NO_ALL_FRAME_RADIUS'
        rows.append(row)
    report={'schema_version':1,'scope':'analytic_source_constraints_not_dataset_calibration',
            'planned_cases':len(original['cases']),'cases':rows,'accepted_cases':sum(row['accepted'] for row in rows),
            'release_allowed':False,'limitations':['post-generation engineering feasibility, not a held-out efficacy study',
                                                  'narrow intervals do not establish tracking or human robustness',
                                                  'previous fixed-weight rejects are preserved']}
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.source,args.output)
