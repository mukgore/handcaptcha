# -*- coding: utf-8 -*-
"""python -m dataset_pipeline.cli {run|grid-search-frontal|smoke-test}"""
import argparse
import glob
import json

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.pipeline import run_batch


def _load_config(config_path):
    config = PipelineConfig()
    if config_path:
        with open(config_path, encoding="utf-8") as fh:
            overrides = json.load(fh)
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    return config


def cmd_run(args):
    config = _load_config(args.config)
    video_paths = []
    for pattern in args.clips:
        video_paths.extend(sorted(glob.glob(pattern)))
    if not video_paths:
        print("입력 클립을 찾을 수 없습니다:", args.clips)
        return
    result = run_batch(video_paths, config=config, w3_new=args.w3, output_dir=args.output)
    print(f"처리: {len(result['clip_reports'])}개 클립, 채택: {len(result['manifest'])}개")
    if result["weights_report"]:
        print("재추정 가중치:", result["weights_report"])


def cmd_grid_search_frontal(args):
    from dataset_pipeline.grid_search_frontal import run_grid_search

    config = _load_config(args.config)
    video_paths = []
    for pattern in args.clips:
        video_paths.extend(sorted(glob.glob(pattern)))
    result = run_grid_search(video_paths, output=args.output, config=config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_smoke_test(args):
    from dataset_pipeline.smoke_test import run_smoke_test, DEFAULT_SMOKE_TEST_VIDEO

    run_smoke_test(video_path=args.video or DEFAULT_SMOKE_TEST_VIDEO, output_dir=args.output)


def main():
    parser = argparse.ArgumentParser(prog="python -m dataset_pipeline.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Stage 1-7 파이프라인 실행")
    p_run.add_argument("clips", nargs="+", help="클립 경로 또는 glob 패턴")
    p_run.add_argument("--output", default="pipeline_output")
    p_run.add_argument("--config", default=None, help="PipelineConfig 오버라이드 JSON 파일")
    p_run.add_argument("--w3", type=float, default=None, help="w3_new를 직접 지정(생략 시 배치에서 재추정)")
    p_run.set_defaults(func=cmd_run)

    p_grid = sub.add_parser("grid-search-frontal", help="§4 T_frontal 그리드서치 (1회성)")
    p_grid.add_argument("clips", nargs="+")
    p_grid.add_argument("--output", default="t_frontal_grid_search.json")
    p_grid.add_argument("--config", default=None)
    p_grid.set_defaults(func=cmd_grid_search_frontal)

    p_smoke = sub.add_parser("smoke-test", help="저장소 자체 mp4로 코드 경로 실행 검증 (실데이터 검증 아님)")
    p_smoke.add_argument("--video", default=None)
    p_smoke.add_argument("--output", default=None)
    p_smoke.set_defaults(func=cmd_smoke_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
