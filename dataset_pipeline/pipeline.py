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
import uuid

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage1_extract import extract_landmarks
from dataset_pipeline.stage2_quality import apply_quality_filter
from dataset_pipeline.stage3_frontality import apply_frontality_filter
from dataset_pipeline.stage4_length_norm import length_normalize, final_length_sec
from dataset_pipeline.stage5_weights import estimate_weights
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.candidate import build_candidate
from dataset_pipeline.storage import private_output


def process_clip(video_path, config):
    """Runs Stage 1-4 for a single clip. Returns (report_dict, extended_frames)
    -- extended_frames is None if the clip was discarded at Stage 2 or 3."""
    clip_id = os.path.basename(video_path)
    frames, info = extract_landmarks(video_path, confidence=config.quality_conf_min)

    quality = apply_quality_filter(frames, config)
    report = {
        "clip_id": clip_id,
        "video_info": {k: info[k] for k in ('width', 'height', 'fps', 'total_frames')},
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


def run_batch(video_paths, config=None, w3_new=None, output_dir=None, *, render_candidates=False):
    if output_dir is not None:
        output_dir = str(private_output(output_dir))
    config = config or PipelineConfig()
    video_paths = list(video_paths)
    paths_by_id = {os.path.basename(p): p for p in video_paths}
    if len(paths_by_id) != len(video_paths):
        raise ValueError('Duplicate source basenames are ambiguous; use unique clip names')
    if render_candidates and not output_dir:
        raise ValueError('Candidate rendering requires a private output directory')
    if output_dir:
        if os.path.exists(output_dir) and (not os.path.isdir(output_dir) or os.listdir(output_dir)):
            raise FileExistsError('Batch output must be a new or empty private directory')
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, '.pipeline_owner'), 'x', encoding='ascii') as owner:
            owner.write(uuid.uuid4().hex + '\n')
    clip_reports = []
    accepted_frames_by_clip = {}

    for path in video_paths:
        try:
            report, extended = process_clip(path, config)
        except (OSError, ValueError, RuntimeError) as error:
            report = {'clip_id': os.path.basename(path), 'final_status': 'quarantined_extraction',
                      'extraction_error_type': type(error).__name__}
            diagnostic_id = getattr(error, 'diagnostic_id', None)
            if isinstance(diagnostic_id, str):
                report['private_diagnostic_id'] = diagnostic_id
            clip_reports.append(report)
            continue
        if extended is not None:
            accepted_frames_by_clip[report["clip_id"]] = extended
        clip_reports.append(report)

    weights_report = None
    if w3_new is None and accepted_frames_by_clip:
        weights_report = estimate_weights(list(accepted_frames_by_clip.values()), config)
        w3_new = weights_report.get("w3_new")

    manifest, artifacts = [], []
    if w3_new is not None:
        for report in clip_reports:
            clip_id = report["clip_id"]
            if clip_id not in accepted_frames_by_clip:
                continue
            gate = gate_clip(accepted_frames_by_clip[clip_id], w3_new, config)
            report["stage7"] = {
                "policy_version": gate["policy_version"],
                "accepted": gate["accepted"],
                "pass_frac": gate["pass_frac"],
                "failing_frame_idxs": gate["failing_frame_idxs"],
            }
            report["final_status"] = "accepted" if gate["accepted"] else "discarded_stage7"
            if gate["accepted"]:
                if render_candidates:
                    try:
                        artifact = build_candidate(paths_by_id[clip_id], accepted_frames_by_clip[clip_id],
                                                   report['video_info'], w3_new, config,
                                                   os.path.join(output_dir, 'artifacts'))
                        artifacts.append({'clip_id': clip_id, **artifact})
                        report['artifact'] = artifact
                        report['final_status'] = 'artifact_verified_research'
                    except (ValueError, OSError) as error:
                        report['final_status'] = 'quarantined_render'
                        report['artifact_error'] = str(error)
                        continue
                manifest.append(clip_id)

    result = {"clip_reports": clip_reports, "weights_report": weights_report, "manifest": manifest,
              "artifacts": artifacts, "manifest_scope": 'research_artifacts' if render_candidates else 'geometry_only'}

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "pipeline_report.json"), "x", encoding="utf-8") as fh:
            json.dump({"config": config.to_dict(), "w3_new_used": w3_new, "clips": clip_reports}, fh, ensure_ascii=False, indent=2)
        if weights_report:
            with open(os.path.join(output_dir, "weights_report.json"), "x", encoding="utf-8") as fh:
                json.dump(weights_report, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(output_dir, "manifest.json"), "x", encoding="utf-8") as fh:
            json.dump({"accepted_clips": manifest, "scope": result['manifest_scope'],
                       "release_allowed": False, "artifacts": artifacts}, fh, ensure_ascii=False, indent=2)

    return result
