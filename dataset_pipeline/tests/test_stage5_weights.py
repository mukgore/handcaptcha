# -*- coding: utf-8 -*-
import math

from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage5_weights import is_open_hand, frame_ratios
from dataset_pipeline.tests.fixtures import straight_middle_finger_world, bent_middle_finger_world


def test_is_open_hand_true_for_straight_finger():
    config = PipelineConfig()
    assert is_open_hand(straight_middle_finger_world(), config.t_straight_deg) is True


def test_is_open_hand_false_for_bent_finger():
    config = PipelineConfig()
    assert is_open_hand(bent_middle_finger_world(), config.t_straight_deg) is False


def test_frame_ratios_match_known_construction():
    # By fixtures.straight_middle_finger_world()'s construction: P9 at y=1,
    # P10 at y=2, P11 at y=3 relative to the wrist at the origin.
    r_pip, r_dip = frame_ratios(straight_middle_finger_world())
    assert math.isclose(r_pip, 2.0, rel_tol=1e-9)
    assert math.isclose(r_dip, 3.0, rel_tol=1e-9)
