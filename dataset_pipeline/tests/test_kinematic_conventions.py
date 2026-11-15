import math
import unittest

import numpy as np

from experiments.motion_fixture.kinematic_conventions import (
    chain,equivalent_modified_inputs,isolated_mcp_vector,ISOLATED_BMC_BASIS,
)
from experiments.motion_fixture.biomechanical_features import signed_angles,rotation


class KinematicConventionTests(unittest.TestCase):
    def test_standard_neutral_and_cmc_rotation_have_known_endpoints(self):
        lengths=[1.,.8,.6,.4]
        result=chain('nonthumb',[0]*5,lengths,'BIO07_standard_DH')
        np.testing.assert_allclose(result['points'],[[0,0,0],[1,0,0],[1.8,0,0],[2.4,0,0],[2.8,0,0]],atol=1e-12)
        rotated=chain('nonthumb',[math.pi/2,0,0,0,0],lengths,'BIO07_standard_DH')
        np.testing.assert_allclose(rotated['points'][:,1],result['points'][:,0],atol=1e-12)

    def test_nonthumb_full_chain_agrees_after_declared_frame_and_sign_mapping(self):
        q=[.2,.3,.5,.4,.2];lengths=[1.,.8,.6,.4]
        a=chain('nonthumb',q,lengths,'BIO07_standard_DH');mapped,alignment=equivalent_modified_inputs('nonthumb',q)
        b=chain('nonthumb',mapped,lengths,'BIO06_modified_DH')
        np.testing.assert_allclose(b['points']@alignment[:3,:3].T,a['points'],atol=1e-12)
        np.testing.assert_allclose(alignment@b['tip_transform'],a['tip_transform'],atol=1e-12)
        naive=chain('nonthumb',q,lengths,'BIO06_modified_DH')
        self.assertGreater(np.linalg.norm(naive['points']-a['points']),.1)

    def test_thumb_chain_agrees_with_terminal_translation(self):
        q=[.3,.2,.5,.4];lengths=[1.,.8,.6]
        a=chain('thumb',q,lengths,'BIO07_standard_DH');mapped,alignment=equivalent_modified_inputs('thumb',q)
        b=chain('thumb',mapped,lengths,'BIO06_modified_DH')
        np.testing.assert_allclose(a['points'],b['points'],atol=1e-12)
        np.testing.assert_allclose(a['tip_transform'],alignment@b['tip_transform'],atol=1e-12)

    def test_isolated_bmc_vector_roundtrip_but_mixed_angles_are_not_identical(self):
        for abduction,flexion in ((0.,.4),(.3,0.),(.3,.6)):
            vector=isolated_mcp_vector(abduction,flexion)
            pair=signed_angles(ISOLATED_BMC_BASIS.T@vector)
            predicted=ISOLATED_BMC_BASIS@rotation(*pair)@np.array([0.,0.,1.])
            np.testing.assert_allclose(predicted,vector,atol=1e-12)
            if abduction and flexion:self.assertGreater(np.linalg.norm(pair-[flexion,abduction]),.01)
            else:np.testing.assert_allclose(pair,[flexion,abduction],atol=1e-12)

    def test_explicit_boundaries_and_shape_rejections(self):
        for kind,q,lengths,convention in (('other',[0]*5,[1]*4,'BIO07_standard_DH'),
            ('nonthumb',[0]*4,[1]*4,'BIO07_standard_DH'),('thumb',[0]*4,[1,-1,1],'BIO07_standard_DH'),
            ('thumb',[0]*4,[1]*3,'other')):
            with self.assertRaises(ValueError):chain(kind,q,lengths,convention)


if __name__=='__main__':unittest.main()
