# -*- coding: utf-8 -*-
"""Small synthetic 21-point hand-pose fixtures for unit tests. No real
Jester/InterHand2.6M data is available in this environment, so Stage 5/6/7
math is unit-tested against hand-built coordinates instead."""


def straight_middle_finger_world():
    """21 synthetic 3D world points, all in the z=0 plane (frontal to the
    camera). The middle finger (P0,P9,P10,P11,P12) is perfectly colinear
    along +y, so all three Stage-5 open-hand joint angles are exactly 180
    degrees, and r_PIP=2.0, r_DIP=3.0 by construction (P9 at y=1, P10 at
    y=2, P11 at y=3, relative to wrist at the origin)."""
    return [
        (0.0, 0.0, 0.0),      # 0 WRIST (P0)
        (-0.3, 0.3, 0.0),     # 1 THUMB_CMC
        (-0.4, 0.6, 0.0),     # 2 THUMB_MCP
        (-0.45, 0.8, 0.0),    # 3 THUMB_IP
        (-0.5, 1.0, 0.0),     # 4 THUMB_TIP
        (-0.6, 0.8, 0.0),     # 5 INDEX_MCP (P5)
        (-0.65, 1.3, 0.0),    # 6 INDEX_PIP
        (-0.68, 1.6, 0.0),    # 7 INDEX_DIP
        (-0.7, 1.9, 0.0),     # 8 INDEX_TIP
        (0.0, 1.0, 0.0),      # 9 MIDDLE_MCP (P9)
        (0.0, 2.0, 0.0),      # 10 MIDDLE_PIP (P10)
        (0.0, 3.0, 0.0),      # 11 MIDDLE_DIP (P11)
        (0.0, 4.0, 0.0),      # 12 MIDDLE_TIP (P12)
        (0.6, 0.8, 0.0),      # 13 RING_MCP
        (0.65, 1.3, 0.0),     # 14 RING_PIP
        (0.68, 1.6, 0.0),     # 15 RING_DIP
        (0.7, 1.9, 0.0),      # 16 RING_TIP
        (1.0, 0.7, 0.0),      # 17 PINKY_MCP (P17)
        (1.05, 1.1, 0.0),     # 18 PINKY_PIP
        (1.08, 1.4, 0.0),     # 19 PINKY_DIP
        (1.1, 1.7, 0.0),      # 20 PINKY_TIP
    ]


def bent_middle_finger_world():
    """Same as straight_middle_finger_world() but with P10 bent sideways, so
    the joint angle at P9 is well under a typical T_straight (should fail
    the Stage-5 open-hand test)."""
    pts = list(straight_middle_finger_world())
    pts[10] = (1.0, 1.5, 0.0)  # MIDDLE_PIP bent off the P0-P9-P11 line
    return pts


def edge_on_hand_world():
    """Same shape as straight_middle_finger_world() but rotated so the palm
    plane is edge-on to the camera (x-z plane instead of x-y) -- should fail
    the Stage-3 frontality test."""
    return [(x, 0.0, y) for (x, y, _z) in straight_middle_finger_world()]


def to_px(world_pts, scale=100.0, offset=(500.0, 500.0)):
    """Rescale/shift a world-space fixture into a plausible pixel-space
    fixture. The Stage 5/6/7 ratios and geometric-margin checks are
    scale-invariant, so reusing the same shape is sufficient for testing."""
    return [(p[0] * scale + offset[0], p[1] * scale + offset[1], p[2] * scale) for p in world_pts]
