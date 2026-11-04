"""Build private research candidates through the unchanged Stage6 renderer.

The intermediate video is private and lossless (FFV1). No RELEASED asset is
created: rights, human/security review and independent PTS/track QA are separate.
"""
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import cv2

from dataset_pipeline.stage6_occlusion import generate_occluded_video
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.timeline import build_frame_map


def build_candidate(video_path, frames, info, w3_new, config, output_root,
                    *, max_cache_bytes=256 * 1024 * 1024, max_output_frames=20000):
    if len(frames) > max_output_frames:
        raise ValueError('Output frame count exceeds candidate build budget')
    timeline = build_frame_map(frames, info)
    gate = gate_clip(frames, w3_new, config)
    if not gate['accepted']:
        raise ValueError('Stage7 rejected this candidate')
    width, height = info['width'], info['height']
    if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in (width, height)):
        raise ValueError('Positive integer video dimensions required')
    selected = {f['source_frame_idx'] for f in timeline['frames']}
    # Bound decoded memory before reading the source, not after allocating it.
    if len(selected) * width * height * 3 > max_cache_bytes:
        raise ValueError('Selected source frames exceed decoded cache budget')
    cap = cv2.VideoCapture(str(video_path))
    cache, observed_pts = {}, {}
    try:
        if not cap.isOpened():
            raise ValueError('Could not open source video')
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(source_fps) or not math.isclose(source_fps, info['fps'], rel_tol=1e-6):
            raise ValueError('Source FPS differs from extraction metadata')
        count, previous_pts = 0, None
        while True:
            ok, image = cap.read()
            if not ok:
                break
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)
            if not math.isfinite(pts) or pts < 0 or (previous_pts is not None and pts <= previous_pts):
                raise ValueError('Source decoder did not report increasing timestamps')
            previous_pts = pts
            if image.shape[:2] != (height, width):
                raise ValueError('Source dimensions differ from extraction metadata')
            if count in selected:
                cache[count], observed_pts[count] = image, pts
            count += 1
        if 'total_frames' in info and info['total_frames'] != count:
            raise ValueError('Decoded source count differs from extraction metadata')
        if set(cache) != selected:
            raise ValueError('Mapped source frame does not exist')
        for f in timeline['frames']:
            if not math.isclose(f['source_pts_ms'], observed_pts[f['source_frame_idx']], abs_tol=0.01):
                raise ValueError('Mapped source time differs from decoded source time')
    finally:
        cap.release()

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    # Unique directories are private until artifact.json is atomically linked.
    # Readers must require that manifest and validate its output hash.
    with tempfile.TemporaryDirectory(prefix='.building-', dir=root) as temporary:
        temporary = Path(temporary)
        aligned = temporary / 'aligned_private.avi'
        writer = cv2.VideoWriter(str(aligned), cv2.VideoWriter_fourcc(*'FFV1'),
                                 timeline['output_fps'], (width, height))
        try:
            if not writer.isOpened():
                raise ValueError('Lossless private timeline writer is unavailable')
            for f in timeline['frames']:
                writer.write(cache[f['source_frame_idx']])
        finally:
            writer.release()
        aligned_frames = [{**frame, 'frame_idx': i} for i, frame in enumerate(frames)]
        masked = temporary / 'masked.mp4'
        generate_occluded_video(str(aligned), aligned_frames,
                                {'width': width, 'height': height, 'fps': timeline['output_fps']},
                                w3_new, str(masked))
        capture = cv2.VideoCapture(str(masked))
        output_times = []
        try:
            if not capture.isOpened():
                raise ValueError('Final candidate cannot be opened')
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                output_times.append(capture.get(cv2.CAP_PROP_POS_MSEC))
            expected = [f['output_pts_ms'] for f in timeline['frames']]
            if len(output_times) != len(expected) or any(
                    not math.isfinite(a) or not math.isclose(a, b, abs_tol=0.1)
                    for a, b in zip(output_times, expected)):
                raise ValueError('Final candidate timing differs from the explicit CFR map')
        finally:
            capture.release()
        artifact_hash = hashlib.sha256(masked.read_bytes()).hexdigest()
        manifest = {'schema_version': 1, 'state': 'RESEARCH_CANDIDATE',
                    'release_allowed': False, 'rights_status': 'UNREVIEWED',
                    'gate_policy_version': gate['policy_version'], 'w3_new': w3_new,
                    'mask_formula': 'midpoint_P0_P9_v1', 'timeline': timeline,
                    'decoded_frame_count': len(output_times), 'output_sha256': artifact_hash,
                    'media_file': 'masked.mp4', 'config': config.to_dict(),
                    'limitations': ['decoder timestamps are not independent container PTS proof',
                                    'source duration is retimed to explicit CFR after selection',
                                    'no rights, anatomical, human or attack release approval']}
        manifest_path = temporary / 'artifact.json'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
        # Hash-addressed names avoid source names and accidental replacement.
        target = root / artifact_hash
        target.mkdir()  # existing candidate, including an incomplete one, is never overwritten
        created = []
        try:
            os.link(masked, target / 'masked.mp4')
            created.append(target / 'masked.mp4')
            os.link(manifest_path, target / 'artifact.json')  # completion marker published last
            created.append(target / 'artifact.json')
        except BaseException:
            # Delete only files created by this call, and leave existing candidates alone.
            for p in reversed(created):
                p.unlink()
            try:
                target.rmdir()
            except OSError:
                pass  # a competing file is not ours to delete
            raise
        return {'artifact_id': artifact_hash, 'state': manifest['state'],
                'release_allowed': False, 'manifest_file': f'{artifact_hash}/artifact.json',
                'media_file': f'{artifact_hash}/masked.mp4', 'output_sha256': artifact_hash,
                'frame_count': len(output_times), 'timeline_version': timeline['version']}
