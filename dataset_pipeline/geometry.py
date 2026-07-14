# -*- coding: utf-8 -*-
"""Generic 2D/3D vector math used across pipeline stages. All functions accept
plain (x,y) or (x,y,z) tuples/lists/np.ndarrays and return floats or arrays.
"""
import numpy as np


def to_arr(p):
    return np.asarray(p, dtype=float)


def dist(a, b):
    return float(np.linalg.norm(to_arr(a) - to_arr(b)))


def midpoint(a, b):
    return (to_arr(a) + to_arr(b)) / 2.0


def cross3(a, b):
    return np.cross(to_arr(a), to_arr(b))


def angle_between(v1, v2):
    """Angle in degrees between two vectors (order-independent, 0-180)."""
    v1, v2 = to_arr(v1), to_arr(v2)
    m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if m1 < 1e-12 or m2 < 1e-12:
        return 0.0
    cos_a = np.dot(v1, v2) / (m1 * m2)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def joint_angle(p, j, c):
    """Interior angle (degrees) at vertex j formed by rays j->p and j->c.

    Generalizes handtest1.py's compute_joint_angle to arbitrary dimensionality
    (works for both 2D pixel-space and 3D world-landmark points).
    """
    p, j, c = to_arr(p), to_arr(j), to_arr(c)
    return angle_between(p - j, c - j)
