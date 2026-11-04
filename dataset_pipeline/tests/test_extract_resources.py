import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from dataset_pipeline.stage1_extract import extract_landmarks


class Capture:
    def __init__(self):
        self.count=0
        self.released=False
    def isOpened(self): return True
    def get(self, key):
        return {cv2.CAP_PROP_FRAME_WIDTH:32, cv2.CAP_PROP_FRAME_HEIGHT:32,
                cv2.CAP_PROP_FPS:10., cv2.CAP_PROP_FRAME_COUNT:3,
                cv2.CAP_PROP_POS_MSEC:max(0,self.count-1)*100.}[key]
    def read(self):
        self.count+=1
        return (True,np.zeros((32,32,3),np.uint8)) if self.count<=3 else (False,None)
    def release(self): self.released=True


class ExtractResourceTests(unittest.TestCase):
    def test_constructor_failure_releases_video(self):
        capture=Capture()
        with patch('dataset_pipeline.stage1_extract.cv2.VideoCapture',return_value=capture), \
             patch('dataset_pipeline.stage1_extract.mp.solutions.hands.Hands',side_effect=RuntimeError('model failed')):
            with self.assertRaises(RuntimeError): extract_landmarks('synthetic.mp4', resource_mode='native')
        self.assertTrue(capture.released)

    def test_detector_failure_closes_model_and_capture(self):
        capture=Capture(); closed=[]
        detector=SimpleNamespace(process=lambda image: (_ for _ in ()).throw(RuntimeError('detector failed')),
                                 close=lambda:closed.append(True))
        with patch('dataset_pipeline.stage1_extract.cv2.VideoCapture',return_value=capture), \
             patch('dataset_pipeline.stage1_extract.mp.solutions.hands.Hands',return_value=detector):
            with self.assertRaises(RuntimeError): extract_landmarks('synthetic.mp4', resource_mode='native')
        self.assertTrue(capture.released);self.assertEqual(closed,[True])

    def test_decoder_timestamps_are_retained_without_index_fallback(self):
        capture=Capture()
        detector=SimpleNamespace(process=lambda image:SimpleNamespace(multi_hand_landmarks=None), close=lambda:None)
        with patch('dataset_pipeline.stage1_extract.cv2.VideoCapture',return_value=capture), \
             patch('dataset_pipeline.stage1_extract.mp.solutions.hands.Hands',return_value=detector):
            frames,info=extract_landmarks('synthetic.mp4', resource_mode='native')
        self.assertEqual([f['source_pts_ms'] for f in frames],[0.,100.,200.])
        self.assertEqual(info['decoded_frames'],3);self.assertTrue(info['timestamps_monotonic'])
        self.assertTrue(capture.released)
