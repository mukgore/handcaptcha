"""Isolate the legacy MediaPipe ASCII resource-path workaround in one process."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from dataset_pipeline.storage import WEB_ROOT, private_output

WORKER_ROOT = WEB_ROOT.parent / 'private_artifacts' / 'mediapipe_worker'
ASSETS = ('hand_landmark/hand_landmark_tracking_cpu.binarypb',
          'hand_landmark/hand_landmark_full.tflite', 'hand_landmark/handedness.txt',
          'palm_detection/palm_detection_full.tflite')


def extract_in_worker(video_path, confidence, *, timeout_seconds=300):
    if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:
        raise ValueError('Confidence must be finite and in [0, 1]')
    if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not math.isfinite(timeout_seconds) or timeout_seconds<=0:
        raise ValueError('Positive finite extraction timeout required')
    source=Path(video_path).resolve(strict=True)
    root=private_output(WORKER_ROOT);root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='request_',dir=root) as temporary:
        folder=Path(temporary);request=folder/'request.json';output=folder/'result.json'
        request.write_text(json.dumps({'video_path':str(source),'confidence':confidence}),encoding='utf8')
        try:
            with (folder/'stderr.txt').open('wb') as errors:
                result=subprocess.run([sys.executable,'-m','dataset_pipeline.resource_worker',
                                       '--request',str(request),'--output',str(output)],
                                      cwd=WEB_ROOT,stdout=subprocess.DEVNULL,stderr=errors,timeout=timeout_seconds)
            if result.returncode:
                raise RuntimeError('MediaPipe resource worker failed')
            payload=json.loads(output.read_text(encoding='utf8'))
            frames,info=payload['frames'],payload['video_info']
            if not isinstance(frames,list) or not isinstance(info,dict) or info.get('decoded_frames')!=len(frames):
                raise ValueError('Inconsistent extraction worker output')
            return frames,info
        except (OSError,ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired) as error:
            diagnostics=root/'failures'/folder.name
            diagnostics.parent.mkdir(exist_ok=True)
            shutil.copytree(folder,diagnostics)
            if isinstance(error,subprocess.TimeoutExpired):
                failure=TimeoutError('MediaPipe worker exceeded its extraction budget; private diagnostics retained')
            else:
                failure=RuntimeError('MediaPipe extraction failed; private worker diagnostics retained')
            failure.diagnostic_id=folder.name
            raise failure from error


def _asset_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def _prepare_resources(package_root):
    assets={name:package_root/'modules'/name for name in ASSETS}
    if not all(path.is_file() for path in assets.values()):
        raise FileNotFoundError('Required installed MediaPipe assets missing; downloads are disabled')
    hashes={name:_asset_digest(path) for name,path in assets.items()}
    fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    cache_root=private_output(WORKER_ROOT)/'cache';cache_root.mkdir(parents=True,exist_ok=True)
    target=cache_root/fingerprint
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='.assets_',dir=cache_root) as temporary:
            source=Path(temporary)
            for name,path in assets.items():
                destination=source/'mediapipe'/'modules'/name
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
            try:os.rename(source,target)
            except OSError:
                if not target.is_dir():raise
    if any(_asset_digest(target/'mediapipe'/'modules'/name)!=value for name,value in hashes.items()):
        raise ValueError('Cached model assets changed')
    return target,fingerprint


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();request=json.loads(Path(args.request).read_text(encoding='utf8'))
    if set(request)!={'video_path','confidence'}:raise ValueError('Unexpected worker request')
    import mediapipe
    import mediapipe.python.solution_base as solution_base
    from dataset_pipeline.stage1_extract import _extract_landmarks_native
    resources,fingerprint=_prepare_resources(Path(mediapipe.__file__).parent)
    relative=os.path.relpath(resources,Path.cwd())
    if not relative.isascii():raise ValueError('Run worker from the same-drive ASCII-relative repository root')
    native_os=solution_base.os
    class ResourcePath:
        def __getattr__(self,name):return getattr(os.path,name)
        def abspath(self,value):
            if value==solution_base.__file__:return str(Path(relative)/'mediapipe'/'python'/'solution_base.py')
            return os.path.abspath(value)
    # No installed file or parent-process module is modified. This process
    # contains exactly one extractor, so the legacy global resource root is local.
    solution_base.os=SimpleNamespace(sep=os.sep,path=ResourcePath())
    try:frames,info=_extract_landmarks_native(request['video_path'],request['confidence'])
    finally:solution_base.os=native_os
    info['resource_runtime']='isolated_ascii_resource_worker';info['resource_fingerprint']=fingerprint
    with Path(args.output).open('x',encoding='utf8') as stream:
        json.dump({'frames':frames,'video_info':info},stream,allow_nan=False)


if __name__=='__main__':main()
