import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES
from dataset_pipeline.release_registry import digest
from experiments.motion_fixture.mano_reference_audit import audit,named_tip_ids,projection,TIP_NAMES,TIP_COLUMNS


class ManoReferenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.ids=dict(zip(TIP_NAMES,(10,20,30,40,50)))
        self.points=np.zeros((3,21,3),np.float32)
        for i,base in enumerate((1,5,9,13,17)):
            self.points[:,base]=[(i-2)*.2,1.,0.]
            for j,length in enumerate((.2,.15,.1),1):self.points[:,base+j]=self.points[:,base+j-1]+[0.,length,0.]
        self.vertices=np.random.default_rng(7).uniform(-1,1,(3,778,3)).astype(np.float32)
        self.vertices[:,list(self.ids.values())]=self.points[:,TIP_COLUMNS]
        self.faces=np.tile([0,1,2],(1538,1)).astype(np.int32);self.pose=np.zeros((3,6),np.float32)
        (self.root/'authored_source.avi').write_bytes(b'synthetic binding bytes, not decoded video')
        self.write()

    def write(self):
        np.savez_compressed(self.root/'private_surface.npz',vertices=self.vertices,joints=self.points,faces=self.faces,pose=self.pose)
        xy=projection(self.vertices,self.points)
        frames=[{'frame_idx':i,'source_pts_ms':i*1000/12,'authored_handedness':'right',
                 'landmarks_world':{n:dict(zip(('x','y','z'),p.tolist())) for n,p in zip(LANDMARK_NAMES,self.points[i])},
                 'landmarks_px':{n:{'x':float(v[0]),'y':float(v[1]),'z':float(p[2])} for n,v,p in zip(LANDMARK_NAMES,xy[i],self.points[i])}} for i in range(3)]
        (self.root/'private_reference.json').write_text(json.dumps({'frames':frames,'source_info':{'total_frames':3,'width':512,'height':420}}))
        self.bind()

    def bind(self):
        report={'state':'RESEARCH_MANO_PCA_PILOT','release_allowed':False,'frames':3,'hand':'right','component':0,
                'source_video_sha256':digest(self.root/'authored_source.avi'),
                'reference_sha256':digest(self.root/'private_reference.json'),'surface_sha256':digest(self.root/'private_surface.npz')}
        (self.root/'mano_report.json').write_text(json.dumps(report))

    def mutate_reference(self,change):
        p=self.root/'private_reference.json';v=json.loads(p.read_text());change(v);p.write_text(json.dumps(v));self.bind()

    def test_saved_references_and_named_tips_match_without_anatomy_or_si_claim(self):
        result=audit(self.root,self.ids)
        self.assertTrue(result['tip_mapping_all_five_match']);self.assertEqual(result['named_tips_match_all_frames_n'],5)
        self.assertEqual(result['measurable_feature_frames_n'],3)
        self.assertFalse(result['physical_unit_verified']);self.assertEqual(result['length_unit'],'model_native_units')
        self.assertFalse(result['biological_validity_proven']);self.assertFalse(result['full_generator_ready'])

    def test_tip_label_permutation_is_quarantined_without_silent_repair(self):
        self.points[:,[4,8]]=self.points[:,[8,4]];self.write()
        before=(self.root/'private_reference.json').read_bytes();result=audit(self.root,self.ids)
        self.assertEqual(result['named_tips_match_all_frames_n'],3)
        self.assertEqual(result['state'],'QUARANTINED_REFERENCE_CONSISTENCY')
        self.assertEqual(result['measurable_feature_frames_n'],0)
        self.assertEqual(before,(self.root/'private_reference.json').read_bytes())

    def test_projection_error_is_quarantined_even_if_points_and_hashes_are_consistent(self):
        self.mutate_reference(lambda v:v['frames'][1]['landmarks_px']['WRIST'].__setitem__('x',999.))
        result=audit(self.root,self.ids);self.assertFalse(result['projection_matches_declared_framing'])
        self.assertEqual(result['state'],'QUARANTINED_REFERENCE_CONSISTENCY')

    def test_independent_axis_aligned_projection_has_expected_pixel_mapping(self):
        v=np.zeros((3,778,3));v[:,0]=[-1,-1,-1];v[:,1]=[1,1,1]
        p=np.zeros((3,21,3));p[:,9]=[0,1,0];p[:,5]=[-.5,.8,0];p[:,17]=[.5,.8,0]
        result=projection(v,p)
        np.testing.assert_allclose(result[:,:,0],256+175*p[:,:,0],atol=1e-12)
        np.testing.assert_allclose(result[:,:,1],210-175*p[:,:,1],atol=1e-12)

    def test_reference_native_array_mismatch_and_hand_label_conflict_are_rejected(self):
        self.mutate_reference(lambda v:v['frames'][1]['landmarks_world']['WRIST'].__setitem__('x',.3))
        with self.assertRaisesRegex(ValueError,'native joints'):audit(self.root,self.ids)
        self.write();self.mutate_reference(lambda v:v['frames'][1].__setitem__('authored_handedness','left'))
        with self.assertRaisesRegex(ValueError,'hand labels'):audit(self.root,self.ids)

    def test_changed_bound_file_and_malformed_saved_topology_are_rejected(self):
        (self.root/'private_surface.npz').write_bytes(b'changed')
        with self.assertRaises(ValueError):audit(self.root,self.ids)
        self.write();self.faces[0,0]=778;self.write()
        with self.assertRaisesRegex(ValueError,'face indices'):audit(self.root,self.ids)

    def test_named_tip_source_is_parsed_without_executing_imports_or_calls(self):
        path=self.root/'vertex_ids.py';path.write_text('raise RuntimeError("must never execute")\nvertex_ids='+repr({'mano':self.ids}))
        self.assertEqual(named_tip_ids(path),self.ids)
        path.write_text('vertex_ids=make_ids()')
        with self.assertRaises((ValueError,TypeError)):named_tip_ids(path)
        path.write_text('vertex_ids='+repr({'mano':dict(self.ids,thumb=True)}))
        with self.assertRaises(ValueError):named_tip_ids(path)


if __name__=='__main__':unittest.main()
