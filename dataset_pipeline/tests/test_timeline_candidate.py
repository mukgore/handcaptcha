"""Decode real synthetic videos; no camera, participant or network data."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from dataset_pipeline.candidate import build_candidate
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.pipeline import run_batch
from dataset_pipeline.timeline import build_frame_map
from dataset_pipeline.tests.test_stage7_v2 import pose, record


class TimelineTests(unittest.TestCase):
    def frames(self):
        return [dict(frame_idx=i, source_pts_ms=i * 100.) for i in (0, 2, 1, 0)]

    def test_filter_and_reverse_map_source_indices_without_compressing_time(self):
        frames = self.frames()
        before = copy.deepcopy(frames)
        mapping = build_frame_map(frames, {'fps': 10.})
        self.assertEqual([r['source_frame_idx'] for r in mapping['frames']], [0, 2, 1, 0])
        self.assertEqual([r['source_pts_ms'] for r in mapping['frames']], [0., 200., 100., 0.])
        self.assertEqual([r['output_pts_ms'] for r in mapping['frames']], [0., 100., 200., 300.])
        self.assertEqual(before, frames)

    def test_missing_or_conflicting_source_metadata_is_rejected(self):
        for bad in ([{'frame_idx': 0}], [{'frame_idx': -1, 'source_pts_ms': 0}],
                    [{'frame_idx': True, 'source_pts_ms': 0}],
                    [{'frame_idx': 0, 'source_pts_ms': 1}, {'frame_idx': 0, 'source_pts_ms': 2}],
                    [{'frame_idx': 0, 'source_pts_ms': 20}, {'frame_idx': 1, 'source_pts_ms': 10}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_frame_map(bad, {'fps': 10.})

    def test_duplicate_source_landmarks_cannot_change_during_reverse(self):
        a = dict(frame_idx=0, source_pts_ms=0., landmarks_px={'x': 1})
        b = dict(a, landmarks_px={'x': 2})
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            build_frame_map([a, b], {'fps': 10.})

    def test_empty_or_invalid_fps_is_rejected(self):
        for frames, fps in (([], 10.), (self.frames(), 0.), (self.frames(), float('nan'))):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                build_frame_map(frames, {'fps': fps})


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.mp4'
        self.output = self.root / 'private_candidates'
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*'mp4v'), 10., (480, 320))
        self.assertTrue(writer.isOpened())
        try:
            for value in (40, 120, 220):
                writer.write(np.full((320, 480, 3), value, np.uint8))
        finally:
            writer.release()
        self.info = {'width': 480, 'height': 320, 'fps': 10., 'total_frames': 3}
        self.frames = []
        capture = cv2.VideoCapture(str(self.source))
        try:
            for i in range(3):
                self.assertTrue(capture.read()[0])
                points = [(x + 160. + 80 * i, y + 110., z) for x, y, z in pose(2)]
                frame = record(i, points)
                frame['source_pts_ms'] = capture.get(cv2.CAP_PROP_POS_MSEC)
                self.frames.append(frame)
        finally:
            capture.release()
        self.config = PipelineConfig()

    def build(self, frames=None, info=None):
        return build_candidate(self.source, self.frames if frames is None else frames,
                               self.info if info is None else info, 1.95, self.config, self.output)

    def test_actual_video_and_masks_follow_filtered_reverse_mapping(self):
        selected = [self.frames[2], self.frames[0], self.frames[2]]
        before = copy.deepcopy(selected)
        artifact = self.build(selected)
        manifest = json.loads((self.output / artifact['manifest_file']).read_text(encoding='utf8'))
        video = self.output / artifact['media_file']
        self.assertEqual(manifest['output_sha256'], hashlib.sha256(video.read_bytes()).hexdigest())
        self.assertEqual([r['source_frame_idx'] for r in manifest['timeline']['frames']], [2, 0, 2])
        self.assertFalse(manifest['release_allowed'])
        self.assertEqual(manifest['rights_status'], 'UNREVIEWED')
        self.assertEqual(selected, before)
        self.assertFalse(list(self.output.glob('.building-*')))
        self.assertEqual(sorted(p.name for p in video.parent.iterdir()), ['artifact.json', 'masked.mp4'])
        capture = cv2.VideoCapture(str(video))
        try:
            images = []
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                images.append(image)
            self.assertEqual(len(images), 3)
            self.assertGreater(int(images[0][20, 20].mean()), 190)  # source 2
            self.assertLess(int(images[1][20, 20].mean()), 60)  # source 0
            self.assertGreater(int(images[0][160, 80].mean()), 190)  # outside source-2 mask
            self.assertLess(int(images[1][160, 80].max()), 30)  # inside source-0 mask
        finally:
            capture.release()

    def test_mismatched_time_and_frame_count_never_publish_candidate(self):
        bad = copy.deepcopy(self.frames)
        bad[1]['source_pts_ms'] += 1.
        for frames, info in ((bad, self.info), (self.frames, dict(self.info, total_frames=4))):
            with self.subTest(info=info), self.assertRaises(ValueError):
                self.build(frames, info)
        self.assertFalse(self.output.exists())

    def test_existing_candidate_is_not_overwritten(self):
        artifact = self.build()
        manifest = self.output / artifact['manifest_file']
        before = manifest.read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(before, manifest.read_bytes())

    def test_gate_failure_and_cache_budget_never_publish_candidate(self):
        bad = copy.deepcopy(self.frames)
        bad[0]['detected'] = False
        with self.assertRaisesRegex(ValueError, 'Stage7'):
            self.build(bad)
        with self.assertRaisesRegex(ValueError, 'budget'):
            build_candidate(self.source, self.frames, self.info, 1.95, self.config, self.output, max_cache_bytes=1)
        with self.assertRaisesRegex(ValueError, 'budget'):
            build_candidate(self.source, self.frames, self.info, 1.95, self.config, self.output, max_output_frames=1)
        self.assertFalse(self.output.exists())

    def test_batch_outputs_verified_artifact_and_separate_geometry_scope(self):
        report = {'clip_id': self.source.name, 'video_info': self.info, 'final_status': 'passed_stage1_4'}
        with patch('dataset_pipeline.pipeline.process_clip', return_value=(report, self.frames)):
            result = run_batch([str(self.source)], w3_new=1.95, output_dir=str(self.output), render_candidates=True)
        self.assertEqual(result['manifest'], ['source.mp4'])
        self.assertEqual(result['manifest_scope'], 'research_artifacts')
        self.assertEqual(result['clip_reports'][0]['final_status'], 'artifact_verified_research')
        self.assertEqual(len(result['artifacts']), 1)
        stored = json.loads((self.output / 'manifest.json').read_text(encoding='utf8'))
        self.assertFalse(stored['release_allowed'])

    def test_batch_render_failure_is_quarantined_and_excluded_from_manifest(self):
        report = {'clip_id': self.source.name, 'video_info': self.info, 'final_status': 'passed_stage1_4'}
        with patch('dataset_pipeline.pipeline.process_clip', return_value=(report, self.frames)), \
             patch('dataset_pipeline.pipeline.build_candidate', side_effect=ValueError('synthetic render fault')):
            result = run_batch([str(self.source)], w3_new=1.95, output_dir=str(self.output), render_candidates=True)
        self.assertEqual(result['manifest'], [])
        self.assertEqual(result['artifacts'], [])
        self.assertEqual(result['clip_reports'][0]['final_status'], 'quarantined_render')

    def test_batch_rejects_ambiguous_names_or_missing_output_before_extraction(self):
        for paths, output in ((['a/x.mp4', 'b/x.mp4'], str(self.output)), (['x.mp4'], None)):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                run_batch(paths, output_dir=output, render_candidates=True)


if __name__ == '__main__':
    unittest.main()
