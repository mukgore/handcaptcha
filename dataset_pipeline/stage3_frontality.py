# -*- coding: utf-8 -*-
"""Stage 3 (spec §3): per-clip frontality gate using the palm normal vector
vs. the camera axis, in 3D world-landmark space.
"""
from dataset_pipeline.common import P0, P5, P17
from dataset_pipeline.geometry import cross3, angle_between
from dataset_pipeline.stage1_extract import frame_points

CAMERA_AXIS = (0.0, 0.0, 1.0)


def frame_theta(world_pts):
    """Angle (degrees) between the palm normal and the camera axis, folded
    into [0,90]. n=cross(P5-P0, P17-P0) flips sign between left/right hands
    and between palm-toward-camera vs. back-of-hand-toward-camera -- both
    should count as frontal (theta near 0), so we fold rather than use the
    raw angle directly."""
    n = cross3(
        (world_pts[P5][0] - world_pts[P0][0], world_pts[P5][1] - world_pts[P0][1], world_pts[P5][2] - world_pts[P0][2]),
        (world_pts[P17][0] - world_pts[P0][0], world_pts[P17][1] - world_pts[P0][1], world_pts[P17][2] - world_pts[P0][2]),
    )
    theta = angle_between(n, CAMERA_AXIS)
    return min(theta, 180.0 - theta)


def apply_frontality_filter(frames, config):
    thetas = []
    for f in frames:
        pts = frame_points(f, "world")
        if pts is None:
            continue
        thetas.append(frame_theta(pts))

    if not thetas:
        return {"accepted": False, "reason": "no_valid_frames", "frontal_frac": 0.0, "thetas": []}

    frontal_frac = sum(1 for t in thetas if t < config.t_frontal_deg) / len(thetas)
    accepted = frontal_frac >= config.frontal_pass_frac
    return {
        "accepted": accepted,
        "reason": None if accepted else "frontal_frac_below_threshold",
        "frontal_frac": frontal_frac,
        "thetas": thetas,
    }
