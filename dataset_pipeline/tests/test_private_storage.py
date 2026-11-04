from pathlib import Path
import tempfile
import unittest

from dataset_pipeline.storage import WEB_ROOT, private_output
from dataset_pipeline.pipeline import run_batch
from experiments.motion_fixture.generate import build_fixture


class PrivateStorageTests(unittest.TestCase):
    def test_static_root_descendants_and_ancestors_are_rejected(self):
        for path in (WEB_ROOT, WEB_ROOT / 'pipeline_output', WEB_ROOT.parent):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_output(path)

    def test_sibling_private_folder_is_allowed(self):
        expected = WEB_ROOT.parent / 'private_artifacts' / 'test-only'
        self.assertEqual(private_output(expected), expected.resolve())

    def test_pipeline_and_fixture_reject_static_output_before_processing(self):
        target = WEB_ROOT / 'must_not_create_private_storage_test'
        with self.assertRaises(ValueError):
            run_batch([], output_dir=target, render_candidates=True)
        with self.assertRaises(ValueError):
            build_fixture(target, template='middle_flex', seed=7, w3_new=2.5)
        self.assertFalse(target.exists())
