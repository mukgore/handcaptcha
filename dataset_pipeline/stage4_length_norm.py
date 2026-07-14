# -*- coding: utf-8 -*-
"""Stage 4 (spec §3): forward+reverse frame concatenation to reach the
5-6s target length. Continuity at the join is automatic since the last
forward frame equals the first reverse frame -- coordinates are reused
as-is, no recomputation.

Note: real Jester clips run ~4s at ~12fps (~37 frames); doubling per this
literal method yields ~8s, overshooting the spec's stated 5-6s target. This
mismatch is intentional to implement per spec rather than deviate --
final_length_sec() below makes it visible in the per-clip report.
"""


def length_normalize(frames):
    if len(frames) < 2:
        return list(frames)
    return list(frames) + list(reversed(frames[:-1]))


def final_length_sec(frames, fps):
    if not fps:
        return None
    return len(frames) / fps
