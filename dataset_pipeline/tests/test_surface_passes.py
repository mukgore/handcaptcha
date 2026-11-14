import copy
import math
import unittest

import numpy as np

from experiments.motion_fixture.surface_passes import (Surface, capsule_surface, sphere_surface,
    render, MODES, OBJECT_ID, TARGET_IDS)
from experiments.motion_fixture.grasp_contacts import KINDS, records, reflect_depth
from experiments.motion_fixture.contact import segment_distance
from experiments.motion_fixture.generate import draw_frame
from experiments.motion_fixture.depth_cue_audit import mask_for


class SurfacePassTests(unittest.TestCase):
    def test_sphere_front_depth_normal_and_background(self):
        x, y = np.array([[0., .3]]), np.zeros((1, 2))
        z, n = sphere_surface(x, y, [0, 0, .4], .2)
        self.assertAlmostEqual(z[0, 0], .6)
        np.testing.assert_allclose(n[0, 0], [0, 0, 1])
        self.assertEqual(z[0, 1], -np.inf); np.testing.assert_equal(n[0, 1], 0)

    def test_tilted_capsule_front_matches_independent_surface_distance(self):
        a, b = np.array([-.3, 0., 0.]), np.array([.3, 0., .4]); r = .1
        z, n = capsule_surface(np.zeros((1, 1)), np.zeros((1, 1)), a, b, r)
        expected = .2+r*math.sqrt(1+(.4/.6)**2)
        self.assertAlmostEqual(z[0, 0], expected)
        self.assertAlmostEqual(segment_distance([0, 0, z[0, 0]], a, b), r)
        self.assertAlmostEqual(float(np.linalg.norm(n[0, 0])), 1.)
        self.assertGreater(segment_distance([0, 0, z[0, 0]+.01], a, b), r)

    def test_axis_parallel_to_camera_uses_front_endpoint_cap(self):
        z, n = capsule_surface(np.zeros((1, 1)), np.zeros((1, 1)), [0, 0, -.5], [0, 0, .5], .1)
        self.assertAlmostEqual(z[0, 0], .6); np.testing.assert_allclose(n[0, 0], [0, 0, 1])

    def test_nearest_surface_wins_independent_of_insertion_order(self):
        for reverse in (False, True):
            surface = Surface(); items = [([0, 0, -.3], 1), ([0, 0, .3], OBJECT_ID)]
            if reverse: items.reverse()
            for center, identifier in items: surface.add([center], .1, identifier)
            self.assertEqual(surface.owner[220, 256], OBJECT_ID)
            self.assertAlmostEqual(surface.depth[220, 256], .4)

    def test_depth_reflection_can_change_surface_cues_while_wire_stays_equal(self):
        # Flat hand-only removes object visibility AND directional-light cues.
        for kind in KINDS:
            source = records(kind, 7)[12]
            reflected = reflect_depth([source], object_too=True)[0]
            np.testing.assert_array_equal(draw_frame(source), draw_frame(reflected))
            a, b = render(source), render(reflected)
            np.testing.assert_array_equal(a['images']['flat_hand_only'], b['images']['flat_hand_only'])
            self.assertFalse(np.array_equal(a['images']['lit_hand_only'], b['images']['lit_hand_only']))
            self.assertEqual(set(a['images']), set(MODES))
            visible = a['owner'] != 0
            self.assertTrue(np.isfinite(a['depth'][visible]).all())
            np.testing.assert_allclose(np.linalg.norm(a['normals'][visible], axis=1), 1., atol=1e-9)
            self.assertEqual(len(TARGET_IDS), 2)

    def test_mask_is_binary_opaque_and_changes_no_pixel_outside_disk(self):
        frame = records(KINDS[0], 7)[12]; image = render(frame)['images']['lit_object']
        mask = mask_for(frame, 2.5); result = image.copy(); result[mask] = 0
        np.testing.assert_array_equal(result[~mask], image[~mask]); self.assertEqual(result[mask].max(), 0)
        self.assertTrue(mask.any()); self.assertFalse(mask.all())

    def test_mismatched_or_nonfinite_geometry_and_projection_are_rejected(self):
        for change in ('world', 'projection', 'depth_projection', 'radius', 'object_kind'):
            frame = copy.deepcopy(records(KINDS[0], 7)[12])
            if change == 'world': frame['landmarks_world']['WRIST']['z'] = float('nan')
            if change == 'projection': frame['landmarks_px']['WRIST']['x'] += 1
            if change == 'depth_projection': frame['landmarks_px']['WRIST']['z'] += .1
            if change == 'radius': frame['authored_object']['radius'] = -1
            if change == 'object_kind': frame['authored_object']['kind'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(ValueError): render(frame)


if __name__ == '__main__': unittest.main()
