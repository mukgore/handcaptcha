"""Explicit source-to-output mapping for filtered/reversed, CFR-retimed clips.

Source times are decoder-reported milliseconds, not an independently audited
container PTS table. Missing/contradictory times fail; array order is not time.
"""
import math

TIMELINE_VERSION = "source_index_decoder_ms_to_cfr_v1"


def build_frame_map(frames, info, output_fps=None):
    fps = info['fps'] if output_fps is None else output_fps
    if not frames or not math.isfinite(fps) or fps <= 0:
        raise ValueError('Nonempty frames and a positive finite output FPS required')
    by_source, mapping = {}, []
    for i, frame in enumerate(frames):
        index, pts = frame.get('frame_idx'), frame.get('source_pts_ms')
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError('A nonnegative integer source frame index is required')
        if isinstance(pts, bool) or not isinstance(pts, (int, float)) or not math.isfinite(pts) or pts < 0:
            raise ValueError('Decoder source_pts_ms is required for every frame')
        signature = (float(pts), frame.get('landmarks_px'))
        if index in by_source and by_source[index] != signature:
            raise ValueError('Conflicting time or landmarks for the same source frame')
        by_source[index] = signature
        mapping.append({'output_frame_idx': i, 'output_pts_ms': i * 1000. / fps,
                        'source_frame_idx': index, 'source_pts_ms': float(pts),
                        'reference_index': index, 'transform': 'selection_and_cfr_retime'})
    ordered = sorted(by_source)
    if any(by_source[b][0] <= by_source[a][0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Source timestamps must increase with source frame index')
    return {'version': TIMELINE_VERSION, 'source_time_basis': 'decoder_reported_ms',
            'output_time_basis': 'explicit_cfr_retime', 'output_fps': float(fps),
            'output_duration_ms': len(frames) * 1000. / fps, 'frames': mapping}
