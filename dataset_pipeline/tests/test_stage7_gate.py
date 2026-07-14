# -*- coding: utf-8 -*-
from dataset_pipeline.common import P0, THUMB_CMC, P5, RING_MCP, P17, P9, P10, P11
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.geometry import dist
from dataset_pipeline.stage6_occlusion import project_occlusion_circle
from dataset_pipeline.stage7_gate import check_frame_conditions


def _placeholder_landmarks():
    # Unused indices parked far from the test circle so they can never
    # accidentally satisfy/violate a condition.
    return [(9999.0, 9999.0, 0.0)] * 21


def test_check_frame_conditions_passes_when_joint_covered_and_palm_visible():
    lm = _placeholder_landmarks()
    lm[P9], lm[P10], lm[P11] = (0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 10.0, 0.0)
    lm[P0] = (200.0, 200.0, 0.0)
    lm[THUMB_CMC] = (180.0, 180.0, 0.0)
    lm[P5] = (150.0, -150.0, 0.0)
    lm[RING_MCP] = (-150.0, 150.0, 0.0)
    lm[P17] = (-200.0, -200.0, 0.0)

    config = PipelineConfig()
    ok, detail = check_frame_conditions(lm, center=(0.0, 0.0, 0.0), radius=50.0, config=config)
    assert ok is True
    assert detail == {"condition1": True, "condition2": True}


def test_check_frame_conditions_fails_when_pip_joint_not_covered():
    lm = _placeholder_landmarks()
    lm[P9], lm[P10], lm[P11] = (0.0, -10.0, 0.0), (100.0, 100.0, 0.0), (10.0, 10.0, 0.0)
    lm[P0] = (200.0, 200.0, 0.0)
    lm[THUMB_CMC] = (180.0, 180.0, 0.0)
    lm[P5] = (150.0, -150.0, 0.0)
    lm[RING_MCP] = (-150.0, 150.0, 0.0)
    lm[P17] = (-200.0, -200.0, 0.0)

    config = PipelineConfig()
    ok, detail = check_frame_conditions(lm, center=(0.0, 0.0, 0.0), radius=50.0, config=config)
    assert ok is False
    assert detail["condition1"] is False


def test_check_frame_conditions_fails_when_palm_cue_covered():
    lm = _placeholder_landmarks()
    lm[P9], lm[P10], lm[P11] = (0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 10.0, 0.0)
    lm[P0] = (10.0, 10.0, 0.0)  # too close to the mask center
    lm[THUMB_CMC] = (180.0, 180.0, 0.0)
    lm[P5] = (150.0, -150.0, 0.0)
    lm[RING_MCP] = (-150.0, 150.0, 0.0)
    lm[P17] = (-200.0, -200.0, 0.0)

    config = PipelineConfig()
    ok, detail = check_frame_conditions(lm, center=(0.0, 0.0, 0.0), radius=50.0, config=config)
    assert ok is False
    assert detail["condition2"] is False


def test_project_occlusion_circle_matches_spec_formula():
    lm = _placeholder_landmarks()
    lm[P0] = (0.0, 0.0, 0.0)
    lm[P9] = (0.0, 100.0, 0.0)

    center, radius = project_occlusion_circle(lm, w3_new=1.5)
    assert center == (0.0, 50.0, 0.0)
    assert radius == 75.0  # dist(P0,P9)*w3_new/2 = 100*1.5/2


def test_project_occlusion_circle_wrist_coverage_tension():
    """Documents a spec-internal tension found while implementing Stage 6/7:
    per the literal Stage 6 formula (center=midpoint(P0,P9),
    diameter=dist(P0,P9)*w3_new), the wrist P0 ends up strictly INSIDE the
    occlusion circle whenever w3_new > 1 -- which is the expected regime for
    all three original occlusion levels (1.45/1.75/1.95). That conflicts
    with Stage 7's condition 2 ("팔목 등 손 형태 단서가 잔존"). Flagged here
    as a regression-tracked known issue rather than silently worked around;
    resolve once real data clarifies intent (e.g. whether the center should
    track further from the wrist, as the old ratio-projection did)."""
    lm = _placeholder_landmarks()
    lm[P0] = (0.0, 0.0, 0.0)
    lm[P9] = (0.0, 100.0, 0.0)

    center, radius = project_occlusion_circle(lm, w3_new=1.95)
    assert dist(lm[P0], center) < radius
