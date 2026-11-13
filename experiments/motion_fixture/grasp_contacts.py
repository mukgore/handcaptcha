"""Two authored contact topologies and orthographic depth counterexamples.

Kinematic capsule/sphere software fixtures, not anatomical hands, force closure,
learned generation, human-feasible grasps or CAPTCHA efficacy evidence.
"""
import copy
import math
import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES
from .contact import EDGES,segment_distance

VERSION='authored_contact_topology_v1'
KINDS=('opposed_two_tip','three_tip_front')
RADIUS=.025
TOLERANCE=.003
LENGTHS={1:(.20,.19,.17),5:(.20,.19,.17),9:(.28,.24,.20),13:(.34,.27,.21),17:(.25,.20,.18)}


def smooth(value):
    value=min(1.,max(0.,value));return value*value*(3-2*value)


def finger(base,lengths,target,branch):
    """Two-link planar IK with the first two bones collinear; x stays fixed."""
    base,target=np.asarray(base,float),np.asarray(target,float)
    if not np.isfinite(base).all() or not np.isfinite(target).all() or abs(base[0]-target[0])>1e-12:
        raise ValueError('Finite constant-x fixture plane required')
    a,b=sum(lengths[:2]),lengths[2];delta=target[1:]-base[1:];distance=float(np.linalg.norm(delta))
    if not abs(a-b)+1e-9<distance<a+b-1e-9:raise ValueError('Target outside the authored IK envelope')
    angle=math.atan2(delta[1],delta[0])+branch*math.acos(np.clip((a*a+distance*distance-b*b)/(2*a*distance),-1.,1.))
    direction=np.array([0.,math.cos(angle),math.sin(angle)])
    return np.array([base,base+lengths[0]*direction,base+a*direction,target])


def records(kind,seed,frames=24,fps=12):
    if kind not in KINDS or type(seed) is not int or seed<0:raise ValueError('Explicit authored topology and seed required')
    if type(frames) is not int or not 12<=frames<=240 or type(fps) not in (int,float) or not math.isfinite(fps) or not 1<=fps<=60:
        raise ValueError('Bounded fixture frame count/FPS required')
    radius=float(np.random.default_rng(seed).uniform(.14,.16));offset=radius+RADIUS;result=[]
    for i in range(frames):
        t=i/(frames-1);closure=min(smooth(t/.3),smooth((1-t)/.3))
        carry=.08*smooth((t-.4)/.2);translation=np.array([carry,0.,0.])
        points=np.zeros((21,3));points[0]=(0.,-.75,0.)
        for base,x in ((1,-offset),(5,offset)):
            points[base:base+4]=finger([x,0.,0.],LENGTHS[base],[x,.35+.10*closure,.10+.15*closure],1)
        if kind=='three_tip_front':
            points[9:13]=finger([0.,0.,0.],LENGTHS[9],[0.,.35+.10*closure,.25-offset-.15*(1-closure)],-1)
        else:
            points[9]=(0.,0.,0.);direction=np.array([0.,math.cos(-.25),math.sin(-.25)])
            for j,length in enumerate(LENGTHS[9],1):points[9+j]=points[8+j]+length*direction
        for base,location in ((13,(.38,-.05,0.)),(17,(.66,-.16,0.))):
            points[base]=location
            for j,length in enumerate(LENGTHS[base],1):points[base+j]=points[base+j-1]+[0.,length,0.]
        points+=translation
        center=np.array([0.,.45,.25])+translation
        xy=np.column_stack([256+150*points[:,0],220-150*points[:,1]])
        if not np.isfinite(points).all() or (xy[:,0]<0).any() or (xy[:,0]>=512).any() or (xy[:,1]<0).any() or (xy[:,1]>=420).any():
            raise ValueError('Authored fixture leaves viewport')
        result.append({'frame_idx':i,'source_pts_ms':i*1000/fps,'detected':True,
            'landmarks_world':{name:dict(zip(('x','y','z'),point.tolist())) for name,point in zip(LANDMARK_NAMES,points)},
            'landmarks_px':{name:{'x':float(pixel[0]),'y':float(pixel[1]),'z':float(point[2])} for name,pixel,point in zip(LANDMARK_NAMES,xy,points)},
            'authored_object':{'kind':'kinematic_sphere','center':center.tolist(),'radius':radius,
                'support':'prescribed_kinematic_support; gravity/friction not simulated'},
            'authored_contact_tips':[4,8]+([12] if kind=='three_tip_front' else []),
            'authored_contact_phase':'hold' if .3<=t<=.7 else 'approach' if t<.3 else 'release'})
    return result


