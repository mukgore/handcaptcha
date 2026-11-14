"""Evidence-bearing limits and fail-closed sampled-motion checks.

No human/data-derived limits are bundled. A pending/synthetic profile cannot
qualify a biological generator. Even sourced rule passes are not physics,
comfort, independent source authentication or an operational release.
"""
import math

import numpy as np

from .biomechanical_features import VERSION,GeometryError,extract,angular_derivatives

RULES=('bone_lengths','palm_curvatures','palm_spread_radians','joint_angle_hulls',
       'angular_speed_rad_s','angular_acceleration_rad_s2')
INTERVAL_SHAPES={'bone_lengths':(20,2),'palm_curvatures':(4,2),'palm_spread_radians':(4,2)}
MAIN='https://jankautz.com/publications/WeaklySupervised3DHand_ECCV20.pdf'
SUPPLEMENT='https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123620205-supp.pdf'


def pending_profile():
    return {'schema_version':1,'profile_version':'bmc21_limits_pending_v1','feature_version':VERSION,
        'length_unit':'authored_units','mapping_status':'unresolved',
        'mapping_evidence':'Numeric anatomical correspondence, units and thumb-specific limits are not established.',
        'rules':{name:{'status':'unresolved','values':None,'evidence':{
            'url':SUPPLEMENT if name=='joint_angle_hulls' else MAIN,
            'locator':'Formula only; no accepted numerical admissible limits for this rig.'}}
            for name in RULES}}


def _numeric(value,shape=None):
    raw=np.asarray(value)
    if raw.dtype.kind not in 'fiu':raise ValueError('Finite numeric profile values required')
    a=raw.astype(float)
    if (shape is not None and a.shape!=shape) or not np.isfinite(a).all() or (np.abs(a)>1e9).any():
        raise ValueError('Bounded profile shape/values required')
    return a


def polygon(value):
    p=_numeric(value)
    if p.ndim!=2 or p.shape[1]!=2 or not 3<=len(p)<=64:
        raise ValueError('Bounded convex CCW angle polygon required')
    if (np.abs(p[:,0])>math.pi).any() or (np.abs(p[:,1])>math.pi/2).any():
        raise ValueError('Hull must use the documented signed-radian convention')
    e=np.roll(p,-1,axis=0)-p
    if (np.linalg.norm(e,axis=1)<=1e-10).any():raise ValueError('Nondegenerate polygon edges required')
    for i,edge in enumerate(e):
        offsets=p-p[i];cross=edge[0]*offsets[:,1]-edge[1]*offsets[:,0]
        if (cross< -1e-10).any():raise ValueError('Convex CCW polygon required')
    area=np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))/2
    if area<=1e-10:raise ValueError('Positive angle hull area required')
    return p


def hull_distance(point,hull):
    """Supplement Sec.1: inside test and projected-edge periodic residual."""
    point=_numeric(point,(2,));p=polygon(hull);e=np.roll(p,-1,axis=0)-p;w=point-p
    cross=e[:,0]*w[:,1]-e[:,1]*w[:,0]
    if (cross>=-1e-10).all():return 0.
    t=np.clip(np.sum(w*e,axis=1)/np.sum(e*e,axis=1),0.,1.)
    closest=p+t[:,None]*e
    distance=np.sum(np.abs(np.cos(point)-np.cos(closest))+np.abs(np.sin(point)-np.sin(closest)),axis=1)
    return float(distance.min())


def validate(profile):
    fields={'schema_version','profile_version','feature_version','length_unit','mapping_status','mapping_evidence','rules'}
    if not isinstance(profile,dict) or set(profile)!=fields or type(profile['schema_version']) is not int or profile['schema_version']!=1 or profile['feature_version']!=VERSION:
        raise ValueError('Explicit supported biomechanical profile required')
    if profile['length_unit'] not in ('m','mm','authored_units') or profile['mapping_status'] not in ('unresolved','synthetic_test','documented'):
        raise ValueError('Explicit units and mapping status required')
    if any(not isinstance(profile[k],str) or not profile[k].strip() for k in ('profile_version','mapping_evidence')):
        raise ValueError('Profile version and coordinate/thumb correspondence evidence required')
    if not isinstance(profile['rules'],dict) or set(profile['rules'])!=set(RULES):
        raise ValueError('All static and temporal rule categories required')
    parsed={}
    for name in RULES:
        rule=profile['rules'][name]
        if not isinstance(rule,dict) or set(rule)!={'status','values','evidence'} or rule['status'] not in ('unresolved','synthetic_test','evidence_backed'):
            raise ValueError('Explicit rule status, values and evidence required')
        if not isinstance(rule['evidence'],dict) or not rule['evidence'] or any(not isinstance(v,str) or not v.strip() for v in rule['evidence'].values()):
            raise ValueError('Traceable nonempty rule evidence required')
        if rule['status']=='evidence_backed' and (not {'url','locator','value_origin','population_and_scope'}.issubset(rule['evidence']) or not rule['evidence']['url'].startswith('https://')):
            raise ValueError('Sourced values need location, origin and applicability evidence')
        if name=='bone_lengths' and rule['status']=='evidence_backed' and profile['length_unit']=='authored_units':
            raise ValueError('Physical bone limits require established m/mm units, not uncalibrated authored units')
        if rule['status']=='unresolved':
            if rule['values'] is not None:raise ValueError('Unresolved limits cannot silently carry approved values')
            parsed[name]=None;continue
        if name in INTERVAL_SHAPES:
            a=_numeric(rule['values'],INTERVAL_SHAPES[name])
            if (a[:,0]>a[:,1]).any():raise ValueError('Ordered intervals required')
            if name=='bone_lengths' and (a[:,0]<=0).any():raise ValueError('Positive physical bone lengths required')
            if name=='palm_spread_radians' and ((a<0).any() or (a>math.pi).any()):raise ValueError('Palm spread uses radians')
        elif name=='joint_angle_hulls':
            if not isinstance(rule['values'],list) or len(rule['values'])!=15:raise ValueError('All fifteen signed-angle hulls required')
            a=[polygon(p) for p in rule['values']]
        else:
            a=_numeric(rule['values'],(15,2))
            if (a<=0).any():raise ValueError('Positive angular speed/acceleration limits required')
        parsed[name]=a
    return parsed


