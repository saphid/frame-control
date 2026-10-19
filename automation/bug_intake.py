#!/usr/bin/env python3
"""Private, non-agent admission and leased queue for saphid/frame-control only."""
import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import socket
import threading
import stat
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO = 'saphid/frame-control'
PROJECT = 343535
MAX_BODY = 65536
SCHEMA = '''CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, created INTEGER NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, lease TEXT, until INTEGER);
 CREATE TABLE IF NOT EXISTS dispatches (
 report_id TEXT PRIMARY KEY, lease TEXT NOT NULL, started INTEGER NOT NULL,
 outcome TEXT NOT NULL, status INTEGER);
 CREATE TABLE IF NOT EXISTS dispositions (
 report_id TEXT PRIMARY KEY, lease TEXT NOT NULL, finished INTEGER NOT NULL,
 disposition TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS reports_created ON reports(created);
 CREATE INDEX IF NOT EXISTS reports_fingerprint ON reports(fingerprint);'''


class Rejected(Exception):
    def __init__(self, status):
        self.status = status


class Queue:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript(SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def admit_standard(self, raw, message_id, timestamp, signatures, key, now=None):
        now = int(time.time()) if now is None else now
        if len(raw) > MAX_BODY:
            raise Rejected(413)
        if (not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', message_id or '')
                or not re.fullmatch(r'[0-9]{10}', timestamp or '')
                or abs(now - int(timestamp)) > 300
                or not signatures or len(signatures) > 4096):
            raise Rejected(401)
        expected = hmac.new(key, message_id.encode() + b'.' + timestamp.encode() + b'.' + raw,
                            hashlib.sha256).digest()
        valid = False
        for entry in signatures.split():
            version, sep, encoded = entry.partition(',')
            if version != 'v1' or not sep:
                continue
            try:
                candidate = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                continue
            valid |= hmac.compare_digest(expected, candidate)
        if not valid:
            raise Rejected(401)
        return self._admit_authenticated(raw, now)

    def admit(self, raw, timestamp, signature, key, now=None):
        now = int(time.time()) if now is None else now
        if len(raw) > MAX_BODY:
            raise Rejected(413)
        if not re.fullmatch(r'[0-9]{10}', timestamp or '') or abs(now - int(timestamp)) > 300:
            raise Rejected(401)
        expected = hmac.new(key, timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ''):
            raise Rejected(401)
        return self._admit_authenticated(raw, now)

    def _admit_authenticated(self, raw, now):
        try:
            body = json.loads(raw)
            if body['repository'] != REPO or type(body['project_id']) is not int or body['project_id'] != PROJECT:
                raise ValueError()
            event = body['event']
            name, props = event['event'], event['properties']
            event_id = str(uuid.UUID(event['uuid']))
            if name not in ('$exception', 'problem_report') or props['$lib'] != 'frame-control':
                raise ValueError()
            if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', props['app_version']):
                raise ValueError()
            if props['os'] not in ('Linux', 'macOS', 'Windows'):
                raise ValueError()
            if name == 'problem_report' and props.get('kind') != 'bug':
                raise ValueError()
            evidence = props.get('$exception_message') if name == '$exception' else props.get('message')
            if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 16000:
                raise ValueError()
            if name == '$exception':
                entries = props.get('$exception_list')
                if (not isinstance(props.get('$exception_type'), str) or not props['$exception_type'].strip()
                        or not isinstance(entries, list) or not 1 <= len(entries) <= 10
                        or not all(isinstance(e, dict) and isinstance(e.get('type'), str)
                                   and isinstance(e.get('value'), str) for e in entries)
                        or entries[0]['value'] != evidence
                        or entries[0]['type'] != props['$exception_type']):
                    raise ValueError()
            elif not isinstance(props.get('title'), str) or not props['title'].strip():
                raise ValueError()
            # Ignore arbitrary envelope instructions; preserve only event data for triage.
            payload = json.dumps({'repository': REPO, 'project_id': PROJECT, 'event': {'uuid': event_id, 'event': name, 'properties': props}}, allow_nan=False)
            fingerprint = hashlib.sha256(json.dumps([name, props.get('$exception_type'), evidence],
                                                    ensure_ascii=True).encode()).hexdigest()
        except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
            raise Rejected(422) from None
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Keep bounded history for quotas and replay suppression. Never prune active work.
            db.execute("DELETE FROM reports WHERE created < ? AND state IN ('done','dead')", (now - 30*86400,))
            if db.execute('SELECT 1 FROM reports WHERE id=? OR (fingerprint=? AND created>=?)',
                          (event_id, fingerprint, now - 7*86400)).fetchone():
                return 'duplicate'
            hour, day, active = db.execute("SELECT SUM(created>=?), SUM(created>=?), SUM(state IN ('pending','leased','held')) FROM reports",
                                           (now-3600, now-86400)).fetchone()
            if (hour or 0) >= 4 or (day or 0) >= 20 or (active or 0) >= 20:
                raise Rejected(429)
            db.execute('INSERT INTO reports(id,fingerprint,created,payload) VALUES(?,?,?,?)',
                       (event_id, fingerprint, now, payload))
        return 'accepted'

    def claim(self, now=None):
        now = int(time.time()) if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE reports SET state=CASE WHEN id IN (SELECT report_id FROM dispatches) THEN 'held' WHEN attempts>=3 THEN 'dead' ELSE 'pending' END, lease=NULL WHERE state='leased' AND until<=?", (now,))
            if db.execute("SELECT 1 FROM reports WHERE state IN ('leased','held') LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT * FROM reports WHERE state='pending' ORDER BY created,id LIMIT 1").fetchone()
            if row is None:
                return None
            lease = str(uuid.uuid4())
            db.execute("UPDATE reports SET state='leased', attempts=attempts+1, lease=?, until=? WHERE id=?",
                       (lease, now+7200, row['id']))
            return {'id': row['id'], 'lease': lease, 'expires': now+7200,
                    'untrusted_report': json.loads(row['payload'])}

    def inspect(self, report_id, lease, now=None):
        now = int(time.time()) if now is None else now
        with self.connect() as db:
            row = db.execute("SELECT payload FROM reports WHERE id=? AND lease=? AND state='leased' AND until>?",
                             (report_id, lease, now)).fetchone()
        if row is None:
            raise ValueError('invalid or expired lease')
        return {'untrusted_report': json.loads(row['payload'])}

    def finish(self, report_id, lease, now=None, disposition='completed'):
        if not isinstance(disposition, str) or not disposition.strip() or len(disposition) > 4000:
            raise ValueError('invalid disposition')
        now = int(time.time()) if now is None else now
        with self.connect() as db:
            if db.execute("UPDATE reports SET state='done',lease=NULL WHERE id=? AND lease=? AND state='leased' AND until>?",
                          (report_id, lease, now)).rowcount != 1:
                raise ValueError('invalid or expired lease')
            db.execute('INSERT INTO dispositions VALUES(?,?,?,?)',
                       (report_id, lease, now, disposition))


def load_key(path, standard=False):
    # Open without following symlinks, then validate the opened file (not a racy path stat).
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise ValueError('key must be an owner-only owned regular file')
        key = source.read(4097).strip()
    if len(key) > 4096:
        raise ValueError('key too long')
    if standard:
        if not key.startswith(b'whsec_'):
            raise ValueError('standard key must use whsec_ base64 format')
        try:
            key = base64.b64decode(key[6:], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('invalid standard key') from None
    if len(key) < 32:
        raise ValueError('key must contain at least 32 bytes')
    return key


def handler(queue, key, standard=False, request_deadline=5):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(request_deadline)
            # An inactivity timeout alone permits endless trickle requests. Shut the
            # socket down at an absolute deadline, including header and body reads.
            def expire():
                try:
                    self.request.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            self.deadline = threading.Timer(request_deadline, expire)
            self.deadline.daemon = True
            self.deadline.start()
            try:
                super().setup()
            except BaseException:
                self.deadline.cancel()
                raise

        def finish(self):
            try:
                super().finish()
            finally:
                self.deadline.cancel()

        def handle(self):
            try:
                super().handle()
            except OSError:
                pass  # Expected on deadline expiry or a disconnected sender.

        def log_message(self, *args):
            pass  # Never log reports, headers, or credentials.

        def do_POST(self):
            self.connection.settimeout(5)
            status = 400
            try:
                if self.path != '/intake':
                    raise Rejected(404)
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    raise Rejected(400)
                length = int(self.headers['Content-Length'])
                if not 0 < length <= MAX_BODY:
                    raise Rejected(413)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise Rejected(400)
                names = (('webhook-id', 'webhook-timestamp', 'webhook-signature') if standard
                         else ('X-Frame-Timestamp', 'X-Frame-Signature'))
                if any(len(self.headers.get_all(name, [])) != 1 for name in names):
                    raise Rejected(401)
                if standard:
                    result = queue.admit_standard(raw, *(self.headers.get(name) for name in names), key)
                else:
                    result = queue.admit(raw, *(self.headers.get(name) for name in names), key)
                status = 202 if result == 'accepted' else 200
            except Rejected as error:
                status = error.status
            except (ValueError, OSError, sqlite3.Error):
                status = 503
            self.send_response(status)
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    keys = serve.add_mutually_exclusive_group(required=True)
    keys.add_argument('--standard-key-file')
    keys.add_argument('--key-file', help='legacy custom X-Frame authentication')
    serve.add_argument('--port', type=int, default=8789)
    sub.add_parser('claim')
    inspect = sub.add_parser('inspect')
    inspect.add_argument('id')
    inspect.add_argument('lease')
    finish = sub.add_parser('finish')
    finish.add_argument('id')
    finish.add_argument('lease')
    finish.add_argument('--disposition', default='completed')
    args = parser.parse_args()
    os.umask(0o077)
    queue = Queue(args.db)
    if args.command == 'serve':
        try:
            key = load_key(args.standard_key_file or args.key_file, bool(args.standard_key_file))
        except (ValueError, OSError):
            parser.error('invalid private signing key file')
        HTTPServer(('127.0.0.1', args.port), handler(queue, key, bool(args.standard_key_file))).serve_forever()
    elif args.command == 'claim':
        print(json.dumps(queue.claim()))
    elif args.command == 'inspect':
        try:
            print(json.dumps(queue.inspect(args.id, args.lease)))
        except ValueError:
            parser.exit(1, 'invalid or expired lease\n')
    else:
        try:
            queue.finish(args.id, args.lease, disposition=args.disposition)
        except ValueError:
            parser.exit(1, 'invalid disposition or lease\n')


if __name__ == '__main__':
    main()
