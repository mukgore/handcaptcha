# -*- coding: utf-8 -*-
import math

from dataset_pipeline.geometry import dist, midpoint, cross3, angle_between, joint_angle


def test_dist():
    assert dist((0, 0, 0), (3, 4, 0)) == 5.0


def test_midpoint():
    mp = midpoint((0, 0, 0), (2, 4, 6))
    assert list(mp) == [1.0, 2.0, 3.0]


def test_cross3_orthogonal_axes():
    result = cross3((1, 0, 0), (0, 1, 0))
    assert list(result) == [0.0, 0.0, 1.0]


def test_angle_between_orthogonal():
    assert math.isclose(angle_between((1, 0, 0), (0, 1, 0)), 90.0, abs_tol=1e-6)


def test_angle_between_opposite():
    assert math.isclose(angle_between((1, 0, 0), (-1, 0, 0)), 180.0, abs_tol=1e-6)


def test_joint_angle_straight_line():
    # p, j, c colinear with j in the middle -> interior angle is 180 deg.
    assert math.isclose(joint_angle((0, -1, 0), (0, 0, 0), (0, 1, 0)), 180.0, abs_tol=1e-6)


def test_joint_angle_right_angle():
    assert math.isclose(joint_angle((1, 0, 0), (0, 0, 0), (0, 1, 0)), 90.0, abs_tol=1e-6)
