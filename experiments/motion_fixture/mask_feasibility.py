"""Exact all-frame feasible weight interval for the unchanged 2D Stage6/7.

Diagnostic generator constraints only, not dataset weight calibration or human
recognizability. Proposals must still pass the actual gate and renderer.
"""
import math

from dataset_pipeline.common import P0,P9,P10,P11,VISIBLE_FINGER_TIPS
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.stage7_gate import _validate_config


def inspect(frames,config):
    _validate_config(config)
    if not frames:raise ValueError('Full nonempty frame denominator required')
    lower=0.;upper=math.inf;rows=[]
    for frame in frames:
        points=frame_points(frame,'px')
        if points is None or len(points)!=21 or not all(math.isfinite(v) for p in points for v in p[:2]):
            raise ValueError('Complete finite image landmarks required')
        wrist,mcp=points[P0][:2],points[P9][:2];scale=math.dist(wrist,mcp)
        if not math.isfinite(scale) or scale<1e-8:raise ValueError('Unrepresentable or degenerate wrist/MCP scale')
        center=tuple((a+b)/2 for a,b in zip(wrist,mcp))
        midpoint=lambda a,b:tuple((x+y)/2 for x,y in zip(points[a][:2],points[b][:2]))
        required=max(math.dist(p,center) for p in (points[P10][:2],midpoint(P9,P10),midpoint(P10,P11)))
        visible=sorted((math.dist(points[index][:2],center) for index in VISIBLE_FINGER_TIPS.values()),reverse=True)
        if not all(math.isfinite(v) for v in (required,*visible)):raise ValueError('Unrepresentable landmark distance')
        lo=max(2/scale,2*required/(scale*(1-config.condition1_margin_frac)))
        hi=2*visible[config.condition2_min_visible_fingers-1]/(scale*(1+config.condition2_margin_frac))
        if not all(math.isfinite(v) for v in (lo,hi)):raise ValueError('Unrepresentable mask interval')
        lower=max(lower,lo);upper=min(upper,hi)
        rows.append({'frame_idx':frame['frame_idx'],'minimum_w3':lo,'maximum_w3':hi,'feasible':lo<=hi})
    feasible=lower<=upper
    return {'schema_version':1,'scope':'all_frame_stage7_2d_landmark_contract_only',
            'frames':len(frames),'minimum_w3':lower,'maximum_w3':upper,'feasible':feasible,
            'proposed_w3':lower+(upper-lower)/2 if feasible else None,'frame_intervals':rows,
            'policy':'midpoint_middle_pip_visible_fingertips_v2','release_allowed':False,
            'limitations':['source-specific generator proposal, not a fitted dataset/operating parameter',
                           'actual raster/gate must still be verified','no anatomical/human/security approval']}
