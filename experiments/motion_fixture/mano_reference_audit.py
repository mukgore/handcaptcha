"""Read-only checks on saved MANO geometry; never loads pickle/model weights.

Checks named surface tips and saved projection, not the anatomical semantics
of all internal joints, physical units, historical worker source or rights.
"""
import ast
import json
from pathlib import Path
import zipfile

import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES
from .accept_mano_pilot import load_bound_pilot,verify_pilot
from .biomechanical_features import extract,GeometryError,BONE_LABELS

TIP_NAMES=('thumb','index','middle','ring','pinky')
TIP_COLUMNS=(4,8,12,16,20)
PIXEL_TOLERANCE=.001  # float32 source projection vs independent float64 reconstruction


def named_tip_ids(source):
    path=Path(source)
    if path.stat().st_size>128*1024:raise ValueError('Vertex-ID source budget exceeded')
    tree=ast.parse(path.read_text(encoding='utf-8-sig'));matches=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='vertex_ids' for t in node.targets):
            matches.append(ast.literal_eval(node.value))
    if len(matches)!=1 or not isinstance(matches[0],dict) or 'mano' not in matches[0]:
        raise ValueError('One literal named MANO vertex-ID mapping required')
    return validate_tips(matches[0]['mano'])


def validate_tips(ids):
    if not isinstance(ids,dict) or set(ids)!=set(TIP_NAMES) or any(type(v) is not int or not 0<=v<778 for v in ids.values()) or len(set(ids.values()))!=5:
        raise ValueError('Five distinct named MANO surface-tip indices required')
    return {name:ids[name] for name in TIP_NAMES}


def projection(vertices,joints):
    """Declared fixed orthographic framing, recomputed independently in float64."""
    vertices=np.asarray(vertices,float);joints=np.asarray(joints,float)
    y=joints[0,9]-joints[0,0];yn=float(np.linalg.norm(y))
    if yn<=1e-10:raise ValueError('Degenerate projection wrist/middle axis')
    y/=yn;x=joints[0,17]-joints[0,5];x-=float(x@y)*y;xn=float(np.linalg.norm(x))
    if xn<=1e-10:raise ValueError('Degenerate projection palm plane')
    x/=xn;basis=np.column_stack((x,y));flat=vertices@basis
    low=flat.min(axis=(0,1));high=flat.max(axis=(0,1));extent=high-low
    if (extent<=1e-10).any():raise ValueError('Degenerate surface projection extent')
    scale=min((512-70)/extent[0],(420-70)/extent[1]);center=(low+high)/2
    xy=(joints@basis-center)*scale;xy[...,0]+=256;xy[...,1]=210-xy[...,1]
    return xy


