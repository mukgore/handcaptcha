# -*- coding: utf-8 -*-
"""Stage 2 (spec §3): drop frames with a sudden wrist jump or low detection
confidence; discard the whole clip if more than 10% of its frames get
dropped.
"""
import numpy as np

from dataset_pipeline.common import P0
from dataset_pipeline.stage1_extract import frame_points


def compute_wrist_jumps(frames):
    """Per-frame frame-to-frame wrist displacement (None where undetected or
    the previous frame was undetected)."""
    jumps = [None] * len(frames)
    prev = None
    for i, f in enumerate(frames):
        pts = frame_points(f, "world")
        if pts is None:
            prev = None
            continue
        wrist = np.asarray(pts[P0])
        if prev is not None:
            jumps[i] = float(np.linalg.norm(wrist - prev))
        prev = wrist
    return jumps


def apply_quality_filter(frames, config):
    jumps = compute_wrist_jumps(frames)
    valid_jumps = [j for j in jumps if j is not None]
    if len(valid_jumps) < 2:
        return {"accepted": False, "reason": "insufficient_frames", "dropped_frac": 1.0, "kept_frames": []}

    mean_j, std_j = float(np.mean(valid_jumps)), float(np.std(valid_jumps))
    jump_threshold = mean_j + config.quality_n_std * std_j

    kept, dropped = [], 0
    for i, f in enumerate(frames):
        conf = f.get("confidence")
        jump = jumps[i]
        drop = (
            not f.get("detected")
            or (conf is not None and conf < config.quality_conf_min)
            or (jump is not None and jump > jump_threshold)
        )
        if drop:
            dropped += 1
        else:
            kept.append(f)

    dropped_frac = dropped / len(frames) if frames else 1.0
    accepted = dropped_frac <= config.quality_max_drop_frac
    return {
        "accepted": accepted,
        "reason": None if accepted else "dropped_frac_exceeded",
        "dropped_frac": dropped_frac,
        "kept_frames": kept,
    }
