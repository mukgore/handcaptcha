from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import threading
import unittest

from dataset_pipeline.private_delivery import PrivateDelivery, handler_for
from experiments.preview_server import PreviewServer
import test_release_registry as registry_fixtures


class PrivateDeliveryTests(unittest.TestCase):
    def setUp(self):
        # Synthetic review contracts remain inside temporary test directories.
        # No actual artifact is approved by these tests.
        self.fixture = registry_fixtures.ReleaseRegistryTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.advance(); self.root = self.fixture.root
        self.clock = [self.fixture.now.timestamp()]
        self.delivery = PrivateDelivery(self.fixture.registry, self.root/'delivery.sqlite3', clock=lambda: self.clock[0])
        self.session = self.delivery.provision_session('tenant-a', 'synthetic-subject', ttl_seconds=3600)
        self.token = self.delivery.issue(self.session, self.fixture.artifact, 'fixture-action', operation='op-1', ttl_seconds=60)

    def test_only_bound_session_can_read_and_tokens_are_not_stored_raw(self):
        raw = self.delivery.media(self.token, self.session)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.fixture.artifact)
        for tenant in ('tenant-a', 'tenant-b'):
            other = self.delivery.provision_session(tenant, 'other', ttl_seconds=60)
            with self.assertRaises(PermissionError): self.delivery.media(self.token, other)
        stored = (self.root/'delivery.sqlite3').read_bytes()
        self.assertNotIn(self.session.encode(), stored); self.assertNotIn(self.token.encode(), stored)

    def test_expiry_and_session_revocation_deny_future_access(self):
        self.clock[0] += 61
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)
        self.clock[0] -= 61
        self.delivery.revoke_session(self.session)
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)

    def test_retirement_and_byte_replacement_revoke_delivery(self):
        (self.root/'media.mp4').write_bytes(b'changed')
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)

    def test_registry_retirement_blocks_existing_grant(self):
        self.fixture.registry.transition(self.fixture.artifact, 7, 'RETIRED', {'reason': 'synthetic withdrawal'}, now=self.fixture.now)
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)
        with self.assertRaises(PermissionError):
            self.delivery.issue(self.session, self.fixture.artifact, 'fixture-action', operation='op-1', ttl_seconds=30)

    def test_verdict_action_binding_and_single_atomic_consumer(self):
        with self.assertRaises(PermissionError): self.delivery.consume(self.token, self.session, action='fixture-action', operation='op-1')
        self.delivery.record_verdict(self.token, passed=True, evidence_ref='synthetic-evaluator-test-only')
        with self.assertRaises(PermissionError): self.delivery.consume(self.token, self.session, action='other', operation='op-1')
        with self.assertRaises(PermissionError): self.delivery.consume(self.token, self.session, action='fixture-action', operation='wrong-op')
        def consume(_):
            try: return self.delivery.consume(self.token, self.session, action='fixture-action', operation='op-1')
            except PermissionError: return 'denied'
        with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(consume, range(4)))
        self.assertEqual(results.count('denied'), 3)
        with self.delivery._connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM actions').fetchone()[0], 1)
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)

    def test_failed_verdict_cannot_be_replaced(self):
        self.delivery.record_verdict(self.token, passed=False, evidence_ref='synthetic-failure')
        with self.assertRaises(PermissionError): self.delivery.record_verdict(self.token, passed=True, evidence_ref='replacement')
        with self.assertRaises(PermissionError): self.delivery.consume(self.token, self.session, action='fixture-action', operation='op-1')

    def test_http_range_head_no_cache_and_no_public_verdict_endpoint(self):
        server = PreviewServer(('127.0.0.1', 0), handler_for(self.delivery))
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        def cleanup(): server.shutdown(); server.server_close(); worker.join(timeout=2)
        self.addCleanup(cleanup)
        def request(method, path, headers):
            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            try:
                client.request(method, path, headers=headers); response = client.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally: client.close()
        headers = {'Authorization': 'Bearer '+self.session, 'Range': 'bytes=0-3'}
        status, meta, body = request('GET', '/media/'+self.token, headers)
        self.assertEqual((status, body), (206, b'synt'))
        self.assertIn('no-store', meta['Cache-Control']); self.assertEqual(meta['Vary'], 'Authorization')
        self.assertEqual(request('HEAD', '/media/'+self.token, headers)[2], b'')
        self.assertEqual(request('GET', '/media/'+self.token, {})[0], 403)
        self.assertEqual(request('GET', '/media/'+self.token, {**headers, 'Range': 'bytes=9999-'})[0], 416)
        self.assertEqual(request('GET', '/media/'+self.token+'?pass=true', headers)[0], 403)
        self.assertEqual(request('POST', '/complete', headers)[0], 501)

    def test_rights_expiry_and_media_budget(self):
        self.clock[0] = self.fixture.now.replace(year=2027).timestamp()
        fresh = self.delivery.provision_session('tenant-a', 'new-session', ttl_seconds=60)
        with self.assertRaises(PermissionError): self.delivery.issue(fresh, self.fixture.artifact, 'fixture-action', operation='op-1', ttl_seconds=30)
        self.clock[0] = self.fixture.now.timestamp()
        self.delivery.max_media_bytes = 2
        with self.assertRaises(PermissionError): self.delivery.media(self.token, self.session)

    def test_multiple_grants_cannot_duplicate_same_subject_operation(self):
        other = self.delivery.issue(self.session, self.fixture.artifact, 'fixture-action', operation='op-1', ttl_seconds=60)
        for token in (self.token, other):
            self.delivery.record_verdict(token, passed=True, evidence_ref='synthetic-fixture')
        self.delivery.consume(self.token, self.session, action='fixture-action', operation='op-1')
        with self.assertRaises(PermissionError):
            self.delivery.consume(other, self.session, action='fixture-action', operation='op-1')
