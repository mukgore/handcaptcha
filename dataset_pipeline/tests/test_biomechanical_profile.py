import copy
import math
import unittest

import numpy as np

from experiments.motion_fixture.biomechanical_features import (BASES,GeometryError,extract,
    signed_angles,rotation,angular_derivatives,JOINT_LABELS,ANGLE_CHILD_LABELS,ANGLE_RECORDS)
from experiments.motion_fixture.biomechanical_profile import pending_profile,validate,assess,polygon,hull_distance
from experiments.motion_fixture.grasp_contacts import KINDS,records
from dataset_pipeline.common import LANDMARK_NAMES


def synthetic_hand(flexion=0.):
    p=np.zeros((21,3))
    for i,base in enumerate(BASES):
        p[base]=[(i-2)*.2,1.,0.];direction=p[base]/np.linalg.norm(p[base])
        if i==4:direction=math.cos(flexion)*direction+math.sin(flexion)*np.array([0.,0.,-1.])
        for j,length in enumerate((.2,.15,.1),1):p[base+j]=p[base+j-1]+length*direction
    return p


def synthetic_profile():
    profile=pending_profile();profile['mapping_status']='synthetic_test'
    lengths=extract(synthetic_hand(),handedness='right')['bone_lengths']
    values={'bone_lengths':np.column_stack((lengths*.8,lengths*1.2)).tolist(),
        'palm_curvatures':[[-2.,2.]]*4,'palm_spread_radians':[[0.,math.pi]]*4,
        'joint_angle_hulls':[[[-math.pi,-math.pi/2],[math.pi,-math.pi/2],[math.pi,math.pi/2],[-math.pi,math.pi/2]] for _ in range(15)],
        'angular_speed_rad_s':np.full((15,2),10.).tolist(),
        'angular_acceleration_rad_s2':np.full((15,2),100.).tolist()}
    for name,value in values.items():profile['rules'][name]={'status':'synthetic_test','values':value,'evidence':{'scope':'synthetic test limits, not anatomy'}}
    return profile


