import unittest

import numpy as np

from experiments.motion_fixture.mesh_intersections import triangle_pairs,topology,frame


class MeshIntersectionTests(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])

    def inspect(self,b):return triangle_pairs(self.a[None],np.asarray(b,float)[None],1e-7)

    def test_crossing_and_parallel_separation(self):
        b=[[.2,.2,-1.],[.2,.2,1.],[.8,.2,0.]]
        result=self.inspect(b)
        self.assertTrue(result['two_plane_straddling_indicator'][0])
        self.assertFalse(self.inspect(self.a+[0,0,.01])['intersects'][0])

    def test_coplanar_disjoint_inside_and_edge_contact(self):
        self.assertFalse(self.inspect(self.a+[2,2,0])['intersects'][0])
        self.assertTrue(self.inspect(self.a*.2+[.2,.2,0])['coplanar_overlap'][0])
        self.assertTrue(self.inspect([[0,0,0],[1,0,0],[0,-1,0]])['coplanar_overlap'][0])

    def test_coplanar_aabb_overlap_can_still_be_disjoint(self):
        self.assertFalse(self.inspect([[.8,.8,0],[1.2,.8,0],[.8,1.2,0]])['intersects'][0])

    def test_touch_and_pair_symmetry(self):
        b=np.array([[.2,.2,0],[.2,.2,1],[.8,.2,1.]])
        result=self.inspect(b);self.assertTrue(result['touch_or_numerically_ambiguous'][0])
        reverse=triangle_pairs(b[None],self.a[None],1e-7)
        for key in result:np.testing.assert_array_equal(result[key],reverse[key])

    def test_mesh_translation_rotation_scale_invariance(self):
        b=np.array([[.2,.2,-1.],[.2,.2,1.],[.8,.2,0.]])
        vertices=np.concatenate((self.a,b));mesh=topology([[0,1,2],[3,4,5]],6)
        expected=frame(vertices,mesh)
        rotation=np.array([[0,0,1],[1,0,0],[0,1,0]])
        for variant in (vertices+100.,vertices@rotation,vertices*1000.):
            actual=frame(variant,mesh)
            self.assertEqual(actual['pair_ids'],expected['pair_ids'])
        self.assertFalse(expected['volume_penetration_free_proven'])

    def test_shared_vertex_pairs_excluded_not_declared_volumetrically_clear(self):
        mesh=topology([[0,1,2],[0,3,4]],5)
        vertices=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,0,1]],float)
        result=frame(vertices,mesh)
        self.assertEqual(result['shared_vertex_pairs_excluded_n'],1)
        self.assertEqual(result['tested_pairs_n'],0)
        self.assertFalse(result['volume_penetration_free_proven'])

    def test_degenerate_faces_and_duplicate_topology_are_not_clear(self):
        mesh=topology([[0,1,2]],3)
        result=frame([[0,0,0],[1,0,0],[2,0,0]],mesh)
        self.assertEqual(result['state'],'UNMEASURABLE_DEGENERATE_TRIANGLES')
        self.assertFalse(result['sampled_surface_clear'])
        for faces in ([[0,1,2],[2,0,1]],[[0,0,1]],[[0,1,3]]):
            with self.assertRaises(ValueError):topology(faces,3)

    def test_surface_containment_is_explicitly_not_volume_check(self):
        vertices=np.concatenate((self.a,self.a*.1+[.1,.1,.2]))
        result=frame(vertices,topology([[0,1,2],[3,4,5]],6))
        self.assertTrue(result['sampled_surface_clear'])
        self.assertFalse(result['volume_penetration_free_proven'])
        with self.assertRaises(ValueError):self.inspect(np.zeros((3,3)))


if __name__=='__main__':unittest.main()
