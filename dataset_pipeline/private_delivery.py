"""Registry-backed local delivery core; provisioning/verdicts are trusted APIs.

No public approval endpoint, automatic review, or browser-trusted completion.
The HTTP adapter is loopback only. Deployment/auth gateway remain separate.
"""
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import math
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from experiments.preview_server import byte_range


def _hash(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 128:
        raise PermissionError('Invalid capability')
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def _label(value):
    return isinstance(value, str) and 0 < len(value) <= 128 and value.strip() == value


class PrivateDelivery:
    def __init__(self, registry, database, *, clock=time.time, max_media_bytes=128*1024*1024):
        self.registry = registry; self.clock = clock
        path = Path(database).resolve()
        if not path.is_relative_to(registry.root) or path == Path(registry.database):
            raise ValueError('Separate private delivery database required')
        if type(max_media_bytes) is not int or not 0 < max_media_bytes <= 128*1024*1024:
            raise ValueError('Bounded media byte budget required')
        self.database = str(path); self.max_media_bytes = max_media_bytes
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                  token_hash TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL,
                  expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS grants (
                  token_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL, tenant TEXT NOT NULL,
                  artifact TEXT NOT NULL, action TEXT NOT NULL, operation TEXT NOT NULL, expires REAL NOT NULL,
                  verdict TEXT, verdict_ref TEXT, consumed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS actions (
                  grant_hash TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL,
                  action TEXT NOT NULL, operation TEXT NOT NULL, executed REAL NOT NULL,
                  UNIQUE(tenant,subject,operation));
            ''')

    def _connect(self): return sqlite3.connect(self.database, timeout=10)

    def _eligible(self, artifact):
        return self.registry.eligible_for_serving(artifact, now=datetime.fromtimestamp(self.clock(), timezone.utc))

    def _expiry(self, ttl, maximum):
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not math.isfinite(ttl) or not 0 < ttl <= maximum:
            raise ValueError('Explicit bounded lifetime required')
        return self.clock() + ttl

    def provision_session(self, tenant, subject, *, ttl_seconds):
        """Trusted gateway/operator only. Never bind tenant from browser claims."""
        if not all(_label(x) for x in (tenant, subject)): raise ValueError('Tenant and subject required')
        expiry = self._expiry(ttl_seconds, 3600); token = secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute('INSERT INTO sessions(token_hash,tenant,subject,expires) VALUES(?,?,?,?)',
                       (_hash(token), tenant, subject, expiry))
        return token

    def _session(self, db, token):
        row = db.execute('SELECT tenant,subject,expires,revoked FROM sessions WHERE token_hash=?', (_hash(token),)).fetchone()
        if row is None or row[3] or row[2] <= self.clock(): raise PermissionError('Session unavailable')
        return row

    def revoke_session(self, token):
        with self._connect() as db: db.execute('UPDATE sessions SET revoked=1 WHERE token_hash=?', (_hash(token),))

    def issue(self, session_token, artifact, action, *, operation, ttl_seconds):
        if not all(_label(x) for x in (action, operation)): raise ValueError('Bound action and operation required')
        expiry = self._expiry(ttl_seconds, 600)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE'); session = self._session(db, session_token)
            if not self._eligible(artifact): raise PermissionError('Artifact unavailable')
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO grants(token_hash,session_hash,tenant,artifact,action,operation,expires) VALUES(?,?,?,?,?,?,?)',
                       (_hash(token), _hash(session_token), session[0], artifact, action, operation, min(expiry, session[2])))
        return token

    def _grant(self, db, token, session_token):
        session = self._session(db, session_token)
        row = db.execute('SELECT artifact,action,expires,verdict,consumed,tenant,session_hash,operation FROM grants WHERE token_hash=?', (_hash(token),)).fetchone()
        if (row is None or row[2] <= self.clock() or row[4] or row[5] != session[0]
                or row[6] != _hash(session_token)):
            raise PermissionError('Grant unavailable')
        if not self._eligible(row[0]): raise PermissionError('Artifact unavailable')
        return session, row

    def media(self, token, session_token):
        with self._connect() as db:
            _session, row = self._grant(db, token, session_token)
        # Hash the exact immutable in-memory bytes that will be sent. Reopening
        # after a path-only hash check would permit replacement between checks.
        with self.registry._connect() as db:
            path_row = db.execute('SELECT relative_media FROM artifacts WHERE id=?', (row[0],)).fetchone()
        if path_row is None: raise PermissionError('Artifact unavailable')
        try:
            with self.registry._media(path_row[0]).open('rb') as stream:
                raw = stream.read(self.max_media_bytes + 1)
        except (OSError, ValueError): raise PermissionError('Artifact unavailable') from None
        if len(raw) > self.max_media_bytes or hashlib.sha256(raw).hexdigest() != row[0]:
            raise PermissionError('Media bytes changed or exceeded budget')
        with self._connect() as db: self._grant(db, token, session_token)
        return raw

    def record_verdict(self, token, *, passed, evidence_ref):
        """Trusted evaluator API; never exposed as a client-supplied PASS route."""
        if type(passed) is not bool or not _label(evidence_ref): raise ValueError('Explicit trusted verdict required')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT expires,consumed,verdict FROM grants WHERE token_hash=?', (_hash(token),)).fetchone()
            if row is None or row[0] <= self.clock() or row[1] or row[2] is not None:
                raise PermissionError('Verdict cannot be replaced or added now')
            db.execute('UPDATE grants SET verdict=?,verdict_ref=? WHERE token_hash=?',
                       ('PASS' if passed else 'FAIL', evidence_ref, _hash(token)))

    def consume(self, token, session_token, *, action, operation):
        """Atomically record one protected action; no arbitrary external effects.

        External services need a transaction/outbox using the returned receipt,
        rather than executing before this transaction and risking double use.
        """
        # Serialize registry withdrawal against this local action commit. Session
        # revocation and duplicate consumers serialize on the delivery DB.
        with self.registry._connect() as registry_db:
            registry_db.execute('BEGIN IMMEDIATE')
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE'); session, row = self._grant(db, token, session_token)
                if row[1] != action or row[7] != operation or row[3] != 'PASS': raise PermissionError('Action not authorized')
                key = _hash(token)
                try:
                    db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?)', (key, session[0], session[1], action, operation, self.clock()))
                except sqlite3.IntegrityError: raise PermissionError('Operation already consumed') from None
                db.execute('UPDATE grants SET consumed=1 WHERE token_hash=?', (key,))
        return key


def handler_for(delivery):
    class PrivateMediaHandler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass  # Never log grant/session bearer values
        def do_GET(self): self._serve()
        def do_HEAD(self): self._serve()
        def _serve(self):
            status = 403; payload = b''; partial = False; start = 0; end = -1; size = 0
            try:
                if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                    raise PermissionError('Host unavailable')
                parsed = urlsplit(self.path); parts = parsed.path.split('/')
                if parsed.query or len(parts) != 3 or parts[1] != 'media': raise PermissionError('Route unavailable')
                bearer = self.headers.get('Authorization', '')
                if not bearer.startswith('Bearer '): raise PermissionError('Session required')
                payload = delivery.media(parts[2], bearer[7:]); size = len(payload)
                try:
                    start, end, partial = byte_range(self.headers.get('Range'), size)
                    status = 206 if partial else 200; payload = payload[start:end+1]
                except ValueError: status = 416; payload = b''
            except (PermissionError, UnicodeError, ValueError): payload = b''
            self.send_response(status)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'private, no-store, max-age=0')
            self.send_header('Pragma', 'no-cache'); self.send_header('Vary', 'Authorization')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            if status in (200, 206):
                self.send_header('Content-Type', 'video/mp4'); self.send_header('Accept-Ranges', 'bytes')
            if status == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            if status == 416: self.send_header('Content-Range', f'bytes */{size}')
            self.end_headers()
            if self.command != 'HEAD':
                try: self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError): pass
    return PrivateMediaHandler
