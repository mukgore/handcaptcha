"""Stage7 v2 geometry gate for the unchanged Stage6 midpoint mask.

Require middle-PIP coverage and visible non-target fingertips. Wrist/palm
exposure is no longer required (researcher decision, 2026-11-04).
These landmark proxies do not prove anatomical coverage, palm-facing input,
human recognizability, security or release approval.
"""
import math

from dataset_pipeline.common import P9, P10, P11, VISIBLE_FINGER_TIPS
from dataset_pipeline.stage1_extract import frame_points
from dataset_pipeline.stage6_occlusion import project_occlusion_circle

GATE_POLICY_VERSION = "midpoint_middle_pip_visible_fingertips_v2"


def _validate_config(config):
    if (not math.isfinite(config.condition1_margin_frac)
            or not 0 <= config.condition1_margin_frac < 1
            or not math.isfinite(config.condition2_margin_frac)
            or config.condition2_margin_frac < 0):
        raise ValueError("Invalid Stage7 geometry margins")
    minimum = config.condition2_min_visible_fingers
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= 4:
        raise ValueError("condition2_min_visible_fingers must be an integer from 1 to 4")
    if not math.isfinite(config.gate_pass_frac) or not 0 < config.gate_pass_frac <= 1:
        raise ValueError("gate_pass_frac must be in (0, 1]")


def check_frame_conditions(image_lm_px, center, radius, config):
    """Image x/y gate; middle fingertip is excluded from visible cues.

    condition1 is unchanged: P10 and midpoints P9-P10 / P10-P11 must be
    inside the margin-shrunk mask. condition2 counts thumb/index/ring/pinky
    tips outside the margin-expanded mask; the wrist may be inside.
    """
    _validate_config(config)
    detail = {"condition1": False, "condition2": False,
              "policy_version": GATE_POLICY_VERSION,
              "visible_fingers": [], "visible_finger_count": 0,
              "required_visible_fingers": config.condition2_min_visible_fingers,
              "reason": "invalid_geometry"}
    try:
        if (len(image_lm_px) != 21 or len(center) < 2
                or any(len(p) < 2 for p in image_lm_px)
                or not all(math.isfinite(v) for p in image_lm_px for v in p[:2])
                or not all(math.isfinite(v) for v in center[:2])
                or not math.isfinite(radius) or int(radius) < 1):
            return False, detail
        distance = lambda p: math.dist(p[:2], center[:2])
        p9, p10, p11 = image_lm_px[P9], image_lm_px[P10], image_lm_px[P11]
        middle = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        inner_radius = radius * (1 - config.condition1_margin_frac)
        detail["condition1"] = all(distance(p) <= inner_radius for p in
                                   (p10, middle(p9, p10), middle(p10, p11)))
        outer_radius = radius * (1 + config.condition2_margin_frac)
        detail["visible_fingers"] = [name for name, index in VISIBLE_FINGER_TIPS.items()
                                     if distance(image_lm_px[index]) >= outer_radius]
        detail["visible_finger_count"] = len(detail["visible_fingers"])
        detail["condition2"] = detail["visible_finger_count"] >= config.condition2_min_visible_fingers
    except (TypeError, ValueError, IndexError, OverflowError):
        return False, detail
    detail["reason"] = ("middle_joint_not_covered" if not detail["condition1"] else
                        "insufficient_visible_fingers" if not detail["condition2"] else None)
    return detail["condition1"] and detail["condition2"], detail


def gate_clip(frames, w3_new, config):
    _validate_config(config)
    total, passed = 0, 0
    failing_frame_idxs, frame_diagnostics = [], []
    for f in frames:
        total += 1
        idx = f.get("frame_idx") if isinstance(f, dict) else None
        detail = {"reason": "invalid_landmarks"}
        try:
            pts = frame_points(f, "px")
            if pts is None:
                ok = False
                detail = {"reason": "missing_landmarks"}
            else:
                center, radius = project_occlusion_circle(pts, w3_new)
                ok, detail = check_frame_conditions(pts, center, radius, config)
        except (ValueError, IndexError, TypeError, KeyError, AttributeError, OverflowError):
            ok = False
        frame_diagnostics.append({"frame_idx": idx, "accepted": ok, **detail})
        if ok:
            passed += 1
        else:
            failing_frame_idxs.append(idx)
    pass_frac = passed / total if total else 0.0
    return {"accepted": total > 0 and pass_frac >= config.gate_pass_frac,
            "pass_frac": pass_frac, "failing_frame_idxs": failing_frame_idxs,
            "total_checked": total, "policy_version": GATE_POLICY_VERSION,
            "frame_diagnostics": frame_diagnostics}
