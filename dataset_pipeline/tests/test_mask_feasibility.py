import unittest

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage7_gate import gate_clip
from experiments.motion_fixture.mask_feasibility import inspect
from test_stage7_v2 import pose, record


class MaskFeasibilityTests(unittest.TestCase):
    def test_analytic_midpoint_satisfies_actual_unchanged_gate(self):
        frames=[record(i,pose(2)) for i in range(3)]
        result=inspect(frames,PipelineConfig())
        self.assertTrue(result['feasible']);self.assertEqual(result['frames'],3)
        self.assertTrue(gate_clip(frames,result['proposed_w3'],PipelineConfig())['accepted'])

    def test_incompatible_coverage_and_visibility_have_no_proposal(self):
        result=inspect([record(0,pose(0))],PipelineConfig())
        self.assertFalse(result['feasible']);self.assertIsNone(result['proposed_w3'])
        self.assertGreater(result['minimum_w3'],result['maximum_w3'])

    def test_all_frames_are_required_even_when_some_individual_frames_are_feasible(self):
        result=inspect([record(0,pose(2)),record(1,pose(0))],PipelineConfig())
        self.assertFalse(result['feasible']);self.assertEqual(len(result['frame_intervals']),2)

    def test_translation_and_scale_do_not_fit_a_new_parameter(self):
        a=inspect([record(0,pose(2))],PipelineConfig())
        moved=[(x*3+200,y*3+30,z) for x,y,z in pose(2)]
        b=inspect([record(0,moved)],PipelineConfig())
        self.assertAlmostEqual(a['minimum_w3'],b['minimum_w3'])
        self.assertAlmostEqual(a['maximum_w3'],b['maximum_w3'])

    def test_empty_missing_and_degenerate_input_rejected(self):
        for frames in ([],[{'frame_idx':0,'detected':False}],[record(0,[(0,0,0)]*21)]):
            with self.assertRaises(ValueError):inspect(frames,PipelineConfig())
