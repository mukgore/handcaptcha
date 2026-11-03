"""Codec output failures and concurrent publication must never expose a candidate."""
import os
import unittest
from unittest.mock import patch
import numpy as np
from dataset_pipeline.stage6_occlusion import generate_occluded_video
from dataset_pipeline.tests import test_mask_delivery as delivery
record = delivery.record


class MaskIntegrityTests(unittest.TestCase):
    setUp = delivery.MaskDeliveryTests.setUp
    def test_unmasked_decoded_output_is_rejected(self):
        import cv2
        real_capture = cv2.VideoCapture
        source = self.source
        class Unmasked:
            def __init__(self): self.count = 0
            def isOpened(self): return True
            def read(self):
                self.count += 1
                return (True, np.full((32, 32, 3), 255, np.uint8)) if self.count <= 3 else (False, None)
            def release(self): pass
        with patch('dataset_pipeline.stage6_occlusion.cv2.VideoCapture',
                   side_effect=lambda path: real_capture(path) if path == source else Unmasked()):
            with self.assertRaisesRegex(ValueError, 'interior check failed'):
                generate_occluded_video(source, [record(i) for i in range(3)], self.info, 1., self.target)
        self.assertFalse(os.path.exists(self.target))
        self.assertEqual(sorted(os.listdir(self.tempdir.name)), ['source.mp4'])

    def test_concurrent_output_creation_is_never_replaced(self):
        real_link = os.link
        def competing_link(src, dst):
            with open(dst, 'wb') as fh: fh.write(b'competing-artifact')
            return real_link(src, dst)
        with patch('dataset_pipeline.stage6_occlusion.os.link', side_effect=competing_link):
            with self.assertRaises(FileExistsError):
                generate_occluded_video(self.source, [record(i) for i in range(3)], self.info, 1., self.target)
        with open(self.target, 'rb') as fh: self.assertEqual(fh.read(), b'competing-artifact')
        self.assertNotIn('.masked-', ''.join(os.listdir(self.tempdir.name)))
