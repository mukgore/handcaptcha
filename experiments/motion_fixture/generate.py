"""Generate a deterministic abstract 3D hand fixture and test the mask path.

Engineering motion bounds are authored for software QA, not anatomical limits.
No Text2HOI/MANO, fitted body, real grasp, human feasibility or security claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from dataset_pipeline.candidate import build_candidate
from dataset_pipeline.common import LANDMARK_NAMES
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.storage import private_output

VERSION = 'authored_3d_hand_fixture_v1'
TEMPLATES = ('index_flex','middle_flex','alternating')
FINGERS = {5:((-.38,-.05,0.),(.35,.28,.22)),
           9:((0.,0.,0.),(.28,.24,.20)),
           13:((.38,-.05,0.),(.34,.27,.21)),
           17:((.66,-.16,0.),(.25,.20,.18))}
BOUNDS_RADIANS = (.35,.45,.25)  # unvalidated engineering envelope, not human safety limits
WIDTH, HEIGHT, SCALE = 512, 420, 150.


def generate_motion(template,seed,frames=24,fps=12.):
    if template not in TEMPLATES or isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
        raise ValueError('Known template and nonnegative integer seed required')
    if isinstance(frames,bool) or not isinstance(frames,int) or not 3<=frames<=240:
        raise ValueError('Fixture frame count must be between 3 and 240')
    if isinstance(fps,bool) or not isinstance(fps,(int,float)) or not math.isfinite(fps) or not 1<=fps<=60:
        raise ValueError('Fixture FPS must be finite and between 1 and 60')
    rng=np.random.default_rng(seed)
    amplitude=float(rng.uniform(.75,1.0))
    result=[]
    for i in range(frames):
        phase=i/(frames-1)
        wave=(1-math.cos(2*math.pi*phase))/2
        p=np.zeros((21,3));p[0]=(0.,-.75,0.);p[1]=(-.2,-.48,0.)
        for j,length in enumerate((.28,.24,.18),start=2):
            p[j]=p[j-1]+np.array([-math.sin(1.1),math.cos(1.1),0.])*length
        angles={}
        for base,(location,lengths) in FINGERS.items():
            flex=wave if ((template=='index_flex' and base==5) or
                           (template=='middle_flex' and base==9)) else 0.
            if template=='alternating' and base in (5,13):
                flex=wave if base==5 else 1-wave
            joint_angles=np.array(BOUNDS_RADIANS)*flex*amplitude
            angles[str(base)]=joint_angles.tolist();p[base]=location
            theta=0.
            for j,(length,angle) in enumerate(zip(lengths,joint_angles),start=1):
                theta+=angle
                p[base+j]=p[base+j-1]+np.array([0.,length*math.cos(theta),length*math.sin(theta)])
        translation=np.array([.04*math.sin(2*math.pi*phase),0.,0.])
        p+=translation
        xy=np.stack((256.+SCALE*p[:,0],220.-SCALE*p[:,1]),axis=1)
        if not np.isfinite(p).all() or (xy[:,0]<0).any() or (xy[:,0]>=WIDTH).any() or (xy[:,1]<0).any() or (xy[:,1]>=HEIGHT).any():
            raise ValueError('Authored fixture leaves the configured viewport')
        result.append({'frame_idx':i,'source_pts_ms':i*1000./fps,'detected':True,
            'landmarks_world':{name:dict(zip(('x','y','z'),point.tolist())) for name,point in zip(LANDMARK_NAMES,p)},
            'landmarks_px':{name:{'x':float(v[0]),'y':float(v[1]),'z':float(point[2])}
                            for name,v,point in zip(LANDMARK_NAMES,xy,p)},
            'authored_joint_flex_radians':angles})
    return result


def draw_frame(frame):
    image=np.full((HEIGHT,WIDTH,3),(40,32,24),np.uint8)
    p=[(int(frame['landmarks_px'][name]['x']),int(frame['landmarks_px'][name]['y'])) for name in LANDMARK_NAMES]
    cv2.fillPoly(image,[np.array([p[j] for j in (0,1,5,9,13,17)],np.int32)],(130,174,206))
    for start in (1,5,9,13,17):
        cv2.line(image,p[0],p[start],(160,196,220),7)
        for a,b in zip(range(start,start+3),range(start+1,start+4)):
            cv2.line(image,p[a],p[b],(160,196,220),9)
    for point in p:cv2.circle(image,point,4,(210,230,244),-1)
    cv2.putText(image,'AUTHORED FIXTURE / NOT HUMAN VALIDATION',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.46,(220,220,220),1,cv2.LINE_AA)
    return image


def build_fixture(output,*,template,seed,w3_new,frames=24,fps=12.):
    output = private_output(output)
    if isinstance(w3_new,bool) or not isinstance(w3_new,(int,float)) or not math.isfinite(w3_new) or w3_new<=0:
        raise ValueError('Explicit finite positive mask multiplier required')
    records=generate_motion(template,seed,frames,fps)
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    source=root/'authored_source.avi'
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'FFV1'),fps,(WIDTH,HEIGHT))
    try:
        if not writer.isOpened():raise ValueError('FFV1 writer unavailable')
        for record in records:writer.write(draw_frame(record))
    finally:
        writer.release()
    capture=cv2.VideoCapture(str(source))
    try:
        for record in records:
            ok,_image=capture.read()
            if not ok:raise ValueError('Fixture source decode is incomplete')
            record['source_pts_ms']=capture.get(cv2.CAP_PROP_POS_MSEC)
        if capture.read()[0]:raise ValueError('Unexpected fixture source frame')
    finally:
        capture.release()
    (root/'private_reference.json').write_text(json.dumps({'schema_version':1,'frames':records},indent=2,allow_nan=False)+'\n',encoding='utf8')
    config=PipelineConfig();gate=gate_clip(records,w3_new,config)
    report={'generator_version':VERSION,'generator_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'origin_type':'self_authored_procedural_fixture','template_id':template,'seed':seed,
            'frame_count':frames,'fps':fps,'w3_new':w3_new,'gate_policy':gate['policy_version'],
            'gate_pass_frac':gate['pass_frac'],'gate_accepted':gate['accepted'],
            'state':'RESEARCH_FIXTURE_ONLY','release_allowed':False,'artifact':None,
            'bounds_radians':BOUNDS_RADIANS,'bounds_status':'unvalidated_engineering_parameters',
            'learned_model':None,'object_contact_model':None,'human_feasibility_tested':False,
            'limitations':['not observed human motion; not anatomical ground truth',
                           'abstract bone graph; no surface collision or grasp physics',
                           'seed variation does not establish independent motion families',
                           'not a Text2HOI reproduction or a completed data-backed P1 study']}
    if gate['accepted']:
        report['artifact']=build_candidate(source,records,{'width':WIDTH,'height':HEIGHT,'fps':fps,'total_frames':frames},
                                            w3_new,config,root/'candidates')
    (root/'fixture_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')
    cv2.imwrite(str(root/'preview.png'),draw_frame(records[len(records)//2]))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--template',choices=TEMPLATES,required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--w3',type=float,required=True)
    parser.add_argument('--frames',type=int,default=24);parser.add_argument('--fps',type=float,default=12.)
    args=parser.parse_args()
    report=build_fixture(args.output,template=args.template,seed=args.seed,w3_new=args.w3,frames=args.frames,fps=args.fps)
    print(json.dumps({k:report[k] for k in ('generator_version','template_id','gate_accepted','gate_pass_frac','state')}))


if __name__=='__main__':main()
