# -*- coding: utf-8 -*-
"""Proves Stage 1/6/7 code paths execute without crashing, using one of the
repo's own demo clips (an already-occluded level3_DIP.mp4). This is NOT a
correctness validation against real data: the clip is a 2D-pixel occlusion
demo video, not raw 3D-world-landmark Jester footage, so its numeric results
(pass_frac etc.) are not meaningful -- see run_smoke_test()'s docstring.
Real Jester/InterHand2.6M validation must be run separately once those
datasets are available.
"""
import json
import os

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage1_extract import extract_landmarks
from dataset_pipeline.stage6_occlusion import generate_occluded_video
from dataset_pipeline.stage7_gate import gate_clip

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SMOKE_TEST_VIDEO = os.path.join(REPO_ROOT, "l1_level3_DIP.mp4")
SMOKE_TEST_W3 = 1.95  # arbitrary placeholder ratio, not a validated value


def run_smoke_test(video_path=DEFAULT_SMOKE_TEST_VIDEO, output_dir=None):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"스모크 테스트용 영상이 없습니다: {video_path}")

    print(f"[smoke-test] {video_path}")
    frames, info = extract_landmarks(video_path)
    detected = sum(1 for f in frames if f["detected"])
    print(f"[smoke-test] Stage 1: {detected}/{len(frames)} frames detected")

    config = PipelineConfig()
    gate = gate_clip(frames, SMOKE_TEST_W3, config)
    print(f"[smoke-test] Stage 6/7: pass_frac={gate['pass_frac']:.2f}, accepted={gate['accepted']}")

    result = {"detected_frames": detected, "total_frames": len(frames), "gate": gate}

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        masked_path = os.path.join(output_dir, "smoke_test_masked.mp4")
        generate_occluded_video(video_path, frames, info, SMOKE_TEST_W3, masked_path)
        print(f"[smoke-test] wrote {masked_path}")
        with open(os.path.join(output_dir, "smoke_test_report.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {**result, "note": "NOT a real-data validation -- see module docstring"},
                fh, ensure_ascii=False, indent=2,
            )

    print("[smoke-test] NOTE: this only proves the code paths run end-to-end;")
    print("[smoke-test] it does not validate correctness against real Jester/InterHand2.6M data.")
    return result


if __name__ == "__main__":
    run_smoke_test(output_dir=os.path.join(REPO_ROOT, "dataset_pipeline", "_smoke_output"))
