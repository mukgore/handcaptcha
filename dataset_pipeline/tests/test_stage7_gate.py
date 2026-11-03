# -*- coding: utf-8 -*-
from dataset_pipeline.common import P0, THUMB_CMC, P5, RING_MCP, P17, P9, P10, P11
from dataset_pipeline.config import PipelineConfig
import math
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
    assert detail["condition1"] is True
    assert detail["condition2"] is True
    assert detail["visible_finger_count"] == 4


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


def test_check_frame_conditions_allows_wrist_covered_with_visible_fingertips():
    lm = _placeholder_landmarks()
    lm[P9], lm[P10], lm[P11] = (0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 10.0, 0.0)
    lm[P0] = (10.0, 10.0, 0.0)  # wrist coverage is allowed in Stage7 v2
    lm[THUMB_CMC] = (180.0, 180.0, 0.0)
    lm[P5] = (150.0, -150.0, 0.0)
    lm[RING_MCP] = (-150.0, 150.0, 0.0)
    lm[P17] = (-200.0, -200.0, 0.0)

    config = PipelineConfig()
    ok, detail = check_frame_conditions(lm, center=(0.0, 0.0, 0.0), radius=50.0, config=config)
    assert ok is True
    assert detail["condition2"] is True


def test_project_occlusion_circle_matches_spec_formula():
    lm = _placeholder_landmarks()
    lm[P0] = (0.0, 0.0, 0.0)
    lm[P9] = (0.0, 100.0, 0.0)

    center, radius = project_occlusion_circle(lm, w3_new=1.5)
    assert center == (0.0, 50.0)
    assert radius == 75.0  # dist(P0,P9)*w3_new/2 = 100*1.5/2


def test_project_occlusion_circle_keeps_wrist_coverage_by_design():
    """Stage6 is unchanged. Stage7 v2 allows this covered wrist rather than
    rejecting every such frame because of the historical wrist-outside rule."""
    lm = _placeholder_landmarks()
    lm[P0] = (0.0, 0.0, 0.0)
    lm[P9] = (0.0, 100.0, 0.0)

    center, radius = project_occlusion_circle(lm, w3_new=1.95)
    assert math.dist(lm[P0][:2], center) < radius
