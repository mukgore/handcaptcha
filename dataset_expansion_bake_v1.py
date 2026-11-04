"""Reprocess adopted video sources through the current research pipeline.

Run with --adopted, --source-root, --output and an explicit --w3.
Legacy circle-only/JPEG-folder records cannot establish source frame timing.
"""
import argparse
import json
import math
from pathlib import Path

import cv2

from dataset_pipeline.pipeline import run_batch
from dataset_pipeline.storage import private_output


def bake_adopted(adopted_path, source_root, output_dir, w3_new):
    root = Path(source_root).resolve(strict=True)
    output = private_output(output_dir)
    if output.exists():
        raise FileExistsError('Use a new private output directory')
    if isinstance(w3_new, bool) or not isinstance(w3_new, (int, float)) or not math.isfinite(w3_new) or w3_new <= 0:
        raise ValueError('Explicit finite positive w3_new required')
    records = json.loads(Path(adopted_path).read_text(encoding='utf-8-sig'))
    if not isinstance(records, dict) or not records:
        raise ValueError('Expected a nonempty adopted-clip mapping')
    sources = []
    for clip_id, record in records.items():
        if not isinstance(record, dict) or not isinstance(clip_id, str):
            raise ValueError('Invalid adopted clip record')
        source = (root / clip_id).resolve(strict=True)
        if not source.is_relative_to(root) or source == root:
            raise ValueError('Clip path must stay inside source root')
        if not source.is_file():
            raise ValueError('Video source required; JPEG folders lack explicit frame-time evidence')
        fps = record.get('info', {}).get('fps')
        if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
            raise ValueError('Explicit adopted-source FPS required; no fallback FPS')
        capture = cv2.VideoCapture(str(source))
        try:
            actual = capture.get(cv2.CAP_PROP_FPS)
            if not capture.isOpened() or not math.isfinite(actual) or not math.isclose(actual, fps, rel_tol=1e-6):
                raise ValueError('Adopted FPS differs from decodable video source')
        finally:
            capture.release()
        sources.append(str(source))
    if len({Path(p).name for p in sources}) != len(sources):
        raise ValueError('Duplicate source basenames are ambiguous')
    # No old mask reuse: extraction, quality/frontality, explicit frame map,
    # Stage7 and the unchanged Stage6 renderer all run in the shared pipeline.
    return run_batch(sources, w3_new=w3_new, output_dir=str(output), render_candidates=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopted', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--w3', type=float, required=True)
    args = parser.parse_args(argv)
    result = bake_adopted(args.adopted, args.source_root, args.output, args.w3)
    return 0 if len(result['artifacts']) == len(result['clip_reports']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
