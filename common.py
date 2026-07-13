# -*- coding: utf-8 -*-
"""MediaPipe 21-point hand landmark convention shared across all pipeline stages."""

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# Spec §1 shorthand: P0=wrist, P5=index MCP, P9=middle MCP, P10=middle PIP,
# P11=middle DIP, P12=middle TIP, P17=pinky MCP.
P0, P5, P9, P10, P11, P12, P17 = WRIST, INDEX_MCP, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP, PINKY_MCP

LANDMARK_NAMES = [
    "WRIST",
    "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
    "INDEX_MCP", "INDEX_PIP", "INDEX_DIP", "INDEX_TIP",
    "MIDDLE_MCP", "MIDDLE_PIP", "MIDDLE_DIP", "MIDDLE_TIP",
    "RING_MCP", "RING_PIP", "RING_DIP", "RING_TIP",
    "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP",
]

# Spec §5 Stage 5 "open hand" test: three interior joint angles, each read at
# the triple's middle index (e.g. (P0,P9,P10) is the interior angle at P9).
OPEN_HAND_JOINTS = [
    (P0, P9, P10),
    (P9, P10, P11),
    (P10, P11, P12),
]

# Spec §9 Stage 7 condition 1 (middle finger first-joint coverage) proxy points.
CONDITION1_POINTS = [P10]  # extended with midpoints of (P9,P10) and (P10,P11) in stage7_gate.py

# Spec §9 Stage 7 condition 2 (palm/wrist cues must remain visible) landmark set.
PALM_CUE_INDICES = [P0, THUMB_CMC, P5, RING_MCP, P17]
