# -*- coding: utf-8 -*-
"""Spec §4: one-off T_frontal grid search. Runs Stage 2 only (no frontality
filter) over a Jester sample, uses Stage 6+7 as an automatic pass/fail
labeler, records each frame's theta, and sweeps candidate T thresholds to
find the F1-maximizing one.

Separate from the main pipeline chain (pipeline.py) since it's a one-time
calibration run, not part of the per-clip acceptance flow.
"""
import json

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage1_extract import extract_landmarks, frame_points
from dataset_pipeline.stage2_quality import apply_quality_filter
from dataset_pipeline.stage3_frontality import frame_theta
from dataset_pipeline.stage6_occlusion import project_occlusion_circle
from dataset_pipeline.stage7_gate import check_frame_conditions

# Old fixed level-3 ratio (1.95, per handtest1.py / dataset_expansion_spec_v1.md
# §0 background) used only as this grid search's auto-labeler -- w3_new isn't
# known yet at this stage since it depends on the T_frontal this search finds.
DEFAULT_W3_FOR_LABELING = 1.95


def f1_score(thetas, labels, t):
    tp = fp = fn = 0
    for theta, label in zip(thetas, labels):
        pred = theta < t
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif not pred and label:
            fn += 1
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run_grid_search(video_paths, output=None, config=None, w3=DEFAULT_W3_FOR_LABELING):
    config = config or PipelineConfig()
    thetas, labels = [], []

    for path in video_paths:
        frames, _info = extract_landmarks(path, confidence=config.quality_conf_min)
        quality = apply_quality_filter(frames, config)  # Stage 2 only, no frontality gate
        for f in quality["kept_frames"]:
            world_pts = frame_points(f, "world")
            px_pts = frame_points(f, "px")
            if world_pts is None or px_pts is None:
                continue
            center, radius = project_occlusion_circle(px_pts, w3)
            passed, _detail = check_frame_conditions(px_pts, center, radius, config)
            thetas.append(frame_theta(world_pts))
            labels.append(passed)

    scores = {t: f1_score(thetas, labels, t) for t in config.candidate_t_frontal_list}
    best_t = max(scores, key=scores.get) if scores else None
    result = {
        "candidate_scores": scores,
        "best_t_frontal_deg": best_t,
        "n_frames": len(thetas),
        "w3_used_as_labeler": w3,
    }
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    return result
