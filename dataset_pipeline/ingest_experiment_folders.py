"""Notebook originals enter the current private research candidate pipeline."""
import hashlib
import json
import math
from pathlib import Path
import re

from dataset_pipeline.pipeline import run_batch


def _validate(directory, clip_id, output, weight):
    if not isinstance(clip_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', clip_id):
        raise ValueError('Safe ASCII clip ID required')
    if output is None:
        raise ValueError('Explicit new private output directory required')
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0:
        raise ValueError('Explicit positive finite w3_new required')
    source = Path(directory) / 'baseline_original.mp4'
    if not source.is_file():
        raise FileNotFoundError(source)
    target = Path(output)
    if target.exists():
        raise FileExistsError('Refusing to overwrite an existing intake or serving pool')
    return source, target


def _write(path, data):
    with path.open('x', encoding='utf8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_experiment_folder(experiment_dir, clip_id, output_dir=None, label=None, *, w3_new=None, config=None):
    """Replaces historical unchecked pool export with private reprocessing.

    Old masked videos are never copied. Unexpected failure leaves no intake
    completion marker; partial outputs remain available for diagnosis.
    """
    source, target = _validate(experiment_dir, clip_id, output_dir, w3_new)
    target.mkdir(parents=True, exist_ok=False)
    digest = _digest(source)
    result = run_batch([str(source)], config=config, w3_new=w3_new,
                       output_dir=str(target), render_candidates=True)
    if _digest(source) != digest:
        raise ValueError('Source changed during intake; no completion marker published')
    entry = {'schema_version': 1, 'clip_id': clip_id, 'label': label,
             'origin_type': 'notebook_baseline_reprocessed', 'source_sha256': digest,
             'state': 'RESEARCH_CANDIDATE' if result['artifacts'] else 'QUARANTINED',
             'pipeline_status': result['clip_reports'][0]['final_status'],
             'artifacts': result['artifacts'], 'rights_status': 'UNREVIEWED',
             'release_allowed': False, 'legacy_mask_used': False}
    _write(target / 'intake.json', entry)
    return entry


def ingest_many(experiment_dirs_with_ids, output_dir=None, *, w3_new=None, config=None):
    """Each ID uses a separate directory; no serving manifest is produced."""
    rows = list(experiment_dirs_with_ids)
    if not rows or output_dir is None:
        raise ValueError('Sources and explicit new private output required')
    root = Path(output_dir)
    if root.exists():
        raise FileExistsError('Refusing to overwrite existing output')
    ids = [row[1] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate clip IDs')
    for directory, clip_id, _label in rows:
        _validate(directory, clip_id, root / clip_id, w3_new)
    root.mkdir(parents=True, exist_ok=False)
    entries = [ingest_experiment_folder(d, cid, root / cid, label, w3_new=w3_new, config=config)
               for d, cid, label in rows]
    manifest = {'schema_version': 1, 'scope': 'private_research_intake',
                'release_allowed': False, 'clips': entries}
    _write(root / 'intake_manifest.json', manifest)
    return manifest
