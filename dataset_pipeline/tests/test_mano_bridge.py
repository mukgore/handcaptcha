import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dataset_pipeline.release_registry import digest
from experiments.motion_fixture.accept_mano_pilot import run
from test_stage7_v2 import pose, record


class ManoBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.pilot=self.root/'pilot';self.pilot.mkdir();self.output=self.root/'output'
        (self.pilot/'authored_source.avi').write_bytes(b'synthetic-not-video')
        (self.pilot/'private_surface.npz').write_bytes(b'synthetic-not-model')
        frames=[record(i,pose(0)) for i in range(3)]
        (self.pilot/'private_reference.json').write_text(json.dumps({'frames':frames,'source_info':{'total_frames':3}}))
        report=dict(state='RESEARCH_MANO_PCA_PILOT',release_allowed=False,hand='right',component=0,frames=3,
                    source_video_sha256=digest(self.pilot/'authored_source.avi'),
                    surface_sha256=digest(self.pilot/'private_surface.npz'),reference_sha256=digest(self.pilot/'private_reference.json'))
        (self.pilot/'mano_report.json').write_text(json.dumps(report))

    def test_quarantine_keeps_failed_geometry_without_calling_encoder(self):
        with patch('experiments.motion_fixture.accept_mano_pilot.build_candidate') as encoder:
            result=run(self.pilot,self.output,w3=2.5)
        encoder.assert_not_called();self.assertEqual(result['state'],'QUARANTINED_GEOMETRY')
        self.assertEqual(len(result['gate_diagnostics']),3);self.assertIsNone(result['artifact'])

    def test_tampered_reference_is_rejected_before_output_creation(self):
        (self.pilot/'private_reference.json').write_text('{}')
        with self.assertRaises(ValueError):run(self.pilot,self.output,w3=2.5)
        self.assertFalse(self.output.exists())

    def test_invalid_mask_parameter_is_not_a_quarantined_success(self):
        for value in (True,0,float('nan')):
            with self.assertRaises(ValueError):run(self.pilot,self.output,w3=value)
        self.assertFalse(self.output.exists())

    def test_video_and_surface_drift_during_render_prevent_completion_report(self):
        for name in ('authored_source.avi','private_surface.npz'):
            with self.subTest(name=name):
                original=(self.pilot/name).read_bytes()
                output=self.root/(name+'.output')
                def mutate(*args,**kwargs):
                    (self.pilot/name).write_bytes(b'changed-during-render')
                    return {'state':'synthetic-mocked-candidate'}
                with patch('experiments.motion_fixture.accept_mano_pilot.gate_clip',return_value={'accepted':True,'pass_frac':1,'frame_diagnostics':[]}),patch('experiments.motion_fixture.accept_mano_pilot.build_candidate',side_effect=mutate):
                    with self.assertRaisesRegex(ValueError,'changed during'):run(self.pilot,output,w3=2.5)
                self.assertFalse((output/'mask_report.json').exists())
                (self.pilot/name).write_bytes(original)

    def test_string_proposal_origin_is_not_accepted_as_a_boolean(self):
        with self.assertRaises(ValueError):run(self.pilot,self.output,w3=2.5,feasibility_proposal='false')
        self.assertFalse(self.output.exists())
