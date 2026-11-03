"""Versioned gate regressions; synthetic geometry, no human performance claim."""
import math
import os
import tempfile
import unittest
from dataclasses import replace

import cv2
import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES, VISIBLE_FINGER_TIPS
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage6_occlusion import project_occlusion_circle, generate_occluded_video
from dataset_pipeline.stage7_gate import check_frame_conditions, gate_clip, GATE_POLICY_VERSION


def pose(visible=4):
    points = [(0., 50., 0.) for _ in range(21)]
    points[0], points[9] = (0., 0., 0.), (0., 100., 0.)
    points[10], points[11] = (0., 120., 0.), (0., 130., 0.)
    locations = [(-120., 50., 0.), (-70., 160., 0.), (70., 160., 0.), (120., 70., 0.)]
    for index, location in list(zip(VISIBLE_FINGER_TIPS.values(), locations))[:visible]:
        points[index] = location
    return points


def record(index, points=None):
    points = points if points is not None else pose()
    return {"frame_idx": index, "detected": True,
            "landmarks_px": {name: dict(zip(('x', 'y', 'z'), p))
                             for name, p in zip(LANDMARK_NAMES, points)}}


class Stage7V2Tests(unittest.TestCase):
    def check(self, points, config=None):
        center, radius = project_occlusion_circle(points, 1.95)
        return check_frame_conditions(points, center, radius, config or PipelineConfig())

    def test_midpoint_mask_can_pass_with_covered_wrist_and_palm(self):
        points = pose(2)
        center, radius = project_occlusion_circle(points, 1.95)
        self.assertEqual(center, (0., 50.))
        self.assertEqual(radius, 97.5)
        self.assertLess(math.dist(points[0][:2], center), radius)
        accepted, detail = self.check(points)
        self.assertTrue(accepted)
        self.assertEqual(detail['visible_fingers'], ['thumb', 'index'])
        self.assertEqual(detail['policy_version'], GATE_POLICY_VERSION)

    def test_middle_joint_still_must_be_covered(self):
        points = pose()
        points[10] = (0., 300., 0.)
        accepted, detail = self.check(points)
        self.assertFalse(accepted)
        self.assertTrue(detail['condition2'])
        self.assertEqual(detail['reason'], 'middle_joint_not_covered')

    def test_zero_or_one_visible_finger_is_rejected(self):
        for count in (0, 1):
            with self.subTest(count=count):
                accepted, detail = self.check(pose(count))
                self.assertFalse(accepted)
                self.assertTrue(detail['condition1'])
                self.assertEqual(detail['reason'], 'insufficient_visible_fingers')

    def test_middle_tip_does_not_count_as_non_target_cue(self):
        points = pose(1)
        points[12] = (1000., 50., 0.)
        accepted, detail = self.check(points)
        self.assertFalse(accepted)
        self.assertEqual(detail['visible_finger_count'], 1)

    def test_expanded_margin_and_configured_minimum_are_applied(self):
        points = pose(2)
        points[8] = (100., 50., 0.)  # outside r=97.5, inside r*1.1
        self.assertFalse(self.check(points)[0])
        self.assertTrue(self.check(points, replace(PipelineConfig(), condition2_margin_frac=0))[0])
        self.assertFalse(self.check(pose(2), replace(PipelineConfig(), condition2_min_visible_fingers=3))[0])

    def test_image_depth_does_not_change_2d_gate(self):
        a = pose()
        b = [(x, y, 1e9 * (i + 1)) for i, (x, y, _) in enumerate(a)]
        self.assertEqual(self.check(a), self.check(b))

    def test_invalid_geometry_fails_closed(self):
        for points in (pose()[:20], [()] * 21, [(math.nan, 0., 0.)] * 21):
            with self.subTest(points=points):
                self.assertFalse(check_frame_conditions(points, (0., 50.), 97.5, PipelineConfig())[0])

    def test_missing_and_malformed_frames_remain_in_denominator(self):
        frames = [record(0), {'frame_idx': 1, 'detected': False},
                  {'frame_idx': 2, 'detected': True, 'landmarks_px': {}}]
        result = gate_clip(frames, 1.95, PipelineConfig())
        self.assertFalse(result['accepted'])
        self.assertEqual(result['total_checked'], 3)
        self.assertAlmostEqual(result['pass_frac'], 1 / 3)
        self.assertEqual(result['failing_frame_idxs'], [1, 2])

    def test_empty_clip_never_passes(self):
        self.assertFalse(gate_clip([], 1.95, PipelineConfig())['accepted'])

    def test_accepted_geometry_matches_unchanged_stage6_encoded_mask(self):
        points = [(x + 160., y + 110., z) for x, y, z in pose(2)]
        frames = [record(i, points) for i in range(3)]
        self.assertTrue(gate_clip(frames, 1.95, PipelineConfig())['accepted'])
        with tempfile.TemporaryDirectory() as directory:
            source, output = [os.path.join(directory, name) for name in ('source.mp4', 'masked.mp4')]
            writer = cv2.VideoWriter(source, cv2.VideoWriter_fourcc(*'mp4v'), 10., (320, 320))
            self.assertTrue(writer.isOpened())
            try:
                for _ in frames:
                    writer.write(np.full((320, 320, 3), 255, np.uint8))
            finally:
                writer.release()
            generate_occluded_video(source, frames, {'width': 320, 'height': 320, 'fps': 10.}, 1.95, output)
            capture = cv2.VideoCapture(output)
            try:
                count = 0
                while True:
                    ok, image = capture.read()
                    if not ok:
                        break
                    self.assertLess(int(image[230, 160].max()), 30)  # middle PIP covered
                    self.assertLess(int(image[110, 160].max()), 30)  # wrist covered, allowed
                    self.assertGreater(int(image[160, 40].min()), 220)  # thumb remains outside
                    count += 1
                self.assertEqual(count, 3)
            finally:
                capture.release()

    def test_invalid_policy_configuration_is_rejected(self):
        for changes in ({'condition2_min_visible_fingers': 0},
                        {'condition2_min_visible_fingers': True},
                        {'condition2_min_visible_fingers': 5},
                        {'condition1_margin_frac': 1},
                        {'condition2_margin_frac': -1}, {'gate_pass_frac': 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(pose(), replace(PipelineConfig(), **changes))


if __name__ == '__main__':
    unittest.main()
