"""Create a NEW private Windows/Python3.10 venv from hashed binary wheels.

Existing environments/PATH are untouched. Network access is explicit with
--download; rebuilding an already downloaded wheelhouse is a separate step.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
import zipfile
from email.parser import BytesParser

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from dataset_pipeline.storage import private_output


def run(output, *, download=False, offline_wheelhouse=None, lock_file=None):
    if os.name != 'nt' or sys.version_info[:2] != (3, 10):
        raise ValueError('This validation recipe targets Windows CPython3.10 only')
    if bool(download) == bool(offline_wheelhouse):
        raise ValueError('Choose explicit download or an existing offline wheelhouse')
    root = private_output(output); root.mkdir(parents=True, exist_ok=False)
    wheels = root/'wheels' if download else private_output(offline_wheelhouse).resolve(strict=True)
    if download: wheels.mkdir()
    env = root/'venv'; venv.EnvBuilder(with_pip=True).create(env)
    python = env/'Scripts'/'python.exe'
    requirements = REPO/'dataset_pipeline'/'requirements-win-py310.txt'
    (root/'requested_requirements.txt').write_bytes(requirements.read_bytes())
    steps = [([str(python), '-m', 'pip', 'download', '--disable-pip-version-check', '--only-binary=:all:',
               '--index-url', 'https://pypi.org/simple', '--dest', str(wheels), '-r', str(requirements)], 'download')]
    def execute(command, name):
        with (root/(name+'.log')).open('xb') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    if download:
        for command, name in steps: execute(command, name)
    records = []; names = set()
    for path in sorted(wheels.iterdir()):
        if path.suffix != '.whl': raise ValueError('Only binary wheels accepted')
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            if len(members) != 1: raise ValueError('Wheel metadata must be unambiguous')
            info = BytesParser().parsebytes(archive.read(members[0]))
        name, version = info['Name'], info['Version']
        if name.lower().replace('_', '-') in names: raise ValueError('Duplicate distribution')
        names.add(name.lower().replace('_', '-'))
        records.append({'name': name, 'version': version, 'filename': path.name,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
    lock = root/'requirements-wheels.lock'
    if download:
        lock.write_text(''.join(f"{x['name']}=={x['version']} --hash=sha256:{x['sha256']}\n" for x in records), encoding='utf8')
    else:
        source_lock=Path(lock_file or REPO/'dataset_pipeline'/'locks'/'windows-cp310-20261105.lock').resolve(strict=True)
        lock.write_bytes(source_lock.read_bytes())
    (root/'wheel_manifest.json').write_text(json.dumps({'schema_version': 1, 'platform': 'windows_cpython310',
                                                      'binary_only': True, 'wheels': records}, indent=2)+'\n', encoding='utf8')
    execute([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-index', '--no-deps',
             '--find-links', str(wheels), '--require-hashes', '-r', str(lock)], 'install')
    execute([str(python), '-m', 'pip', 'check'], 'pip_check')
    execute([str(python), '-c', 'import cv2,mediapipe,numpy,google.protobuf;'
             'assert callable(mediapipe.solutions.hands.Hands);'
             'print(cv2.__version__,mediapipe.__version__,numpy.__version__,google.protobuf.__version__)'], 'import_check')
    result = {'schema_version': 1, 'new_isolated_environment': True, 'dependency_check_passed': True,
              'imports_passed': True, 'wheel_count': len(records), 'wheel_bytes': sum(x['bytes'] for x in records),
              'lock_sha256': hashlib.sha256(lock.read_bytes()).hexdigest(),
              'offline_install': not download,
              'scope': 'new_windows_python310_environment_not_historical_build_recovery'}
    (root/'rebuild_result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--download', action='store_true'); source.add_argument('--offline-wheelhouse')
    parser.add_argument('--lock')
    args = parser.parse_args(); run(args.output, download=args.download, offline_wheelhouse=args.offline_wheelhouse, lock_file=args.lock)
