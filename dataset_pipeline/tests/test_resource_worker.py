import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dataset_pipeline.resource_worker import ASSETS, _prepare_resources, extract_in_worker
from dataset_pipeline.pipeline import run_batch


class ResourceWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.mp4';self.source.write_bytes(b'synthetic-placeholder')
        self.cache=patch('dataset_pipeline.resource_worker.WORKER_ROOT',self.root/'private_worker')
        self.cache.start();self.addCleanup(self.cache.stop)

    def test_parent_launches_isolated_module_and_returns_consistent_output(self):
        def run(command,**kwargs):
            request=json.loads(Path(command[command.index('--request')+1]).read_text())
            self.assertEqual(request['video_path'],str(self.source))
            Path(command[command.index('--output')+1]).write_text(json.dumps({'frames':[], 'video_info':{'decoded_frames':0}}))
            self.assertEqual(command[1:3],['-m','dataset_pipeline.resource_worker'])
            return SimpleNamespace(returncode=0)
        with patch('dataset_pipeline.resource_worker.subprocess.run',side_effect=run):
            frames,info=extract_in_worker(self.source,.5)
        self.assertEqual(frames,[]);self.assertEqual(info['decoded_frames'],0)

    def test_timeout_retains_private_diagnostics(self):
        with patch('dataset_pipeline.resource_worker.subprocess.run',side_effect=subprocess.TimeoutExpired('owned_worker',1)):
            with self.assertRaises(TimeoutError) as failure:extract_in_worker(self.source,.5,timeout_seconds=1)
        self.assertTrue((self.root/'private_worker'/'failures'/failure.exception.diagnostic_id/'request.json').is_file())

    def test_failed_or_inconsistent_worker_never_returns_an_extraction(self):
        with patch('dataset_pipeline.resource_worker.subprocess.run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(RuntimeError):extract_in_worker(self.source,.5)
        def malformed(command,**kwargs):
            Path(command[command.index('--output')+1]).write_text(json.dumps({'frames':[{}],'video_info':{'decoded_frames':0}}))
            return SimpleNamespace(returncode=0)
        with patch('dataset_pipeline.resource_worker.subprocess.run',side_effect=malformed):
            with self.assertRaises(RuntimeError):extract_in_worker(self.source,.5)

    def test_cache_uses_only_installed_assets_and_rejects_modified_copies(self):
        package=self.root/'package'
        with self.assertRaises(FileNotFoundError):_prepare_resources(package)
        for name in ASSETS:
            path=package/'modules'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
        directory,fingerprint=_prepare_resources(package)
        self.assertEqual(_prepare_resources(package),(directory,fingerprint))
        (directory/'mediapipe'/'modules'/ASSETS[0]).write_bytes(b'tampered')
        with self.assertRaises(ValueError):_prepare_resources(package)

    def test_batch_keeps_extraction_failures_in_denominator(self):
        with patch('dataset_pipeline.pipeline.process_clip',side_effect=RuntimeError('private message must stay private')):
            result=run_batch([str(self.source)],w3_new=2.5,output_dir=self.root/'batch',render_candidates=True)
        self.assertEqual(len(result['clip_reports']),1)
        self.assertEqual(result['clip_reports'][0]['final_status'],'quarantined_extraction')
        self.assertEqual(result['artifacts'],[])
        self.assertNotIn('private message',json.dumps(result))

    def test_second_batch_cannot_replace_the_first_failure_report(self):
        target=self.root/'batch'
        with patch('dataset_pipeline.pipeline.process_clip',side_effect=RuntimeError('first failure')):
            run_batch([str(self.source)],w3_new=2.5,output_dir=target,render_candidates=True)
        before=(target/'pipeline_report.json').read_bytes()
        with patch('dataset_pipeline.pipeline.process_clip') as process:
            with self.assertRaises(FileExistsError):
                run_batch([str(self.source)],w3_new=2.5,output_dir=target,render_candidates=True)
            process.assert_not_called()
        self.assertEqual((target/'pipeline_report.json').read_bytes(),before)
