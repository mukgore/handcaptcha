# -*- coding: utf-8 -*-
"""Stage 7 (spec §3/§9): final automatic condition1/condition2 gate. No
reusable code exists in this repo for this check (grepped, not found) --
designed fresh from the plain-English spec definitions:
  condition 1: the occlusion circle fully covers the middle finger's first
               joint area (around P10).
  condition 2: palm/wrist shape cues remain visible outside the mask.
Per-frame AND of both conditions; per-clip gate requires 100% of frames to
pass (spec §5).
"""
from dataset_pipeline.common import P9, P10, P11, PALM_CUE_INDICES
from dataset_pipeline.geometry import dist, midpoint
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.stage6_occlusion import project_occlusion_circle


def check_frame_conditions(image_lm_px, center, radius, config):
    """condition1: P10 plus the midpoints of (P9,P10) and (P10,P11) -- a
    3-point proxy for the joint *area*, not just a single point -- must all
    lie within radius shrunk by condition1_margin_frac.
    condition2: a fixed palm-cue landmark set spanning the palm's outer
    boundary must all lie outside radius grown by condition2_margin_frac."""
    p9, p10, p11 = image_lm_px[P9], image_lm_px[P10], image_lm_px[P11]
    condition1_points = [p10, midpoint(p9, p10), midpoint(p10, p11)]
    inner_radius = radius * (1 - config.condition1_margin_frac)
    condition1 = all(dist(pt, center) <= inner_radius for pt in condition1_points)

    outer_radius = radius * (1 + config.condition2_margin_frac)
    condition2 = all(dist(image_lm_px[i], center) >= outer_radius for i in PALM_CUE_INDICES)

    return condition1 and condition2, {"condition1": condition1, "condition2": condition2}


def gate_clip(frames, w3_new, config):
    total, passed = 0, 0
    failing_frame_idxs = []
    for f in frames:
        pts = frame_points(f, "px")
        if pts is None:
            failing_frame_idxs.append(f.get("frame_idx"))
            continue
        center, radius = project_occlusion_circle(pts, w3_new)
        ok, _detail = check_frame_conditions(pts, center, radius, config)
        total += 1
        if ok:
            passed += 1
        else:
            failing_frame_idxs.append(f.get("frame_idx"))

    pass_frac = passed / total if total else 0.0
    accepted = pass_frac >= config.gate_pass_frac
    return {
        "accepted": accepted,
        "pass_frac": pass_frac,
        "failing_frame_idxs": failing_frame_idxs,
        "total_checked": total,
    }
