import copy
import math
import unittest

from experiments.motion_fixture.contact import generate_touch, inspect, points, segment_distance


class ContactFixtureTests(unittest.TestCase):
    def test_all_frames_contact_and_constant_bones_for_multiple_parameters(self):
        for seed in (0, 7, 18):
            for count in (23, 24):
                records, sphere, report = generate_touch(seed, count)
                self.assertTrue(report['accepted'], report)
                self.assertEqual(report['checked_frames'], count)
                self.assertEqual(report['penetrating_frames'], [])
                self.assertTrue(report['contact_frames'])
                self.assertEqual(records[0]['authored_object'], records[-1]['authored_object'])
                self.assertFalse(report['release_allowed'])

    def test_actual_penetration_rejected(self):
        records, sphere, report = generate_touch(7)
        sphere = copy.deepcopy(sphere)
        sphere['center'] = points(records[report['contact_frames'][0]])[12].tolist()
        result = inspect(records, sphere)
        self.assertFalse(result['accepted']); self.assertTrue(result['penetrating_frames'])

    def test_no_contact_is_not_success(self):
        records, sphere, _ = generate_touch(7)
        sphere = {**sphere, 'center': [10., 10., 10.]}
        result = inspect(records, sphere)
        self.assertFalse(result['accepted']); self.assertEqual(result['contact_frames'], [])

    def test_missing_frame_and_bone_change_rejected(self):
        records, sphere, _ = generate_touch(7)
        with self.assertRaises(ValueError): inspect(records[:4] + records[5:], sphere)
        records[3]['landmarks_world']['MIDDLE_TIP']['z'] += .1
        with self.assertRaises(ValueError): inspect(records, sphere)

    def test_invalid_geometry_rejected_and_segment_projection_is_clamped(self):
        self.assertAlmostEqual(segment_distance([2, 0, 0], [0, 0, 0], [1, 0, 0]), 1)
        for point in ([math.nan, 0, 0], [0, 0]):
            with self.assertRaises(ValueError): segment_distance(point, [0, 0, 0], [1, 0, 0])
        with self.assertRaises(ValueError): segment_distance([0, 0, 0], [1, 0, 0], [1, 0, 0])
