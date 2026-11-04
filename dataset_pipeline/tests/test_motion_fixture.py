import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from experiments.motion_fixture.generate import generate_motion,build_fixture,FINGERS,BOUNDS_RADIANS
from dataset_pipeline.common import LANDMARK_NAMES


class MotionFixtureTests(unittest.TestCase):
    def test_seed_is_reproducible_and_templates_move(self):
        a=generate_motion('index_flex',7,frames=12)
        self.assertEqual(a,generate_motion('index_flex',7,frames=12))
        self.assertNotEqual(a,generate_motion('index_flex',8,frames=12))
        self.assertNotEqual(a[0]['landmarks_world']['INDEX_TIP'],a[5]['landmarks_world']['INDEX_TIP'])

    def test_forward_kinematics_preserves_authored_bone_lengths(self):
        for record in generate_motion('alternating',3,frames=15):
            p=np.array([[record['landmarks_world'][name][axis] for axis in ('x','y','z')] for name in LANDMARK_NAMES])
            for base,(_location,lengths) in FINGERS.items():
                for offset,length in enumerate(lengths):
                    self.assertAlmostEqual(float(np.linalg.norm(p[base+offset+1]-p[base+offset])),length)
                angles=record['authored_joint_flex_radians'][str(base)]
                self.assertTrue(all(0<=a<=b for a,b in zip(angles,BOUNDS_RADIANS)))

    def test_invalid_recipe_is_rejected(self):
        for values in ({'template':'unknown','seed':0},{'template':'index_flex','seed':-1},
                       {'template':'index_flex','seed':0,'frames':2},
                       {'template':'index_flex','seed':0,'fps':0},
                       {'template':'index_flex','seed':0,'fps':True}):
            with self.subTest(values=values),self.assertRaises(ValueError):generate_motion(**values)

    def test_fixture_runs_through_actual_video_and_mask_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'fixture'
            report=build_fixture(target,template='middle_flex',seed=7,w3_new=2.5,frames=6)
            self.assertFalse(report['release_allowed']);self.assertFalse(report['human_feasibility_tested'])
            self.assertIsNone(report['learned_model']);self.assertIsNone(report['object_contact_model'])
            self.assertTrue((target/'authored_source.avi').is_file())
            self.assertTrue((target/'private_reference.json').is_file())
            stored=json.loads((target/'fixture_report.json').read_text(encoding='utf8'))
            self.assertEqual(stored['template_id'],'middle_flex')
            self.assertTrue(report['gate_accepted'])
            self.assertTrue((target/'candidates'/report['artifact']['media_file']).is_file())
            with self.assertRaises(FileExistsError):
                build_fixture(target,template='middle_flex',seed=7,w3_new=2.5,frames=6)

    def test_invalid_mask_multiplier_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'fixture'
            for value in (True,0,-1,float('nan'),float('inf')):
                with self.subTest(value=value),self.assertRaises(ValueError):
                    build_fixture(target,template='middle_flex',seed=7,w3_new=value)
                self.assertFalse(target.exists())
