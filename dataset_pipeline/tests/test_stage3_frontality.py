# -*- coding: utf-8 -*-
from dataset_pipeline.stage3_frontality import frame_theta
from dataset_pipeline.tests.fixtures import straight_middle_finger_world, edge_on_hand_world


def test_frame_theta_near_zero_for_frontal_pose():
    theta = frame_theta(straight_middle_finger_world())
    assert theta < 5.0


def test_frame_theta_near_ninety_for_edge_on_pose():
    theta = frame_theta(edge_on_hand_world())
    assert 85.0 < theta < 95.0
