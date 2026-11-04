import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dataset_pipeline.ingest_experiment_folders import ingest_experiment_folder, ingest_many


class LegacyIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'baseline_original.mp4').write_bytes(b'original-test-source')
        (self.source / 'level3_DIP.mp4').write_bytes(b'old-mask-must-not-be-used')

    def result(self, accepted):
        return {'artifacts': [{'artifact_id': 'test-only'}] if accepted else [],
                'clip_reports': [{'final_status': 'artifact_verified_research' if accepted else 'discarded_stage7'}]}

    def test_reprocesses_original_and_never_exports_a_serving_pool(self):
        target = self.root / 'private'
        with patch('dataset_pipeline.ingest_experiment_folders.run_batch', return_value=self.result(True)) as run:
            entry = ingest_experiment_folder(self.source, 'test01', target, w3_new=2.5)
        self.assertEqual(run.call_args.args[0], [str(self.source / 'baseline_original.mp4')])
        self.assertTrue(run.call_args.kwargs['render_candidates'])
        self.assertFalse(entry['release_allowed'])
        self.assertFalse(entry['legacy_mask_used'])
        self.assertEqual(entry['state'], 'RESEARCH_CANDIDATE')
        self.assertEqual(sorted(p.name for p in target.iterdir()), ['intake.json'])

    def test_gate_rejection_stays_quarantined(self):
        with patch('dataset_pipeline.ingest_experiment_folders.run_batch', return_value=self.result(False)):
            entry = ingest_experiment_folder(self.source, 'test01', self.root / 'private', w3_new=2.5)
        self.assertEqual(entry['state'], 'QUARANTINED')
        self.assertEqual(entry['artifacts'], [])

    def test_invalid_inputs_and_existing_output_do_not_run_pipeline(self):
        target = self.root / 'private'
        for cid, weight in (('../escape', 2.5), ('valid', None), ('valid', True), ('valid', float('nan'))):
            with self.subTest(cid=cid, weight=weight), self.assertRaises(ValueError):
                ingest_experiment_folder(self.source, cid, target, w3_new=weight)
            self.assertFalse(target.exists())
        target.mkdir()
        sentinel = target / 'pool_manifest.json'
        sentinel.write_bytes(b'existing-pool')
        with self.assertRaises(FileExistsError):
            ingest_experiment_folder(self.source, 'valid', target, w3_new=2.5)
        self.assertEqual(sentinel.read_bytes(), b'existing-pool')

    def test_many_uses_separate_ids_and_preflights_duplicates(self):
        target = self.root / 'private'
        rows = [(self.source, 'a', None), (self.source, 'b', None)]
        with patch('dataset_pipeline.ingest_experiment_folders.run_batch', return_value=self.result(False)) as run:
            manifest = ingest_many(rows, target, w3_new=2.5)
        self.assertEqual(run.call_count, 2)
        self.assertFalse(manifest['release_allowed'])
        self.assertEqual(len(json.loads((target / 'intake_manifest.json').read_text())['clips']), 2)
        duplicate = self.root / 'duplicate'
        with self.assertRaises(ValueError):
            ingest_many([rows[0], rows[0]], duplicate, w3_new=2.5)
        self.assertFalse(duplicate.exists())

    def test_unexpected_failure_never_writes_completion_marker(self):
        target = self.root / 'private'
        with patch('dataset_pipeline.ingest_experiment_folders.run_batch', side_effect=ValueError('decode failure')):
            with self.assertRaises(ValueError):
                ingest_experiment_folder(self.source, 'valid', target, w3_new=2.5)
        self.assertFalse((target / 'intake.json').exists())
