"""Regression tests for source/frame alignment and fail-closed masking."""
import os
import tempfile
import unittest

import cv2
import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES
from dataset_pipeline.config import PipelineConfig
from dataset_pipeline.stage6_occlusion import generate_occluded_video, project_occlusion_circle
from dataset_pipeline.stage7_gate import gate_clip


def record(idx, detected=True):
    landmarks = {name: {"x": 8.0, "y": 8.0, "z": 0.0} for name in LANDMARK_NAMES}
    landmarks["MIDDLE_MCP"] = {"x": 24.0, "y": 24.0, "z": 1e6}
    return {"frame_idx": idx, "detected": detected, "landmarks_px": landmarks}


class MaskDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.source = os.path.join(self.tempdir.name, "source.mp4")
        self.target = os.path.join(self.tempdir.name, "masked.mp4")
        self.info = {"width": 32, "height": 32, "fps": 10.0}
        writer = cv2.VideoWriter(self.source, cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 32))
        self.assertTrue(writer.isOpened())
        for _ in range(3):
            writer.write(np.full((32, 32, 3), 255, dtype=np.uint8))
        writer.release()

    def test_masked_output_is_decodable_and_covers_every_frame(self):
        generate_occluded_video(self.source, [record(i) for i in range(3)],
                                self.info, 1.0, self.target)
        cap = cv2.VideoCapture(self.target)
        try:
            count = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                self.assertLess(int(frame[16, 16].max()), 30)
                count += 1
            self.assertEqual(count, 3)
        finally:
            cap.release()

    def test_missing_middle_mask_never_publishes_video(self):
        frames = [record(0), record(1, detected=False), record(2)]
        with self.assertRaisesRegex(ValueError, "No mask landmarks"):
            generate_occluded_video(self.source, frames, self.info, 1.0, self.target)
        self.assertFalse(os.path.exists(self.target))

    def test_short_mask_array_never_publishes_partial_video(self):
        with self.assertRaisesRegex(ValueError, "more frames"):
            generate_occluded_video(self.source, [record(0), record(1)],
                                    self.info, 1.0, self.target)
        self.assertFalse(os.path.exists(self.target))

    def test_existing_artifact_is_not_replaced(self):
        with open(self.target, "wb") as fh:
            fh.write(b"existing-release")
        with self.assertRaises(FileExistsError):
            generate_occluded_video(self.source, [record(i) for i in range(3)],
                                    self.info, 1.0, self.target)
        with open(self.target, "rb") as fh:
            self.assertEqual(fh.read(), b"existing-release")

    def test_filtered_timeline_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "consecutive"):
            generate_occluded_video(self.source, [record(0), record(2), record(3)],
                                    self.info, 1.0, self.target)
        self.assertFalse(os.path.exists(self.target))

    def test_image_depth_is_not_used_to_place_raster_mask(self):
        pts = [(8.0, 8.0, 0.0)] * 21
        pts[9] = (24.0, 24.0, 1e6)
        center, radius = project_occlusion_circle(pts, 1.0)
        self.assertEqual(center, (16.0, 16.0))
        self.assertAlmostEqual(radius, 2**0.5 * 8)

    def test_unknown_frame_counts_against_full_gate_denominator(self):
        frames = [record(0), record(1, detected=False)]
        result = gate_clip(frames, 1.0, PipelineConfig())
        self.assertEqual(result["total_checked"], 2)
        self.assertIn(1, result["failing_frame_idxs"])
        self.assertFalse(result["accepted"])


if __name__ == "__main__":
    unittest.main()
