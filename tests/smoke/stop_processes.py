"""Linux-only smoke cleanup helper, sent over SSH before deleting test files.

Only exact, reserved smoke title directories establish ownership. Never signal
by process name, process group, Steam app id, or a shared Wine/Proton prefix.
"""
import json
import os
from pathlib import Path
import signal
import sys
import time

IDS = frozenset(prefix + kind for prefix in ('fc_smoke_', 'fc-smoke-')
                for kind in ('arm64', 'x86_64', 'exe'))


def owned(pid, roots):
    """Require our uid and an exact cwd/exe or individual absolute argv path.

    /proc retains a deleted cwd/exe with ' (deleted)' appended. This also lets
    the final sweep catch an older run whose title was already removed.
    """
    proc = Path('/proc') / str(pid)
    try:
        if pid == os.getpid() or proc.stat().st_uid != os.getuid():
            return False
        state = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0]
        if state == 'Z':
            return False
        paths = []
        for key in ('cwd', 'exe'):
            try:
                paths.append(os.readlink(proc / key).removesuffix(' (deleted)'))
            except (FileNotFoundError, PermissionError):
                pass
        try:
            paths += os.fsdecode((proc / 'cmdline').read_bytes()).split('\0')
        except PermissionError:
            pass
        return any(path == root or path.startswith(root + '/')
                   for path in paths for root in roots)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False


def candidates(roots):
    return sorted(int(p.name) for p in Path('/proc').iterdir()
                  if p.name.isdigit() and owned(int(p.name), roots))


def stop(ids, grace=3):
    if not ids or not set(ids) <= IDS:
        raise ValueError('only reserved smoke title IDs may be stopped')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('safe smoke cleanup requires Linux Python with pidfd support')
    roots = [str(Path.home() / 'devkit-game' / gid) for gid in ids]
    stopped = set()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        # Re-scan while waiting: wrappers can spawn a child during shutdown.
        deadline = time.monotonic() + grace
        while True:
            pids = candidates(roots)
            if not pids:
                return {'stopped_pids': sorted(stopped)}
            for pid in pids:
                try:
                    fd = os.pidfd_open(pid)
                except ProcessLookupError:
                    continue
                try:
                    # Open first, then revalidate ownership. The handle cannot
                    # signal an unrelated process if this numeric PID is reused.
                    if owned(pid, roots):
                        try:
                            signal.pidfd_send_signal(fd, sig)
                            stopped.add(pid)
                        except ProcessLookupError:
                            pass
                finally:
                    os.close(fd)
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)
    left = candidates(roots)
    if left:
        raise RuntimeError(f'smoke processes survived cleanup: {left}')
    return {'stopped_pids': sorted(stopped)}


if __name__ == '__main__':
    print(json.dumps(stop(sys.argv[1:])))
