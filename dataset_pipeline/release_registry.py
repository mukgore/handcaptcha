"""Private, transactional review registry. Evidence is supplied by reviewers.

This validates bindings and required approvals, not the truth of a review.
Research-only artifacts can never reach RELEASED. Serving must consult this
registry, rather than trusting release_allowed from an arbitrary JSON file.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone
from dataset_pipeline.storage import private_output

STATES = ('INGESTED', 'RIGHTS_CLEARED', 'QUALITY_CHECKED', 'MASKED',
          'ARTIFACT_VERIFIED', 'HUMAN_REVIEWED', 'SECURITY_EVALUATED', 'RELEASED')
TERMINAL = ('QUARANTINED', 'RETIRED')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _time(value):
    if not isinstance(value, str):
        raise ValueError('Timezone-aware ISO timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone-aware ISO timestamp required')
    return result


def validate_review(state, evidence, artifact_hash, source_hashes, now):
    if not isinstance(evidence, dict) or evidence.get('kind') != state or evidence.get('status') != 'PASS':
        raise ValueError('Explicit matching PASS review required')
    if evidence.get('artifact_sha256') != artifact_hash:
        raise ValueError('Review belongs to a different artifact')
    if not all(_text(evidence.get(k)) for k in ('reviewer_id', 'protocol_version')):
        raise ValueError('Reviewer and protocol version required')
    if _time(evidence.get('reviewed_at')) > now:
        raise ValueError('Review time is in the future')
    if not _sha(evidence.get('report_sha256')):
        raise ValueError('Hash of the private review report required')
    flags = {
        'RIGHTS_CLEARED': ('service_delivery_allowed', 'derivatives_allowed'),
        'QUALITY_CHECKED': ('source_quality_passed',),
        'MASKED': ('masked_only_encoder_input', 'timeline_mapping_verified'),
        'ARTIFACT_VERIFIED': ('all_frames_checked', 'pts_checked', 'all_tracks_checked', 'all_renditions_checked'),
        'HUMAN_REVIEWED': ('anatomical_coverage_reviewed', 'task_feasible', 'ambiguity_policy_accepted'),
        'SECURITY_EVALUATED': ('preregistered_criteria_passed',),
        'RELEASED': ('release_approved',),
    }
    if any(evidence.get(k) is not True for k in flags[state]):
        raise ValueError('Missing required review approval')
    if state == 'RIGHTS_CLEARED':
        if evidence.get('rights_status') != 'APPROVED' or set(evidence.get('source_hashes', [])) != set(source_hashes):
            raise ValueError('Rights must cover every source')
        if not _text(evidence.get('rights_record_id')):
            raise ValueError('Rights record required')
        if evidence.get('expires_at') is not None and _time(evidence['expires_at']) <= now:
            raise ValueError('Rights have expired')
    if state == 'MASKED' and not _text(evidence.get('mask_policy_version')):
        raise ValueError('Mask policy version required')
    if state == 'ARTIFACT_VERIFIED':
        if any(type(evidence.get(k)) is not int or evidence[k] != 0 for k in ('failed_frames', 'unknown_frames')):
            raise ValueError('No failed or unknown output frames allowed')
        if type(evidence.get('decoded_frames')) is not int or evidence['decoded_frames'] <= 0:
            raise ValueError('Positive decoded frame count required')
    if state == 'SECURITY_EVALUATED':
        if not all(_text(evidence.get(k)) for k in ('evaluation_scope', 'acceptance_rule_ref', 'holdout_policy_ref')):
            raise ValueError('Security scope and predeclared acceptance/split policy required')
        if not isinstance(evidence.get('attack_families'), list) or not evidence['attack_families'] or not all(_text(x) for x in evidence['attack_families']):
            raise ValueError('Evaluated attack families required')
    if state == 'RELEASED' and not _text(evidence.get('release_version')):
        raise ValueError('Release version required')


class ReleaseRegistry:
    def __init__(self, database, private_root):
        self.root = private_output(private_root).resolve(strict=True)
        registry_path = Path(database).resolve()
        if not registry_path.is_relative_to(self.root):
            raise ValueError('Registry database must be inside its private root')
        self.database = str(registry_path)
        with self._connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY, relative_media TEXT NOT NULL, source_hashes TEXT NOT NULL,
                purpose TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS reviews (
                artifact_id TEXT NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL,
                evidence TEXT NOT NULL, PRIMARY KEY(artifact_id, revision));
            ''')

    def _connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def _media(self, relative):
        if Path(relative).is_absolute():
            raise ValueError('Relative private path required')
        path = (self.root / relative).resolve(strict=True)
        if not path.is_relative_to(self.root) or path == self.root or not path.is_file():
            raise ValueError('Media must remain in the private root')
        return path

    def register(self, relative_media, source_hashes, *, purpose='RESEARCH_ONLY'):
        if purpose not in ('RESEARCH_ONLY', 'SERVICE_CANDIDATE'):
            raise ValueError('Explicit supported purpose required')
        if not isinstance(source_hashes, list) or not source_hashes or not all(_sha(x) for x in source_hashes):
            raise ValueError('Private source hashes required')
        artifact = digest(self._media(relative_media))
        with self._connect() as db:
            db.execute('INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, 0)',
                       (artifact, str(relative_media), json.dumps(sorted(set(source_hashes))), purpose, 'INGESTED'))
        return artifact

    def transition(self, artifact, expected_revision, state, evidence, *, now=None):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Nonnegative integer registry revision required')
        now = now or datetime.now(timezone.utc)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT relative_media, source_hashes, purpose, state, revision FROM artifacts WHERE id=?', (artifact,)).fetchone()
            if row is None:
                raise KeyError(artifact)
            media, sources, purpose, previous, revision = row
            if revision != expected_revision:
                raise ValueError('Stale registry revision')
            if previous in TERMINAL:
                raise ValueError('Quarantined/retired artifacts cannot be promoted')
            if state in TERMINAL:
                if not isinstance(evidence, dict) or not _text(evidence.get('reason')):
                    raise ValueError('Quarantine/retirement reason required')
            else:
                if previous not in STATES or STATES.index(previous)+1 >= len(STATES) or state != STATES[STATES.index(previous)+1]:
                    raise ValueError('Review stages cannot be skipped')
                if state == 'RELEASED' and purpose != 'SERVICE_CANDIDATE':
                    raise ValueError('Research-only artifact cannot be released')
                if digest(self._media(media)) != artifact:
                    raise ValueError('Artifact bytes changed after registration')
                validate_review(state, evidence, artifact, json.loads(sources), now)
                if not _text(evidence.get('report_file')) or digest(self._media(evidence['report_file'])) != evidence['report_sha256']:
                    raise ValueError('Private report bytes do not match the review hash')
                if state == 'RELEASED':
                    self._check_rights(db, artifact, now)
            serialized = json.dumps(evidence, sort_keys=True, allow_nan=False)
            db.execute('INSERT INTO reviews VALUES (?, ?, ?, ?)', (artifact, revision+1, state, serialized))
            db.execute('UPDATE artifacts SET state=?, revision=? WHERE id=?', (state, revision+1, artifact))
            return revision+1

    def _check_rights(self, db, artifact, now):
        row = db.execute('SELECT evidence FROM reviews WHERE artifact_id=? AND state=?', (artifact, 'RIGHTS_CLEARED')).fetchone()
        if row is None:
            raise ValueError('No rights approval')
        expiry = json.loads(row[0]).get('expires_at')
        if expiry is not None and _time(expiry) <= now:
            raise ValueError('Rights have expired')

    def eligible_for_serving(self, artifact, *, now=None):
        now = now or datetime.now(timezone.utc)
        with self._connect() as db:
            row = db.execute('SELECT relative_media, purpose, state FROM artifacts WHERE id=?', (artifact,)).fetchone()
            if row is None or row[1:] != ('SERVICE_CANDIDATE', 'RELEASED'):
                return False
            try:
                self._check_rights(db, artifact, now)
                return digest(self._media(row[0])) == artifact
            except (ValueError, OSError):
                return False
