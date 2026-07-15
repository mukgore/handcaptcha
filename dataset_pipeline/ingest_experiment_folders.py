# -*- coding: utf-8 -*-
"""Ingests `*_experiment/` folders produced by the handtest1-style batch
Colab notebook (baseline_original.mp4 + level3_DIP.mp4 + experiment_data.json)
into this project's pool_manifest.json schema.

These clips get the same "trusted legacy recording" treatment
migrate_legacy_actions.py gives the original 6 -- no Stage 2/3/7 gating is
re-run, and level3_DIP.mp4 is used exactly as that notebook already
generated it (old 5-point-MCP-average ratio formula, not this project's
newer midpoint(P0,P9) formula) for consistency with the existing pool.

Handedness is auto-detected by re-running this project's own MediaPipe
extraction on baseline_original.mp4, since that notebook's own
experiment_data.json doesn't store a handedness label.
"""
import glob
import json
import os
import shutil

from dataset_pipeline.stage1_extract import extract_landmarks
from dataset_pipeline.export_pool import _dominant_handedness


def _find_level3_file(experiment_dir):
    """The batch notebook doesn't always name this file identically (some
    folders produced e.g. '2_level3_DIP.mp4' instead of 'level3_DIP.mp4') --
    match by suffix instead of an exact name."""
    matches = glob.glob(os.path.join(experiment_dir, "*level3_DIP.mp4"))
    if not matches:
        return None
    return matches[0]


def ingest_experiment_folder(experiment_dir, clip_id, output_dir=".", label=None):
    """experiment_dir: path to one '{name}_experiment' folder from the notebook.
    clip_id: short ASCII id to use in the pool/filenames (should not collide
    with existing pool clip_ids like l1/l2/l3/r1/r2/r3). label: optional
    human-readable description (e.g. the original Korean folder name) kept
    in the manifest for documentation, kept separate from clip_id/filenames
    to avoid non-ASCII-filename encoding issues in the manual GitHub upload
    workflow this project currently relies on."""
    baseline_path = os.path.join(experiment_dir, "baseline_original.mp4")
    level3_path = _find_level3_file(experiment_dir)
    if not os.path.exists(baseline_path) or not level3_path:
        raise FileNotFoundError(f"{experiment_dir}에 baseline_original.mp4 또는 *level3_DIP.mp4가 없습니다.")

    frames, info = extract_landmarks(baseline_path)
    handedness = _dominant_handedness(frames)

    os.makedirs(output_dir, exist_ok=True)
    landmarks_out = os.path.join(output_dir, f"{clip_id}_landmarks.json")
    payload = {
        "video_info": {"width": info["width"], "height": info["height"], "fps": info["fps"]},
        "frames": [
            {"frame_idx": f.get("frame_idx"), "detected": bool(f.get("detected")), "landmarks_px": f.get("landmarks_px")}
            for f in frames
        ],
    }
    with open(landmarks_out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)

    video_out = os.path.join(output_dir, f"{clip_id}.mp4")
    shutil.copy2(level3_path, video_out)

    return {
        "clip_id": clip_id,
        "label": label,
        "handedness": handedness,
        "video_file": f"{clip_id}.mp4",
        "landmarks_file": f"{clip_id}_landmarks.json",
        "n_frames": len(frames),
        "fps": info["fps"],
    }


def ingest_many(experiment_dirs_with_ids, output_dir="."):
    """experiment_dirs_with_ids: list of (experiment_dir, clip_id, label) triples."""
    new_entries = [ingest_experiment_folder(d, cid, output_dir, label=lbl) for d, cid, lbl in experiment_dirs_with_ids]

    manifest_path = os.path.join(output_dir, "pool_manifest.json")
    manifest = {"w3_new": None, "clips": []}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)

    by_id = {c["clip_id"]: c for c in manifest.get("clips", [])}
    for entry in new_entries:
        by_id[entry["clip_id"]] = entry  # add new, or overwrite a same-id re-ingest
    manifest["clips"] = list(by_id.values())

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    handedness_counts = {}
    for e in new_entries:
        handedness_counts[e["handedness"]] = handedness_counts.get(e["handedness"], 0) + 1
    print(f"{len(new_entries)}개 클립 편입 완료 ({handedness_counts}), 풀 전체: {len(manifest['clips'])}개")
    return manifest
