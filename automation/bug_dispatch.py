#!/usr/bin/env python3
"""One local poll; only an admitted job can wake the configured T3 webhook."""
import argparse
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit

from bug_intake import Queue, REPO


def private_file(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('configuration and key must be owned private regular files')
    return path


def load_config(path):
    config = json.loads(private_file(path).read_text())
    if set(config) != {'repository', 'checkout', 'database', 'lock', 'webhook_url', 'key_file'}:
        raise ValueError('invalid configuration fields')
    if config['repository'] != REPO:
        raise ValueError('wrong repository')
    for field in ('checkout', 'database', 'lock', 'key_file'):
        if not Path(config[field]).is_absolute():
            raise ValueError('paths must be absolute')
    url = urlsplit(config['webhook_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('webhook must be a fixed HTTPS URL')
    return config


def verify_checkout(path):
    def git(*args):
        return subprocess.check_output(['git', '-C', path, *args], stderr=subprocess.DEVNULL,
                                       timeout=10, text=True).strip()
    if git('remote', 'get-url', 'origin') not in (
            'https://github.com/saphid/frame-control.git', 'https://github.com/saphid/frame-control',
            'git@github.com:saphid/frame-control.git'):
        raise ValueError('wrong checkout remote')
    if git('status', '--porcelain'):
        raise ValueError('checkout must be clean')


def send(url, body, key):
    target = urlsplit(url)
    connection = http.client.HTTPSConnection(target.hostname, target.port or 443, timeout=15)
    try:
        connection.request('POST', target.path + ('?' + target.query if target.query else ''), body,
                           {'Content-Type': 'application/json',
                            'X-Hub-Signature-256': 'sha256=' + hmac.new(key, body, hashlib.sha256).hexdigest()})
        # Do not follow redirects or log/read a private response body.
        return connection.getresponse().status
    finally:
        connection.close()


def dispatch(queue, url, key, now=None, sender=send):
    now = int(time.time()) if now is None else now
    job = queue.claim(now)
    if job is None:
        return 'idle'
    # Commit BEFORE any network I/O. A crash here sacrifices availability, never retries a wake.
    with queue.connect() as db:
        db.execute('INSERT INTO dispatches VALUES(?,?,?,?,NULL)',
                   (job['id'], job['lease'], now, 'uncertain'))
    body = json.dumps({'id': job['id'], 'lease': job['lease']}, separators=(',', ':')).encode()
    status = None
    try:
        status = sender(url, body, key)
        outcome = 'accepted' if 200 <= status < 300 else 'rejected'
    except (OSError, http.client.HTTPException, ValueError):
        outcome = 'uncertain'
    with queue.connect() as db:
        db.execute('UPDATE dispatches SET outcome=?,status=? WHERE report_id=?',
                   (outcome, status, job['id']))
    return outcome


def main():
    import fcntl  # The systemd dispatcher runs on Linux; queue tests also run on Windows.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config = load_config(args.config)
        # The lock covers checkout checks, claim, journal and the entire bounded network request.
        with open(config['lock'], 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            verify_checkout(config['checkout'])
            queue = Queue(config['database'])
            key = private_file(config['key_file']).read_bytes().strip()
            if len(key) < 32:
                raise ValueError('operator key is too short')
            dispatch(queue, config['webhook_url'], key)
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError):
        # URLs, credentials, reports, and exception strings must never enter journal logs.
        parser.exit(1, 'dispatcher failed; inspect private configuration and queue locally\n')


if __name__ == '__main__':
    main()