def reflect_depth(frames,*,object_too):
    if type(object_too) is not bool:raise ValueError('Explicit reflection scope required')
    result=copy.deepcopy(frames)
    for frame in result:
        for name in LANDMARK_NAMES:
            frame['landmarks_world'][name]['z']*=-1;frame['landmarks_px'][name]['z']*=-1
        if object_too:frame['authored_object']['center'][2]*=-1
    return result


def inspect(frames):
    if not frames:raise ValueError('Complete nonempty sequence required')
    lengths=None;minimum=math.inf;contacts=[];bad=[];held=[];tip_rows=[];object0=None;moved=0.
    initial_gaps=final_gaps=None;initial_radius=None;initial_tips=None;previous_time=-math.inf
    for i,frame in enumerate(frames):
        if type(frame['frame_idx']) is not int or frame['frame_idx']!=i:raise ValueError('Complete ordered frames required')
        timestamp=frame['source_pts_ms']
        if type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp<=previous_time:
            raise ValueError('Increasing finite source timestamps required')
        previous_time=timestamp
        p=np.array([[frame['landmarks_world'][n][a] for a in ('x','y','z')] for n in LANDMARK_NAMES])
        obj=frame['authored_object'];center=np.asarray(obj['center'],float);radius=obj['radius']
        if p.shape!=(21,3) or not np.isfinite(p).all() or center.shape!=(3,) or not np.isfinite(center).all() or type(radius) not in (int,float) or not math.isfinite(radius) or radius<=0:
            raise ValueError('Finite authored geometry required')
        current=np.array([np.linalg.norm(p[b]-p[a]) for a,b in EDGES])
        if not np.isfinite(current).all() or (current<=1e-12).any():raise ValueError('Representable nondegenerate bones required')
        if lengths is None:lengths=current
        if not np.allclose(lengths,current,rtol=0,atol=1e-10):raise ValueError('Bone lengths changed')
        clearances=[segment_distance(center,p[a],p[b])-radius-RADIUS for a,b in EDGES]
        if not all(math.isfinite(v) for v in clearances):raise ValueError('Representable clearances required')
        minimum=min(minimum,min(clearances))
        if min(clearances)<-1e-9:bad.append(i)
        tips=frame['authored_contact_tips']
        if tips not in ([4,8],[4,8,12]):raise ValueError('Known authored contact topology required')
        if initial_radius is None:initial_radius=radius;initial_tips=tips
        if radius!=initial_radius or tips!=initial_tips:raise ValueError('Fixed object and contact topology required')
        gaps=[float(np.linalg.norm(p[tip]-center)-radius-RADIUS) for tip in tips]
        active=all(abs(gap)<=TOLERANCE for gap in gaps)
        if active:contacts.append(i)
        if frame['authored_contact_phase']=='hold':held.append(i)
        if initial_gaps is None:initial_gaps=gaps;object0=center
        final_gaps=gaps;moved=max(moved,float(np.linalg.norm(center-object0)))
        tip_rows.append({'frame_idx':i,'tip_clearances':gaps})
    planned=bool(held and all(i in contacts for i in held) and
                 min(initial_gaps)>3*TOLERANCE and min(final_gaps)>3*TOLERANCE and
                 contacts[0]>0 and contacts[-1]<len(frames)-1 and moved>0)
    return {'scope':'authored_capsule_sphere_contact_topology_only','frames_n':len(frames),
        'contact_tips_n':len(frames[0]['authored_contact_tips']),'planned_hold_frames':held,
        'all_tip_contact_frames':contacts,'penetrating_frames':bad,'minimum_clearance':minimum,
        'object_displacement':moved,'plan_satisfied':planned,'accepted':planned and not bad,
        'tip_clearances':tip_rows,'release_allowed':False,
        'limitations':['authored IK envelope; no anatomical or human validation',
            'bone capsules only; no palm mesh/self-collision or force-closure proof',
            'object support/motion is prescribed; gravity/friction not simulated']}
