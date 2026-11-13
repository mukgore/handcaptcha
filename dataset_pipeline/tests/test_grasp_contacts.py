import copy
import unittest
import numpy as np

from experiments.motion_fixture.grasp_contacts import KINDS,records,reflect_depth,inspect
from experiments.motion_fixture.generate import draw_frame
from experiments.motion_fixture.grasp_counterexamples import masked_image
from experiments.motion_fixture.mask_feasibility import inspect as feasibility
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage7_gate import gate_clip


class GraspContactTests(unittest.TestCase):
    def test_both_topologies_hold_then_release_without_proxy_penetration(self):
        for kind,expected in zip(KINDS,(2,3)):
            for seed in (7,19):
                with self.subTest(kind=kind,seed=seed):
                    report=inspect(records(kind,seed))
                    self.assertTrue(report['accepted']);self.assertEqual(report['contact_tips_n'],expected)
                    self.assertEqual(report['penetrating_frames'],[])
                    self.assertGreater(report['all_tip_contact_frames'][0],0)
                    self.assertLess(report['all_tip_contact_frames'][-1],23)
                    self.assertGreater(report['object_displacement'],.07)

    def test_fixed_object_rejects_reflected_hand_but_joint_reflection_is_ambiguous(self):
        for kind in KINDS:
            frames=records(kind,7);before=copy.deepcopy(frames)
            wrong=reflect_depth(frames,object_too=False);ambiguous=reflect_depth(frames,object_too=True)
            self.assertTrue(inspect(frames)['accepted']);self.assertFalse(inspect(wrong)['accepted'])
            self.assertTrue(inspect(ambiguous)['accepted'])
            self.assertEqual(frames,before)
            for source,a,b in zip(frames,wrong,ambiguous):
                np.testing.assert_array_equal(draw_frame(source),draw_frame(a))
                np.testing.assert_array_equal(draw_frame(source),draw_frame(b))
                np.testing.assert_array_equal(masked_image(source,2.5),masked_image(a,2.5))
                np.testing.assert_array_equal(masked_image(source,2.5),masked_image(b,2.5))
                self.assertNotEqual(source['landmarks_world'],b['landmarks_world'])

    def test_recipe_reproducibility_and_seed_variation_are_not_extra_families(self):
        for kind in KINDS:
            self.assertEqual(records(kind,7),records(kind,7))
            self.assertNotEqual(records(kind,7),records(kind,19))

    def test_same_mask_can_cover_all_authored_recipes_without_changing_gate(self):
        frames=[f for seed in (7,19) for kind in KINDS for f in records(kind,seed)]
        result=feasibility(frames,PipelineConfig());self.assertTrue(result['feasible'])
        self.assertTrue(gate_clip(frames,result['proposed_w3'],PipelineConfig())['accepted'])

    def test_modified_lengths_time_order_and_radius_are_rejected(self):
        for change in ('bone','time','radius','index'):
            frames=records(KINDS[0],7)
            if change=='bone':frames[1]['landmarks_world']['THUMB_TIP']['x']+=.1
            if change=='time':frames[1]['source_pts_ms']=0
            if change=='radius':frames[1]['authored_object']['radius']+=.1
            if change=='index':frames[0]['frame_idx']=False
            with self.subTest(change=change),self.assertRaises(ValueError):inspect(frames)

    def test_invalid_recipes_do_not_generate_coordinates(self):
        for kwargs in ({'kind':'unknown','seed':7},{'kind':KINDS[0],'seed':True},
                       {'kind':KINDS[0],'seed':7,'frames':3},{'kind':KINDS[0],'seed':7,'fps':float('nan')}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):records(**kwargs)


if __name__=='__main__':unittest.main()