def assess(points,times,profile,*,handedness,length_unit):
    parsed=validate(profile);raw=np.asarray(points);times=np.asarray(times,float)
    if raw.ndim!=3 or raw.shape[1:]!=(21,3) or len(raw)<3 or times.shape!=(len(raw),) or not np.isfinite(times).all() or (np.diff(times)<=0).any():
        raise ValueError('Complete sampled 3D motion and increasing timestamps in seconds required')
    if length_unit!=profile['length_unit']:raise ValueError('Motion/profile length units differ')
    features=[];errors=[]
    for i,pose in enumerate(raw):
        try:features.append((i,extract(pose,handedness=handedness)))
        except GeometryError as error:errors.append({'frame_idx':i,'code':error.code})
    unresolved=[k for k in RULES if parsed[k] is None]
    violations=[];maximum_residual={};private_features=[]
    for index,f in features:
        private_features.append({'frame_idx':index,**{k:v.tolist() for k,v in f.items() if isinstance(v,np.ndarray)}})
        for key in INTERVAL_SHAPES:
            if parsed[key] is None:continue
            value=f[key];interval=parsed[key];residual=np.maximum(interval[:,0]-value,0)+np.maximum(value-interval[:,1],0)
            maximum_residual[key]=max(maximum_residual.get(key,0.),float(residual.max()))
            if (residual>1e-10).any():violations.append({'frame_idx':index,'rule':key,'indices':np.flatnonzero(residual>1e-10).tolist()})
        if parsed['joint_angle_hulls'] is not None:
            residual=np.array([hull_distance(a,p) for a,p in zip(f['joint_angles_radians'],parsed['joint_angle_hulls'])])
            maximum_residual['joint_angle_hulls']=max(maximum_residual.get('joint_angle_hulls',0.),float(residual.max()))
            if (residual>1e-10).any():violations.append({'frame_idx':index,'rule':'joint_angle_hulls','indices':np.flatnonzero(residual>1e-10).tolist()})
    if not errors:
        lengths=np.array([f['bone_lengths'] for _,f in features])
        variation=np.abs(lengths-lengths[0]);tolerance=np.maximum(1e-10,lengths[0]*1e-8)
        for index in np.flatnonzero((variation>tolerance).any(axis=1)):
            violations.append({'frame_idx':int(index),'rule':'fixed_generated_rig_bone_lengths'})
        angular=np.array([f['joint_angles_radians'] for _,f in features]);v,a=angular_derivatives(angular,times)
        for name,values in (('angular_speed_rad_s',v),('angular_acceleration_rad_s2',a)):
            if parsed[name] is None:continue
            residual=np.maximum(np.abs(values)-parsed[name],0.)
            maximum_residual[name]=float(residual.max())
            for index in np.flatnonzero((residual>1e-10).any(axis=(1,2))):
                violations.append({'time_interval_idx':int(index),'rule':name})
    sourced=profile['mapping_status']=='documented' and all(profile['rules'][k]['status']=='evidence_backed' for k in RULES)
    passed=not errors and not unresolved and not violations
    state='UNMEASURABLE_GEOMETRY' if errors else 'UNRESOLVED_LIMITS' if unresolved else 'RULE_VIOLATIONS' if violations else 'DECLARED_RULES_PASS'
    return {'scope':'sampled_bmc_features_and_declared_limits_only','state':state,'profile_version':profile['profile_version'],
        'feature_version':VERSION,'frames_n':len(raw),'measurable_frames_n':len(features),'geometry_errors':errors,
        'unresolved_rules':unresolved,'violations':violations,'maximum_residual':maximum_residual,
        'declared_rules_pass':passed,'evidence_backed_rule_checks_pass':passed and sourced,
        'biological_validity_proven':False,'full_generator_ready':False,'release_allowed':False,
        'unchecked_requirements':['self_collision_and_anatomical_surface','object_contact_physics',
            'continuous_between_sample_motion','human_comfort_and_task_feasibility','profile_assertion_authentication'],
        'private_features':private_features}
