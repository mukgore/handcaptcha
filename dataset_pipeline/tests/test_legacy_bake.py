import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from dataset_expansion_bake_v1 import bake_adopted


class LegacyBakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'clip.avi'
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*'FFV1'), 12., (32, 32))
        self.assertTrue(writer.isOpened())
        writer.write(np.full((32, 32, 3), 180, dtype=np.uint8))
        writer.release()
        self.adopted = self.root / 'adopted.json'
        self.output = self.root / 'private'

    def write_records(self, value):
        self.adopted.write_text(json.dumps(value), encoding='utf8')

    def test_dispatches_original_to_shared_renderer_ignoring_old_circles(self):
        self.write_records({'clip.avi': {'info': {'fps': 12}, 'frames_mask': []}})
        with patch('dataset_expansion_bake_v1.run_batch', return_value={'result': 'sentinel'}) as run:
            result = bake_adopted(self.adopted, self.root, self.output, 2.5)
        self.assertEqual(result, {'result': 'sentinel'})
        self.assertEqual(run.call_args.args[0], [str(self.source)])
        self.assertTrue(run.call_args.kwargs['render_candidates'])
        self.assertEqual(run.call_args.kwargs['w3_new'], 2.5)

    def test_missing_or_mismatched_fps_never_creates_output(self):
        for info in ({}, {'fps': 0}, {'fps': True}, {'fps': 24}):
            self.write_records({'clip.avi': {'info': info}})
            with self.subTest(info=info), self.assertRaises(ValueError):
                bake_adopted(self.adopted, self.root, self.output, 2.5)
            self.assertFalse(self.output.exists())

    def test_jpeg_directory_without_frame_times_is_rejected(self):
        (self.root / 'jpgs').mkdir()
        self.write_records({'jpgs': {'info': {'fps': 12}}})
        with self.assertRaises(ValueError):
            bake_adopted(self.adopted, self.root, self.output, 2.5)
        self.assertFalse(self.output.exists())

    def test_outside_source_root_and_existing_output_are_rejected(self):
        nested = self.root / 'nested'
        nested.mkdir()
        self.write_records({'../clip.avi': {'info': {'fps': 12}}})
        with self.assertRaises(ValueError):
            bake_adopted(self.adopted, nested, self.output, 2.5)
        self.output.mkdir()
        sentinel = self.output / 'keep'
        sentinel.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):
            bake_adopted(self.adopted, self.root, self.output, 2.5)
        self.assertEqual(sentinel.read_bytes(), b'existing')
