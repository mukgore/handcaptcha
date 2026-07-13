# -*- coding: utf-8 -*-
"""Stage 5 (spec §3): re-estimate the occlusion-circle weights from "open
hand" frames in the Jester sample, and cross-validate against InterHand2.6M.
"""
import numpy as np

from dataset_pipeline.common import OPEN_HAND_JOINTS, P0, P9, P10, P11
from dataset_pipeline.geometry import joint_angle, dist
from dataset_pipeline.stage1_extract import frame_points


def is_open_hand(world_pts, t_straight_deg):
    """All three interior joint angles (spec §5, read at the triple's middle
    index) must be >= T_straight."""
    return all(
        joint_angle(world_pts[p], world_pts[j], world_pts[c]) >= t_straight_deg
        for p, j, c in OPEN_HAND_JOINTS
    )


def frame_ratios(world_pts):
    """r_PIP = dist(P0,P10)/dist(P0,P9), r_DIP = dist(P0,P11)/dist(P0,P9).
    Scale-invariant shape ratios -- valid whether measured in 3D world units
    or (later, in Stage 6) in 2D pixel units on the same frontal-ish pose."""
    d09 = dist(world_pts[P0], world_pts[P9])
    if d09 < 1e-9:
        return None
    return dist(world_pts[P0], world_pts[P10]) / d09, dist(world_pts[P0], world_pts[P11]) / d09


def collect_open_hand_ratios(clips_frames, config):
    r_pip_samples, r_dip_samples = [], []
    for frames in clips_frames:
        for f in frames:
            pts = frame_points(f, "world")
            if pts is None or not is_open_hand(pts, config.t_straight_deg):
                continue
            ratios = frame_ratios(pts)
            if ratios is None:
                continue
            r_pip_samples.append(ratios[0])
            r_dip_samples.append(ratios[1])
    return r_pip_samples, r_dip_samples


def estimate_weights(clips_frames, config):
    """clips_frames: iterable of per-clip frame lists (each frame a dict as
    produced by stage1_extract.extract_landmarks), typically the Stage 2/3/4
    survivors across the whole Jester sample."""
    r_pip_samples, r_dip_samples = collect_open_hand_ratios(clips_frames, config)
    return {
        "w2_new": float(np.median(r_pip_samples)) if r_pip_samples else None,
        "w3_new": float(np.median(r_dip_samples)) if r_dip_samples else None,
        "n_open_hand_frames": len(r_pip_samples),
    }


def cross_validate_with_gt(gt_clips_world_frames, mp_clips_world_frames, config):
    """gt_*: per-clip frame lists sourced from InterHand2.6M's own 3D GT
    coordinates; mp_*: MediaPipe's own extraction on the same videos. Returns
    a correction factor per ratio to apply to the Jester-derived weights if
    MediaPipe's own coordinate error turns out to be large."""
    gt_pip, gt_dip = collect_open_hand_ratios(gt_clips_world_frames, config)
    mp_pip, mp_dip = collect_open_hand_ratios(mp_clips_world_frames, config)

    result = {"gt_n": len(gt_pip), "mp_n": len(mp_pip)}
    for name, gt_samples, mp_samples in (("pip", gt_pip, mp_pip), ("dip", gt_dip, mp_dip)):
        if gt_samples and mp_samples:
            gt_med, mp_med = float(np.median(gt_samples)), float(np.median(mp_samples))
            result[f"gt_median_{name}"] = gt_med
            result[f"mp_median_{name}"] = mp_med
            result[f"correction_factor_{name}"] = (gt_med / mp_med) if mp_med > 1e-9 else None
        else:
            result[f"correction_factor_{name}"] = None
    return result


def apply_correction(raw_value, correction_factor):
    if raw_value is None or correction_factor is None:
        return raw_value
    return raw_value * correction_factor
