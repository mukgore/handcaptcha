"""Private surface visibility/cue audit; not a human/AI security experiment."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from dataset_pipeline.candidate import build_candidate
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.rendition import build_h264_rendition
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.stage6_occlusion import project_occlusion_circle
from dataset_pipeline.stage7_gate import gate_clip
from dataset_pipeline.storage import private_output
from .generate import WIDTH, HEIGHT, draw_frame
from .grasp_contacts import KINDS, records, reflect_depth, inspect
from .grasp_counterexamples import digest
from .mask_feasibility import inspect as feasible_mask
from .surface_passes import VERSION, MODES, OBJECT_ID, TARGET_IDS, render


def mask_for(frame, w3):
    center, radius = project_occlusion_circle(frame_points(frame, 'px'), w3)
    mask = np.zeros((HEIGHT, WIDTH), np.uint8)
    cv2.circle(mask, (int(center[0]), int(center[1])), int(radius), 1, -1)
    return mask.astype(bool)


def _video(path, images, fps, frames):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'FFV1'), fps, (WIDTH, HEIGHT))
    try:
        if not writer.isOpened(): raise ValueError('Lossless surface encoder unavailable')
        for image in images: writer.write(image)
    finally: writer.release()
    cap = cv2.VideoCapture(str(path))
    try:
        for image, frame in zip(images, frames):
            ok, decoded = cap.read()
            if not ok or not np.array_equal(image, decoded): raise ValueError('Surface source bytes changed')
            if abs(float(cap.get(cv2.CAP_PROP_POS_MSEC))-frame['source_pts_ms']) > .01:
                raise ValueError('Surface source timestamp mismatch')
        if cap.read()[0]: raise ValueError('Unexpected surface source frame')
    finally: cap.release()


def _encoded_pair(a, b, frames):
    caps = [cv2.VideoCapture(str(p)) for p in (a, b)]; changed = 0
    try:
        for _ in range(frames):
            ok_a, image_a = caps[0].read(); ok_b, image_b = caps[1].read()
            if not ok_a or not ok_b: raise ValueError('Missing final rendition pair frame')
            changed += int(not np.array_equal(image_a, image_b))
        if any(cap.read()[0] for cap in caps): raise ValueError('Extra final rendition pair frame')
    finally:
        for cap in caps: cap.release()
    return changed


def build(output, *, ffmpeg, ffprobe, seeds=(7, 19), frames=24, fps=12):
    if not isinstance(seeds, (tuple, list)) or not 1 <= len(seeds) <= 8 or len(set(seeds)) != len(seeds):
        raise ValueError('Explicit distinct bounded seeds required')
    recipes = [(kind, seed, records(kind, seed, frames, fps)) for seed in seeds for kind in KINDS]
    config = PipelineConfig(); interval = feasible_mask([f for _, _, seq in recipes for f in seq], config)
    if not interval['feasible']: raise ValueError('No shared mask; existing gate is unchanged')
    w3 = interval['proposed_w3']; root = private_output(output); root.mkdir(parents=True, exist_ok=False)
    info = {'width': WIDTH, 'height': HEIGHT, 'fps': fps, 'total_frames': frames}
    comparisons = []; outputs = []; wire_equal = 0; checked = 0; worst = 0.; encoded_pairs = []
    counters = {mode: {'frame_pairs': 0, 'raw_different_frames': 0, 'masked_different_frames': 0,
                       'outside_changed_pixels': 0, 'maximum_outside_changed_pixels_per_frame': 0}
                for mode in MODES}
    for kind, seed, original in recipes:
        sequences = {'source': original, 'hand_reflection': reflect_depth(original, object_too=False),
                     'joint_reflection': reflect_depth(original, object_too=True)}
        group = root/(kind+'_s'+str(seed)); group.mkdir(); rendered = {}; videos = {}
        for control, sequence in sequences.items():
            contact = inspect(sequence); expected = control != 'hand_reflection'
            if contact['accepted'] != expected: raise ValueError('Declared contact control mismatch')
            if not gate_clip(sequence, w3, config)['accepted']: raise ValueError('Unchanged geometry gate failed')
            out = group/control; out.mkdir()
            reference = out/'reference.private.json'
            reference.write_text(json.dumps({'frames': sequence, 'source_info': info}, allow_nan=False), encoding='utf8')
            reference_hash = digest(reference)
            cache = {mode: [] for mode in MODES}; diagnostics = []
            for i, frame in enumerate(sequence):
                passes = render(frame); mask = mask_for(frame, w3); checked += 1
                if control != 'source':
                    if not np.array_equal(draw_frame(original[i]), draw_frame(frame)):
                        raise ValueError('Wireframe control is not pixel-identical')
                    wire_equal += 1
                target_scene = np.isin(passes['owner'], TARGET_IDS)
                target_hand = np.isin(passes['hand_only_owner'], TARGET_IDS)
                diagnostics.append({'frame_idx': i, 'visible_object_pixels': int(np.sum((passes['owner'] == OBJECT_ID) & ~mask)),
                    'target_scene_pixels_outside_mask': int(np.sum(target_scene & ~mask)),
                    'target_hand_only_pixels_outside_mask': int(np.sum(target_hand & ~mask))})
                for mode in MODES: cache[mode].append(passes['images'][mode])
                if i == frames//2:
                    np.savez_compressed(out/'surface_passes.private.npz', owner=passes['owner'],
                                        depth=np.where(passes['owner'] != 0, passes['depth'], 0.), mask=mask)
                    for mode in MODES:
                        image = passes['images'][mode]; masked = image.copy(); masked[mask] = 0
                        for suffix, data in (('source', image), ('masked', masked)):
                            ok, png = cv2.imencode('.png', data)
                            if not ok: raise ValueError('Surface preview encoding failed')
                            (out/(mode+'_'+suffix+'.private.png')).write_bytes(png.tobytes())
            for mode in MODES:
                mode_out = out/mode; mode_out.mkdir(); source = mode_out/'source.private.avi'
                _video(source, cache[mode], fps, sequence); before = digest(source)
                row = {'mode': mode, 'control': control, 'contact_accepted': contact['accepted'],
                       'target_surface_outside_mask_pixels': sum(d['target_hand_only_pixels_outside_mask' if mode.endswith('hand_only') else 'target_scene_pixels_outside_mask'] for d in diagnostics),
                       'state': 'QUARANTINED_CONTACT_CONTROL', 'artifact': None, 'rendition': None, 'release_allowed': False}
                if contact['accepted'] and row['target_surface_outside_mask_pixels'] == 0:
                    row['artifact'] = build_candidate(source, sequence, info, w3, config, mode_out/'candidates')
                    parent = mode_out/'candidates'/row['artifact']['artifact_id']
                    row['rendition'] = build_h264_rendition(parent, sequence, info, w3, config, mode_out/'renditions',
                        ffmpeg=str(ffmpeg), ffprobe=str(ffprobe), outside_mae_limit=2.)
                    videos[(control, mode)] = mode_out/'renditions'/row['rendition']['output_sha256']/'video.mp4'
                    worst = max(worst, row['rendition']['raster_inspection']['max_frame_outside_mae'])
                    row['state'] = 'RESEARCH_SURFACE_PROXY_ONLY'
                elif contact['accepted']:
                    row['state'] = 'QUARANTINED_TARGET_PROXY_OUTSIDE_MASK'
                if digest(source) != before or digest(reference) != reference_hash:
                    raise ValueError('Source/reference changed during processing')
                (mode_out/'report.private.json').write_text(json.dumps(row, indent=2, allow_nan=False), encoding='utf8')
                outputs.append(row)
            rendered[control] = cache
            (out/'surface_diagnostics.private.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf8')
        for control in ('hand_reflection', 'joint_reflection'):
            for mode in MODES:
                for i, frame in enumerate(original):
                    a, b = rendered['source'][mode][i], rendered[control][mode][i]; mask = mask_for(frame, w3)
                    different = np.any(a != b, axis=-1); outside = int(np.sum(different & ~mask))
                    row = {'kind': kind, 'seed': seed, 'control': control, 'mode': mode, 'frame_idx': i,
                           'raw_changed_pixels': int(np.sum(different)), 'outside_changed_pixels': outside}
                    comparisons.append(row); counts = counters[mode]; counts['frame_pairs'] += 1
                    counts['raw_different_frames'] += int(different.any()); counts['masked_different_frames'] += int(outside > 0)
                    counts['outside_changed_pixels'] += outside
                    counts['maximum_outside_changed_pixels_per_frame'] = max(counts['maximum_outside_changed_pixels_per_frame'], outside)
                if ('source', mode) in videos and (control, mode) in videos:
                    encoded_pairs.append({'kind': kind, 'seed': seed, 'control': control, 'mode': mode,
                        'frames': frames, 'different_frames': _encoded_pair(videos[('source', mode)], videos[(control, mode)], frames)})
    (root/'frame_comparisons.private.json').write_text(json.dumps(comparisons, indent=2), encoding='utf8')
    (root/'encoded_pairs.private.json').write_text(json.dumps(encoded_pairs, indent=2), encoding='utf8')
    summary = {'scope': 'authored_surface_visibility_and_cue_diagnostics_not_efficacy', 'renderer_version': VERSION,
        'recipe_instances_n': len(recipes), 'depth_control_cases_n': len(recipes)*3, 'render_modes_n': len(MODES),
        'surface_frames_computed_n': checked, 'lossless_mode_frames_verified_n': len(outputs)*frames,
        'wire_identical_pair_frames_n': wire_equal, 'comparisons_by_mode': counters,
        'contact_quarantined_mode_cases_n': sum(not r['contact_accepted'] for r in outputs),
        'surface_quarantined_mode_cases_n': sum(r['state'] == 'QUARANTINED_TARGET_PROXY_OUTSIDE_MASK' for r in outputs),
        'h264_renditions_n': sum(r['rendition'] is not None for r in outputs),
        'h264_frames_verified_n': sum(r['rendition']['raster_inspection']['decoded_frames'] for r in outputs if r['rendition']),
        'encoded_pair_frames_n': sum(r['frames'] for r in encoded_pairs),
        'encoded_different_pair_frames_n': sum(r['different_frames'] for r in encoded_pairs),
        'maximum_visible_region_codec_mae': worst, 'release_allowed': False,
        'human_or_ai_efficacy_tested': False, 'new_model_inference': False,
        'limitations': ['authored capsules/sphere, no palm mesh/anatomy/force closure',
            'orthographic opaque nearest-surface rendering; no cast shadows or reflections',
            'flat/lit and object/hand-only controls use the same correlated geometry, not independent families',
            'target surface diagnostic covers only two middle-finger bone proxies, not all hidden anatomy',
            'nonzero pixel differences do not prove human recognizability or strong-attack failure']}
    (root/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n', encoding='utf8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'ffmpeg', 'ffprobe'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(build(args.output, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)))
