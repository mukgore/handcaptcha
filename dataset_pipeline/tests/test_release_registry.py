import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from dataset_pipeline.release_registry import ReleaseRegistry, STATES, digest


class ReleaseRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'media.mp4').write_bytes(b'synthetic-registry-fixture-not-a-real-video')
        (self.root / 'report.json').write_bytes(b'synthetic-review-contract-fixture')
        self.now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.registry = ReleaseRegistry(self.root / 'registry.sqlite3', self.root)
        self.artifact = self.registry.register('media.mp4', ['a'*64], purpose='SERVICE_CANDIDATE')

    def review(self, state):
        evidence = dict(kind=state, status='PASS', artifact_sha256=self.artifact,
                        reviewer_id='synthetic-reviewer', protocol_version='fixture-only',
                        reviewed_at='2026-11-03T00:00:00Z', report_file='report.json',
                        report_sha256=digest(self.root / 'report.json'))
        flags = ['service_delivery_allowed', 'derivatives_allowed', 'source_quality_passed',
                 'masked_only_encoder_input', 'timeline_mapping_verified', 'all_frames_checked',
                 'pts_checked', 'all_tracks_checked', 'all_renditions_checked',
                 'anatomical_coverage_reviewed', 'task_feasible', 'ambiguity_policy_accepted',
                 'preregistered_criteria_passed', 'release_approved']
        evidence.update({k: True for k in flags})
        evidence.update(rights_status='APPROVED', source_hashes=['a'*64], rights_record_id='fixture',
                        expires_at='2026-12-01T00:00:00Z', mask_policy_version='fixture',
                        failed_frames=0, unknown_frames=0, decoded_frames=3,
                        evaluation_scope='synthetic-contract-only', acceptance_rule_ref='fixture',
                        holdout_policy_ref='fixture', attack_families=['fixture'], release_version='fixture')
        return evidence

    def advance(self, stop='RELEASED'):
        revision = 0
        for state in STATES[1:]:
            revision = self.registry.transition(self.artifact, revision, state, self.review(state), now=self.now)
            if state == stop:
                break
        return revision

    def test_release_requires_all_stages_and_same_bytes_then_retires(self):
        self.assertFalse(self.registry.eligible_for_serving(self.artifact, now=self.now))
        revision = self.advance()
        self.assertTrue(self.registry.eligible_for_serving(self.artifact, now=self.now))
        self.registry.transition(self.artifact, revision, 'RETIRED', {'reason': 'fixture withdrawal'}, now=self.now)
        self.assertFalse(self.registry.eligible_for_serving(self.artifact, now=self.now))

    def test_stages_and_stale_revision_cannot_be_skipped(self):
        with self.assertRaises(ValueError):
            self.registry.transition(self.artifact, 0, 'RELEASED', self.review('RELEASED'), now=self.now)
        self.advance('RIGHTS_CLEARED')
        with self.assertRaises(ValueError):
            self.registry.transition(self.artifact, 0, 'QUALITY_CHECKED', self.review('QUALITY_CHECKED'), now=self.now)

    def test_unknown_denied_missing_source_and_research_only_never_release(self):
        for changes in ({'rights_status': 'UNKNOWN'}, {'rights_status': 'DENIED'}, {'source_hashes': []}, {'service_delivery_allowed': False}):
            evidence = self.review('RIGHTS_CLEARED');evidence.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.registry.transition(self.artifact, 0, 'RIGHTS_CLEARED', evidence, now=self.now)
        (self.root / 'research.mp4').write_bytes(b'synthetic-research-only')
        self.artifact = self.registry.register('research.mp4', ['a'*64])
        self.advance('SECURITY_EVALUATED')
        with self.assertRaises(ValueError):
            self.registry.transition(self.artifact, 6, 'RELEASED', self.review('RELEASED'), now=self.now)

    def test_bad_artifact_or_report_binding_fails_without_advancing(self):
        for changes in ({'artifact_sha256': 'b'*64}, {'report_sha256': 'c'*64}, {'report_file': '../outside'}, {'reviewed_at': '2099-01-01T00:00:00Z'}):
            evidence = self.review('RIGHTS_CLEARED');evidence.update(changes)
            with self.subTest(changes=changes), self.assertRaises((ValueError, OSError)):
                self.registry.transition(self.artifact, 0, 'RIGHTS_CLEARED', evidence, now=self.now)
        self.advance('RIGHTS_CLEARED')

    def test_expired_rights_and_modified_artifact_cannot_be_served(self):
        self.advance()
        self.assertFalse(self.registry.eligible_for_serving(self.artifact, now=datetime(2027, 1, 1, tzinfo=timezone.utc)))
        (self.root / 'media.mp4').write_bytes(b'tampered')
        self.assertFalse(self.registry.eligible_for_serving(self.artifact, now=self.now))

    def test_failed_or_unknown_frame_review_is_not_accepted(self):
        self.advance('MASKED')
        for changes in ({'failed_frames': 1}, {'unknown_frames': 1}, {'pts_checked': False}, {'all_tracks_checked': False}, {'decoded_frames': 0}):
            evidence = self.review('ARTIFACT_VERIFIED');evidence.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.registry.transition(self.artifact, 3, 'ARTIFACT_VERIFIED', evidence, now=self.now)

    def test_concurrent_promotions_allow_only_one_revision(self):
        def promote(_):
            try:
                self.registry.transition(self.artifact, 0, 'RIGHTS_CLEARED', self.review('RIGHTS_CLEARED'), now=self.now)
                return 'accepted'
            except ValueError:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(promote, range(2))), ['accepted', 'stale'])

    def test_quarantine_revokes_eligibility_and_prevents_repromotion(self):
        self.registry.transition(self.artifact, 0, 'QUARANTINED', {'reason': 'fixture review failure'}, now=self.now)
        with self.assertRaises(ValueError):
            self.registry.transition(self.artifact, 1, 'RIGHTS_CLEARED', self.review('RIGHTS_CLEARED'), now=self.now)
