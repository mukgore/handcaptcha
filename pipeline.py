# -*- coding: utf-8 -*-
"""Chains Stage 1-7 over a batch of clips and writes report/manifest outputs.

Stage 5 (weight re-estimation) is a whole-sample operation -- it needs to see
every clip's open-hand frames before it can produce w3_new -- so run_batch()
first runs Stage 1-4 per clip, then estimates weights once across the whole
batch (unless a w3_new is supplied, e.g. from a previous run or the
InterHand-corrected value), then runs Stage 6/7 gating per clip using that
shared weight.
"""
import json
import os

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage1_extract import extract_landmarks
from dataset_pipeline.stage2_quality import apply_quality_filter
from dataset_pipeline.stage3_frontality import apply_frontality_filter
from dataset_pipeline.stage4_length_norm import length_normalize, final_length_sec
from dataset_pipeline.stage5_weights import estimate_weights
from dataset_pipeline.stage7_gate import gate_clip


def process_clip(video_path, config):
    """Runs Stage 1-4 for a single clip. Returns (report_dict, extended_frames)
    -- extended_frames is None if the clip was discarded at Stage 2 or 3."""
    clip_id = os.path.basename(video_path)
    frames, info = extract_landmarks(video_path, confidence=config.quality_conf_min)

    quality = apply_quality_filter(frames, config)
    report = {
        "clip_id": clip_id,
        "stage2": {"dropped_frac": quality["dropped_frac"], "accepted": quality["accepted"]},
    }
    if not quality["accepted"]:
        report["final_status"] = "discarded_stage2"
        return report, None

    kept = quality["kept_frames"]
    frontality = apply_frontality_filter(kept, config)
    report["stage3"] = {"frontal_frac": frontality["frontal_frac"], "accepted": frontality["accepted"]}
    if not frontality["accepted"]:
        report["final_status"] = "discarded_stage3"
        return report, None

    extended = length_normalize(kept)
    report["stage4"] = {
        "orig_len_sec": (len(kept) / info["fps"]) if info["fps"] else None,
        "final_len_sec": final_length_sec(extended, info["fps"]),
    }
    report["final_status"] = "passed_stage1_4"
    return report, extended


def run_batch(video_paths, config=None, w3_new=None, output_dir=None):
    config = config or PipelineConfig()
    clip_reports = []
    accepted_frames_by_clip = {}

    for path in video_paths:
        report, extended = process_clip(path, config)
        if extended is not None:
            accepted_frames_by_clip[report["clip_id"]] = extended
        clip_reports.append(report)

    weights_report = None
    if w3_new is None and accepted_frames_by_clip:
        weights_report = estimate_weights(list(accepted_frames_by_clip.values()), config)
        w3_new = weights_report.get("w3_new")

    manifest = []
    if w3_new is not None:
        for report in clip_reports:
            clip_id = report["clip_id"]
            if clip_id not in accepted_frames_by_clip:
                continue
            gate = gate_clip(accepted_frames_by_clip[clip_id], w3_new, config)
            report["stage7"] = {
                "accepted": gate["accepted"],
                "pass_frac": gate["pass_frac"],
                "failing_frame_idxs": gate["failing_frame_idxs"],
            }
            report["final_status"] = "accepted" if gate["accepted"] else "discarded_stage7"
            if gate["accepted"]:
                manifest.append(clip_id)

    result = {"clip_reports": clip_reports, "weights_report": weights_report, "manifest": manifest}

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "pipeline_report.json"), "w", encoding="utf-8") as fh:
            json.dump({"config": config.to_dict(), "w3_new_used": w3_new, "clips": clip_reports}, fh, ensure_ascii=False, indent=2)
        if weights_report:
            with open(os.path.join(output_dir, "weights_report.json"), "w", encoding="utf-8") as fh:
                json.dump(weights_report, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"accepted_clips": manifest}, fh, ensure_ascii=False, indent=2)

    return result