class BiomechanicalProfileTests(unittest.TestCase):
    def test_angle_center_and_bone_child_are_distinct_and_indexed(self):
        records=extract(synthetic_hand(),handedness='right')['joint_angle_records']
        self.assertEqual(len(records),15)
        self.assertEqual([r['angle_index'] for r in records],list(range(15)))
        self.assertEqual(JOINT_LABELS[3:6],('INDEX_MCP','INDEX_PIP','INDEX_DIP'))
        self.assertEqual(ANGLE_CHILD_LABELS[3:6],('INDEX_PIP','INDEX_DIP','INDEX_TIP'))
        self.assertEqual([records[i]['candidate_clinical_joint'] for i in (0,3,4,5)],['TMC','MCP','PIP','DIP'])
        self.assertEqual(records[3]['incoming_bone_parent_point'],'WRIST')
        self.assertEqual(records[4]['incoming_bone_parent_point'],'INDEX_MCP')
        self.assertTrue(all(not r['clinical_axes_neutral_and_sign_verified'] for r in records))
        records[0]['canonical_center_point']='modified returned metadata'
        self.assertEqual(ANGLE_RECORDS[0]['canonical_center_point'],'THUMB_CMC')

    def test_known_pinky_mcp_rotation_is_not_labeled_pip_or_clinical_approval(self):
        result=extract(synthetic_hand(.3),handedness='right')
        self.assertAlmostEqual(result['joint_angles_radians'][12,0],.3)
        self.assertEqual(result['joint_angle_records'][12]['canonical_center_point'],'PINKY_MCP')
        assessment=assess(np.array([synthetic_hand()]*3),[0.,1.,2.],pending_profile(),
            handedness='right',length_unit='authored_units')
        self.assertEqual(assessment['joint_angle_records'],result['joint_angle_records'])
        self.assertFalse(assessment['evidence_backed_rule_checks_pass'])

    def test_surface_tip_motion_is_not_a_rigid_joint_edge_failure(self):
        poses=np.array([synthetic_hand()]*3)
        poses[1,20]+=(poses[1,20]-poses[1,19])*.01
        kinds=['mesh_surface_tip' if i in (4,8,12,16,20) else 'sdk_joint' for i in range(21)]
        result=assess(poses,[0.,1.,2.],synthetic_profile(),handedness='right',length_unit='authored_units',point_kinds=kinds)
        self.assertEqual(result['rigid_edges_checked_n'],15)
        self.assertFalse(any(v['rule']=='fixed_generated_rig_bone_lengths' for v in result['violations']))
        poses[1,18]+=[0.,0.,.05]
        result=assess(poses,[0.,1.,2.],synthetic_profile(),handedness='right',length_unit='authored_units',point_kinds=kinds)
        self.assertTrue(any(v['rule']=='fixed_generated_rig_bone_lengths' for v in result['violations']))

    def test_native_units_keep_limits_unresolved_and_refuse_physical_approval(self):
        profile=pending_profile();profile['length_unit']='model_native_units'
        kinds=['mesh_surface_tip' if i in (4,8,12,16,20) else 'sdk_joint' for i in range(21)]
        result=assess(np.array([synthetic_hand()]*3,dtype=np.float32),[0.,1.,2.],profile,
            handedness='right',length_unit='model_native_units',point_kinds=kinds)
        self.assertEqual(result['state'],'UNRESOLVED_LIMITS')
        self.assertFalse(result['evidence_backed_rule_checks_pass'])
        self.assertLess(result['rig_relative_numeric_tolerance'],1e-5)
        rule=profile['rules']['bone_lengths'];rule.update(status='evidence_backed',values=[[.1,2.]]*20,
            evidence={'url':'https://example.invalid/test','locator':'fixture','value_origin':'fixture','population_and_scope':'fixture'})
        with self.assertRaises(ValueError):validate(profile)

    def test_incorrect_point_kinds_and_low_precision_sdk_are_rejected(self):
        poses=np.array([synthetic_hand()]*3)
        kinds=['mesh_surface_tip' if i in (4,8,12,16,20) else 'sdk_joint' for i in range(21)]
        for bad in (kinds[:-1],['sdk_joint']*21):
            with self.assertRaises(ValueError):assess(poses,[0.,1.,2.],pending_profile(),handedness='right',length_unit='authored_units',point_kinds=bad)
        with self.assertRaises(ValueError):assess(poses.astype(np.float16),[0.,1.,2.],pending_profile(),handedness='right',length_unit='authored_units',point_kinds=kinds)

    def test_straight_fan_has_expected_lengths_zero_curvature_and_zero_local_angles(self):
        p=synthetic_hand();f=extract(p,handedness='right')
        np.testing.assert_allclose(f['bone_lengths'][5:],np.tile([.2,.15,.1],5),atol=1e-12)
        np.testing.assert_allclose(f['palm_curvatures'],0.,atol=1e-12)
        np.testing.assert_allclose(f['joint_angles_radians'],0.,atol=1e-12)
        self.assertEqual(f['local_frames'].shape,(15,3,3))

    def test_signed_octants_and_rotation_reconstruction_are_unambiguous(self):
        for x in (-1.,1.):
            for y in (-1.,1.):
                for z in (-1.,1.):
                    p=np.array([x,y,z]);angles=signed_angles(p)
                    self.assertEqual(np.sign(angles[0]),np.sign(x));self.assertEqual(np.sign(angles[1]),np.sign(y))
                    self.assertAlmostEqual(abs(angles[0]),math.pi/4 if z>0 else 3*math.pi/4)
                    np.testing.assert_allclose(rotation(*angles)@np.array([0.,0.,1.]),p/np.linalg.norm(p),atol=1e-12)

    def test_known_pinky_flexion_and_local_frame_orthonormality(self):
        f=extract(synthetic_hand(.3),handedness='right')
        self.assertAlmostEqual(f['joint_angles_radians'][12,0],.3)
        np.testing.assert_allclose(f['joint_angles_radians'][13:],0.,atol=1e-12)
        for frame in f['local_frames']:
            np.testing.assert_allclose(frame.T@frame,np.eye(3),atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(frame),1.)

    def test_translation_rotation_mirror_and_scale_have_declared_invariances(self):
        p=synthetic_hand(.3);a=extract(p,handedness='right')
        r=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
        b=extract(p@r.T+[3.,-2.,5.],handedness='right')
        left=p.copy();left[:,0]*=-1;c=extract(left,handedness='left')
        for key in ('bone_lengths','palm_curvatures','palm_spread_radians','joint_angles_radians'):
            np.testing.assert_allclose(a[key],b[key],atol=1e-10);np.testing.assert_allclose(a[key],c[key],atol=1e-10)
        d=extract(p*1000.,handedness='right')
        np.testing.assert_allclose(d['bone_lengths'],a['bone_lengths']*1000.,atol=1e-10)
        np.testing.assert_allclose(d['palm_curvatures'],a['palm_curvatures'],atol=1e-10)

    def test_original_contact_proxy_has_unmeasurable_palm_basis_not_an_anatomy_pass(self):
        for kind in KINDS:
            frame=records(kind,7)[0]
            p=[[frame['landmarks_world'][n][axis] for axis in ('x','y','z')] for n in LANDMARK_NAMES]
            with self.subTest(kind=kind),self.assertRaisesRegex(GeometryError,'CANCELLING_PALM_EDGE_NORMALS'):
                extract(p,handedness='right')

    def test_degenerate_points_and_angle_poles_are_rejected_without_filling(self):
        with self.assertRaises(GeometryError):extract(np.zeros((21,3)),handedness='right')
        with self.assertRaises(GeometryError):signed_angles([0.,1.,0.])
        for p in (np.full((21,3),np.nan),np.ones((21,3),bool),np.zeros((20,3))):
            with self.assertRaises(ValueError):extract(p,handedness='right')

    def test_joint_angle_hull_rejects_box_corner_but_includes_boundary(self):
        hull=[[0.,0.],[1.,0.],[0.,1.]]
        self.assertEqual(hull_distance([.2,.2],hull),0.)
        self.assertEqual(hull_distance([.5,.5],hull),0.)
        self.assertGreater(hull_distance([.9,.9],hull),0.)
        for bad in (hull[::-1],[[0,0],[1,0],[0,0]],[[0,0],[1,0],[.2,.2],[0,1]]):
            with self.assertRaises(ValueError):polygon(bad)

    def test_derivatives_use_real_unequal_seconds_and_flexion_unwrap(self):
        times=np.array([0.,.2,.5,1.]);angles=np.zeros((4,15,2))
        angles[:,:,0]=.5*times[:,None];angles[:,:,1]=-.2*times[:,None]
        v,a=angular_derivatives(angles,times)
        np.testing.assert_allclose(v[:,:,0],.5,atol=1e-12);np.testing.assert_allclose(v[:,:,1],-.2,atol=1e-12)
        np.testing.assert_allclose(a,0.,atol=1e-12)
        angles=np.zeros((3,15,2));angles[:,:,0]=np.array([math.pi-.1,-math.pi+.1,-math.pi+.3])[:,None]
        v,_=angular_derivatives(angles,[0.,1.,2.]);np.testing.assert_allclose(v[:,:,0],.2,atol=1e-12)

    def test_pending_profile_never_qualifies_generation(self):
        result=assess(np.array([synthetic_hand()]*3),[0.,1.,2.],pending_profile(),handedness='right',length_unit='authored_units')
        self.assertEqual(result['state'],'UNRESOLVED_LIMITS');self.assertEqual(len(result['unresolved_rules']),6)
        self.assertFalse(result['full_generator_ready']);self.assertFalse(result['biological_validity_proven'])

    def test_synthetic_math_pass_is_not_a_biological_or_release_pass(self):
        result=assess(np.array([synthetic_hand()]*3),[0.,1.,2.],synthetic_profile(),handedness='right',length_unit='authored_units')
        self.assertEqual(result['state'],'DECLARED_RULES_PASS');self.assertTrue(result['declared_rules_pass'])
        self.assertFalse(result['evidence_backed_rule_checks_pass']);self.assertFalse(result['release_allowed'])

    def test_temporal_violations_reject_moving_sequences(self):
        profile=synthetic_profile();profile['rules']['angular_speed_rad_s']['values']=np.full((15,2),.1).tolist()
        profile['rules']['angular_acceleration_rad_s2']['values']=np.full((15,2),.1).tolist()
        result=assess(np.array([synthetic_hand(f) for f in (0.,.3,0.)]),[0.,.1,.2],profile,handedness='right',length_unit='authored_units')
        self.assertEqual(result['state'],'RULE_VIOLATIONS')
        for key in ('angular_speed_rad_s','angular_acceleration_rad_s2'):
            self.assertTrue(any(row['rule']==key for row in result['violations']))

    def test_rig_length_changes_are_rejected_even_inside_broad_length_intervals(self):
        poses=np.array([synthetic_hand()]*3);direction=poses[1,20]-poses[1,19];poses[1,20]+=direction*.01
        result=assess(poses,[0.,1.,2.],synthetic_profile(),handedness='right',length_unit='authored_units')
        self.assertTrue(any(row['rule']=='fixed_generated_rig_bone_lengths' for row in result['violations']))

    def test_bad_profile_shapes_units_and_incomplete_evidence_are_rejected(self):
        for change in ('shape','angle_unit','evidence','physical_unit','missing'):
            profile=synthetic_profile()
            if change=='shape':profile['rules']['bone_lengths']['values']=[[0.,1.]]
            if change=='angle_unit':profile['rules']['joint_angle_hulls']['values'][0][0][0]=-90
            if change=='evidence':profile['rules']['bone_lengths']['status']='evidence_backed'
            if change=='physical_unit':
                rule=profile['rules']['bone_lengths'];rule['status']='evidence_backed'
                rule['evidence']={'url':'https://example.invalid/fixture','locator':'synthetic test',
                                 'value_origin':'test only','population_and_scope':'no biological population'}
            if change=='missing':profile['rules'].pop('angular_speed_rad_s')
            with self.subTest(change=change),self.assertRaises(ValueError):validate(profile)
        with self.assertRaises(ValueError):assess(np.array([synthetic_hand()]*3),[0.,1.,2.],pending_profile(),handedness='right',length_unit='mm')


if __name__=='__main__':unittest.main()