def audit(pilot,tip_ids):
    pilot=Path(pilot).resolve(strict=True);ids=validate_tips(tip_ids)
    report,reference,binding=load_bound_pilot(pilot);frames=reference['frames'];count=len(frames)
    if not 3<=count<=240 or report.get('hand') not in ('left','right'):
        raise ValueError('Bounded full sequence and explicit handedness required')
    info=reference['source_info']
    if info.get('width')!=512 or info.get('height')!=420:raise ValueError('Known pilot projection layout required')
    archive=pilot/'private_surface.npz'
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist())!=4 or sum(i.file_size for i in z.infolist())>64*1024*1024:
            raise ValueError('Bounded four-array surface archive required')
    with np.load(archive,allow_pickle=False) as arrays:
        if set(arrays.files)!={'vertices','joints','faces','pose'}:raise ValueError('Known saved geometry arrays required')
        vertices,joints,faces,pose=(arrays[k] for k in ('vertices','joints','faces','pose'))
    if vertices.shape!=(count,778,3) or joints.shape!=(count,21,3) or faces.shape!=(1538,3) or pose.shape!=(count,6):
        raise ValueError('Full MANO surface/joint/PCA topology required')
    if any(a.dtype.kind not in 'fiu' or not np.isfinite(a).all() for a in (vertices,joints,pose)) or faces.dtype.kind not in 'iu' or faces.min()<0 or faces.max()>=778:
        raise ValueError('Finite numeric arrays and valid face indices required')
    if max(np.abs(vertices).max(),np.abs(joints).max())>1e6:raise ValueError('Native coordinate budget exceeded')
    if any(type(f['frame_idx']) is not int for f in frames) or [f['frame_idx'] for f in frames]!=list(range(count)) or any(f.get('authored_handedness')!=report['hand'] for f in frames):
        raise ValueError('Ordered frames and report/reference hand labels must agree')
    points=np.array([[[f['landmarks_world'][n][a] for a in ('x','y','z')] for n in LANDMARK_NAMES] for f in frames],float)
    xy=np.array([[[f['landmarks_px'][n][a] for a in ('x','y')] for n in LANDMARK_NAMES] for f in frames],float)
    if not np.isfinite(points).all() or not np.isfinite(xy).all():raise ValueError('Finite saved reference required')
    if not np.array_equal(points,joints.astype(float)):raise ValueError('Saved world reference differs from stored native joints')
    timestamps=np.array([f['source_pts_ms'] for f in frames],float)
    if not np.isfinite(timestamps).all() or (np.diff(timestamps)<=0).any():raise ValueError('Increasing complete source timestamps required')
    expected=vertices[:,[ids[name] for name in TIP_NAMES],:].astype(float)
    observed=points[:,TIP_COLUMNS,:]
    matches=np.all(observed==expected,axis=(0,2))
    tip_details={}
    for name,column,match in zip(TIP_NAMES,TIP_COLUMNS,matches):
        actual_ids=np.flatnonzero(np.all(vertices.astype(float)==points[:,column,None,:],axis=(0,2))).tolist()
        tip_details[name]={'matches_named_vertex_all_frames':bool(match),'observed_vertex_matches':actual_ids,
                           'expected_vertex_id':ids[name]}
    projected=projection(vertices,joints);error=float(np.max(np.abs(projected-xy)))
    projection_ok=error<=PIXEL_TOLERANCE
    eligible=bool(matches.all() and projection_ok)
    feature_rows=[];geometry_errors=[];lengths=[]
    if eligible:
        for i,p in enumerate(points):
            try:
                f=extract(p,handedness=report['hand']);lengths.append(f['bone_lengths'])
                feature_rows.append({'frame_idx':i,**{k:v.tolist() for k,v in f.items() if isinstance(v,np.ndarray)}})
            except GeometryError as exc:geometry_errors.append({'frame_idx':i,'code':exc.code})
    # Surface tips are not rigid skeletal joint centers. Describe variation;
    # never apply the authored fixed-20-bone invariant as an anatomy test here.
    spans=None
    if len(lengths)==count:
        lengths=np.array(lengths);relative=(lengths.max(axis=0)-lengths.min(axis=0))/lengths.mean(axis=0)
        is_tip=np.array([label.endswith('_TIP') for label in BONE_LABELS])
        spans={'non_tip_joint_edges_max_relative_span':float(relative[~is_tip].max()),
               'surface_tip_edges_max_relative_span':float(relative[is_tip].max())}
    verify_pilot(pilot,report,binding)
    return {'scope':'saved_mano_native_geometry_and_named_surface_tip_consistency_only',
        'frames_n':count,'hand':report['hand'],'component':report['component'],
        'state':'REFERENCE_CONSISTENCY_CHECKED_NOT_ANATOMICAL' if eligible else 'QUARANTINED_REFERENCE_CONSISTENCY',
        'reference_matches_saved_joints':True,'named_tips_match_all_frames_n':int(matches.sum()),
        'tip_mapping_all_five_match':bool(matches.all()),'projection_max_abs_error_px':error,
        'projection_tolerance_px':PIXEL_TOLERANCE,'projection_matches_declared_framing':projection_ok,
        'length_unit':'model_native_units','physical_unit_verified':False,
        'non_tip_joint_semantics_independently_recovered':False,'handedness_scope':'record/reference label consistency only',
        'measurable_feature_frames_n':len(feature_rows),'geometry_errors':geometry_errors,
        'bone_relative_spans':spans,'biological_validity_proven':False,'full_generator_ready':False,'release_allowed':False,
        'private_tip_details':tip_details,'private_features':feature_rows,
        'limitations':['No model/pickle/torch loaded; stored arrays only.',
            'Named surface-tip matches do not independently recover all internal joint semantics.',
            'Native units are not relabelled m/mm based on appearance or plausible hand size.',
            'No learned admissible hulls, self-collision/contact dynamics or human comfort verification.']}
