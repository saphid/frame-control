"""Report a problem from inside Frame Control. Python stdlib only.

The page's Report a problem dialog shows the diagnostics below before anything
is sent, then this sends the report privately to Frame Control's PostHog
project as a `problem_report` event: only the maintainer can read it, and
nothing is published. It is sent whatever the analytics settings are, because
the person sends it deliberately. Diagnostics are scrubbed first
(frame_telemetry.scrub); the person's own words are sent as written.

An email address goes with a report only when the person ticks "may contact me with
follow-up questions" (contact_followup). Standing choices made in Settings are
frame_contact.py's `contact_consent` events; `contacts` lists them.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

import frame_contact
import frame_devices
import frame_host
import frame_link
import frame_telemetry

KINDS = ('bug', 'idea', 'question', 'other')
TEXT_MAX = 5000     # the person's own text, in JavaScript (UTF-16) units like the page's maxlength
DIAG_MAX = 8000     # the diagnostics block
LOG_LINES = 60
ACTIVITY_LINES = 25

frame = {}  # the Frame's last known SteamOS build, set by server.status()
link = None  # the connector (frame_link.Link), set by server.main; None on the Frame itself


def u16(s):
    """Length as the website's validator counts it (JavaScript strings are UTF-16)."""
    return len(s.encode('utf-16-le')) // 2


def cut(s, n):
    """s shortened to at most n UTF-16 units, never splitting a character."""
    while u16(s) > n:
        s = s[:max(0, len(s) - max(1, (u16(s) - n) // 2))]
    return s


def _log_tail():
    """The last lines of the server log the app writes (FRAME_CONTROL_LOG), newest first."""
    path = os.environ.get('FRAME_CONTROL_LOG')
    if not path:
        return []
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 64 * 1024))
            lines = f.read().decode('utf-8', 'replace').splitlines()
    except OSError:
        return []
    # Request lines ("GET /api/status ...") are noise; keep what went wrong.
    keep = [ln for ln in lines if ln.strip() and not ln.startswith(('GET ', 'POST '))]
    return list(reversed(keep[-LOG_LINES:]))


def ssh_path_kind(path):
    """What sort of ssh a path is, never the path itself (it can hold a user name)."""
    if not path:
        return "not found"
    p = str(path).replace("\\", "/").lower()
    for marks, kind in ((("/system32/openssh/", "/sysnative/openssh/"), "Windows OpenSSH (System32)"),
                        (("/program files/openssh",), "OpenSSH in Program Files"),
                        (("/git/",), "Git for Windows"), (("msys", "cygwin"), "MSYS2/Cygwin"),
                        (("/opt/homebrew/", "/usr/local/", "linuxbrew"), "Homebrew or /usr/local"),
                        (("/nix/",), "Nix")):
        if any(m in p for m in marks):
            return kind
    if p in ("/usr/bin/ssh", "/bin/ssh"):
        return "system OpenSSH"
    return "other"


def _ssh_on_path():
    """Every ssh on PATH, in the order they're found; the first is the one the app runs."""
    names = ("ssh.exe", "ssh") if frame_host.WINDOWS else ("ssh",)
    found, seen = [], set()
    for d in os.get_exec_path():
        for name in names:
            cand = os.path.join(d, name)
            key = os.path.normcase(os.path.abspath(cand))
            if key not in seen and os.path.isfile(cand):
                seen.add(key)
                found.append(cand)
                break
    return found


VERSION_RE = re.compile(r"\b((?:OpenSSH|Sun_SSH|dropbear)[\w.\-]*)(?:[, ]+((?:LibreSSL|OpenSSL) [\w.\-]+))?", re.I)


def ssh_version(path):
    """The version words of `ssh -V` (it prints to stderr), nothing else it says."""
    try:
        r = frame_host.run_ssh([path, "-V"], capture_output=True, stdin=subprocess.DEVNULL, text=True,
                               errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        return f"couldn't run it ({type(e).__name__})"
    m = VERSION_RE.search((r.stderr or "") + " " + (r.stdout or ""))
    return ", ".join(g for g in m.groups() if g) if m else f"unrecognised version (exit {r.returncode})"


def _ssh_check():
    path = shutil.which("ssh")
    if not path:
        return "SSH: no ssh on PATH"
    others = [ssh_path_kind(p) for p in _ssh_on_path()
              if os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(path))]
    others = [k for i, k in enumerate(others) if k not in others[:i]]
    return f"SSH: {ssh_path_kind(path)}, {ssh_version(path)}" + (f"; also on PATH: {', '.join(others)}" if others else "")


_ssh = {"thread": None, "line": None}
_ssh_lock = threading.Lock()
SSH_WAIT = 0.3  # how long a report preview waits for the ssh check (PATH can hold slow network drives)


def start_ssh_check():
    """Look for ssh once, in the background (server.main starts it), so a report never waits
    on PATH folders on slow or mapped drives."""
    def run():
        try:
            line = _ssh_check()
        except Exception as e:  # a report must still go out
            line = f"SSH: couldn't check ({type(e).__name__})"
        _ssh["line"] = line
    with _ssh_lock:
        if _ssh["thread"] is None:
            _ssh["thread"] = threading.Thread(target=run, name="report-ssh-check", daemon=True)
            _ssh["thread"].start()
        return _ssh["thread"]


def ssh_line():
    start_ssh_check().join(SSH_WAIT)
    return _ssh["line"] or "SSH: still being checked"


def config_line(alias):
    """Whether ~/.ssh/config has the managed block for the alias, and a hand-written Host for it."""
    try:
        text = frame_devices.ssh_config().read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "~/.ssh/config: missing"
    except OSError as e:
        return f"~/.ssh/config: can't read it ({type(e).__name__})"
    blocks = [b["alias"] for b in frame_devices.parse_blocks(text)]
    outside, inside = [], None
    for line in text.splitlines():
        m = frame_devices.BLOCK_RE.fullmatch(line.strip())
        if m:
            inside = m.group(1)
        elif inside and line.strip() == frame_devices.end_mark(inside):
            inside = None
        elif not inside:
            outside.append(line)
    own = any(alias in re.split(r"[\s=]+", ln.strip())[1:] for ln in outside
              if re.match(r"(?i)\s*host[\s=]", ln))
    return (f"~/.ssh/config: managed \"{alias}\" block {'yes' if alias in blocks else 'no'} "
            f"({len(blocks)} managed in all); hand-written \"Host {alias}\" {'yes' if own else 'no'}")


def connection_lines():
    """A short summary of the connector in fixed words only: states, stages, error categories,
    kinds of address, counts. No text from errors or ssh, and never an address."""
    if link is None:
        return ["Connection: no connector (this server doesn't reach a headset over SSH)"]
    snap = link.snapshot()
    active = link.active_device()
    alias = active.get("alias") or "?"
    phase, err, via = snap.get("phase") or "idle", snap.get("error"), snap.get("via")
    head = f"Connection: {phase}"
    if phase == "connected" and via:
        rtt = via.get("rtt_ms")
        head += f" via {frame_link.address_kind(via.get('host'), via.get('ip'))}" + (f" ({rtt:g} ms)" if rtt is not None else "")
    elif err:
        head += f" at {err.get('stage')}"
    head += f", attempt {snap.get('attempt') or 0}" + (f" ({snap['reason']})" if snap.get("reason") else "")
    lines = [head]
    kind = ("none set up" if active.get("none") else "a bare ssh alias" if active.get("transient")
            else f"saved, {len(active.get('addresses') or [])} address(es)")
    lines.append(f"Headsets: {len(link.reg.devices())} saved; active \"{alias}\" ({kind})")
    if err:
        lines.append(f"Error: {err.get('stage')}, {frame_link.failure_category(err.get('message'), err.get('raw'))}")
    last = link.last_failure
    if last:
        ago = max(0, int(frame_link.now() - last.get("at", 0)))
        lines.append(f"Last failure: {last.get('stage')}, {last.get('category')}, {ago // 60} min {ago % 60} s ago")
    lines.append(f"Addresses tried: {frame_link.probes_summary(snap.get('probes')) or 'none yet'}")
    net = snap.get("network")
    if net:
        ts = net.get("tailscale") or {}
        lines.append(f"Network: gateway {'yes' if net.get('gateway') else 'no'}, Tailscale "
                     f"{'on' if ts.get('up') else 'off' if ts.get('installed') else 'not installed'}")
    for part in (ssh_line, lambda: config_line(alias)):
        try:
            lines.append(part())
        except Exception as e:  # a report must still go out
            lines.append(f"({type(e).__name__} while checking SSH)")
    return lines


def diagnostics(activity=(), include_logs=False, limit=DIAG_MAX):
    """What a report includes, scrubbed and at most `limit` UTF-16 units. Always the versions
    and builds, and a connection summary (connection_lines: kinds of address and states, never
    the addresses, so "the app can't find the headset" can be told apart); recent activity and the server log only when asked for, since they can name
    files. Sections are filled in order of use, newest lines first, so trimming drops the oldest."""
    t = frame_telemetry.state()
    levels = ', '.join(f"{name} {'on' if on else 'off'}" for name, on in
                       (('usage', t['usage']), ('compat', t['compat']), ('error details', t['diagnostics'])))
    env = [
        f"Frame Control {frame_telemetry.app_version()}"
        f"{' (built app)' if os.environ.get('FRAME_CONTROL_PACKAGED') else ' (source checkout)'}",
        f"Computer: {frame_host.NAME} {platform.release()} {platform.machine()}, Python {'%d.%d.%d' % sys.version_info[:3]}",
        f"SteamOS: {frame.get('build') or 'unknown'} ({frame.get('version') or 'not connected since start'})",
        f"Analytics: {levels}",
        f"Report time: {time.strftime('%Y-%m-%d %H:%M %Z')}",
    ]
    try:
        conn = connection_lines()
    except Exception as e:  # never stop a report over its diagnostics
        conn = [f"Connection: summary unavailable ({type(e).__name__})"]
    out = frame_telemetry.scrub('\n'.join(env) + '\n\n' + '\n'.join(conn), limit=limit)
    if not include_logs:
        return cut(out, limit)
    sections = [('Recent activity (newest first):', [str(a)[:300] for a in list(activity)[:ACTIVITY_LINES] if isinstance(a, str)]),
                ('Server log (newest first):', _log_tail())]
    for title, lines in sections:
        if not lines:
            continue
        block = '\n\n' + title
        if u16(out + block) > limit:
            break
        out += block
        for line in lines:
            line = '\n' + frame_telemetry.scrub(line, 300)
            if u16(out + line) > limit:
                break
            out += line
    return out


def compose(body):
    """(title, text, diagnostics): the diagnostics exactly as the dialog previewed them (passed
    back, scrubbed again and bounded here)."""
    title = ' '.join(str(body.get('title') or '').split())
    text = str(body.get('message') or '').strip()
    if len(title) < 5:
        raise ValueError('give it a short title (at least 5 characters)')
    if len(text) < 10:
        raise ValueError('say a little more about what happened (at least 10 characters)')
    diag = body.get('diagnostics')
    diag = cut(frame_telemetry.scrub(diag, 40000), DIAG_MAX) if isinstance(diag, str) and diag.strip() else ''
    return cut(title, 120), cut(text, TEXT_MAX), diag


def send(body):
    """Send the report to PostHog. Returns {"id", "message"}; raises ReportError."""
    kind = body.get('kind') if body.get('kind') in KINDS else 'bug'
    title, text, diag = compose(body)
    followup = frame_contact.flag(body, 'contactFollowup')
    contact = str(body.get('contact') or '').strip() if followup else ''
    if followup and not frame_contact.valid_email(contact):
        raise ValueError('add your email address for follow-up questions, or untick that box')
    started = time.time()  # a removal from now on (even while saving the address) is redacted from the log
    # It becomes the contact email in Settings, where it's changed or removed like any other.
    contact_id, contact_rev = frame_contact.from_report(contact) if followup else ('', 0)
    ref = uuid.uuid4().hex[:8].upper()
    props = {**frame_telemetry.common(), 'kind': kind, 'title': title, 'message': text,
             'contact': contact, 'contact_followup': followup, 'diagnostics': diag,
             # Only with an address: a later change from this copy (higher rev) can take it back.
             'contact_id': contact_id, 'contact_rev': contact_rev,
             'report_id': ref, 'steamos': str(frame.get('build') or '')[:120], 'level': 'report'}
    # Its own random id: a report can carry contact details, so it isn't linked to this copy's analytics.
    event = {'event': 'problem_report', 'distinct_id': str(uuid.uuid4()), 'uuid': str(uuid.uuid4()),
             'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'properties': props}
    try:
        frame_telemetry.post([event], timeout=30)
    except frame_telemetry.SendError as e:
        raise ReportError(str(e))
    try:
        with frame_telemetry._lock:  # the lock a removal holds while wiping its address
            frame_contact.redact_removed(event, started)
            frame_telemetry.record_sent([event])
    except OSError:
        pass  # it was sent; failing to log it here mustn't make the person send it again
    return {'id': ref, 'message': f'Sent privately to the Frame Control developer (report {ref}).'}


class ReportError(RuntimeError):
    pass


def inbox(days=30):
    """The maintainer's recent reports from PostHog, newest first (needs the personal API key
    frame_compat_db.sync uses). Column 10 is whether the person may be asked follow-up
    questions now: 'withdrawn' when a later choice from the same copy took it back."""
    import frame_compat_db
    days = int(days)
    res = frame_compat_db._posthog_query(
        "SELECT timestamp, properties.report_id, properties.kind, properties.title, properties.message, "
        "properties.contact, properties.app_version, properties.os, properties.steamos, properties.diagnostics, "
        "properties.contact_followup, properties.contact_id, properties.contact_rev "
        f"FROM events WHERE event = 'problem_report' AND timestamp > now() - INTERVAL {days} DAY "
        "ORDER BY timestamp DESC LIMIT 200")
    rows = [r for r in res.get('results') or [] if isinstance(r, list) and len(r) == 13]
    if any(r[11] and _yes(r[10]) for r in rows):
        later = frame_compat_db._posthog_query(
            "SELECT distinct_id, properties.email, properties.followup, ifNull(toInt(properties.rev), 0) "
            "FROM events WHERE event = 'contact_consent' LIMIT 100000")
        mark_withdrawn(rows, later.get('results') or [])
    return rows


def mark_withdrawn(reports, consents):
    """Mark reports whose follow-up permission was taken back: the newest contact choice from
    the same copy made after the report (a higher rev than it carries, not a later clock) no
    longer agrees to follow-up questions at that address."""
    newest = {}
    for c in consents:
        if not isinstance(c, list) or len(c) != 4:
            continue
        cid, email, followup, rev = c
        try:
            rev = int(rev or 0)
        except (TypeError, ValueError):
            continue
        if rev > newest.get(str(cid), (-1,))[0]:
            newest[str(cid)] = (rev, str(email or ''), followup)
    for r in reports:
        if not (r[11] and _yes(r[10])):
            continue
        try:
            sent_at = int(r[12] or 0)
        except (TypeError, ValueError):
            sent_at = 0
        rev, email, followup = newest.get(str(r[11]), (-1, '', None))
        if rev > sent_at and not (_yes(followup) and email.strip().lower() == str(r[5] or '').strip().lower()):
            r[10] = 'withdrawn'


def _yes(v):
    return v is True or str(v).lower() in ('true', '1')


def contacts():
    """{'updates': [(email, since)], 'followup': [...]}: the addresses whose newest
    contact_consent event agrees to each, oldest first. A withdrawal, or a change to another
    address, replaces what came before, so withdrawn addresses are never listed. "Newest" is
    the highest rev from that copy (then time), so every field comes from the same event
    whatever order they arrived in or what the clocks said."""
    import frame_compat_db
    newest = "tuple(ifNull(toInt(properties.rev), 0), timestamp)"
    res = frame_compat_db._posthog_query(
        f"SELECT distinct_id, argMax(properties.email, {newest}), argMax(properties.updates, {newest}), "
        f"argMax(properties.followup, {newest}), argMax(timestamp, {newest}) FROM events "
        "WHERE event = 'contact_consent' GROUP BY distinct_id ORDER BY max(timestamp) LIMIT 100000")
    out = {'updates': [], 'followup': []}
    for row in res.get('results') or []:
        if not isinstance(row, list) or len(row) != 5:
            continue
        _, email, updates, followup, ts = row
        email = str(email or '').strip()
        if not frame_contact.valid_email(email):
            continue
        for kind, agreed in (('updates', updates), ('followup', followup)):
            if _yes(agreed):
                out[kind].append((email, str(ts or '')[:10]))
    return out


USAGE = 'usage: frame_report.py inbox [days] | contacts [updates|followup]'


def main():
    cmd, *args = sys.argv[1:] or ['inbox']
    if cmd == 'contacts':
        kinds = args[:1] or ['updates', 'followup']
        if not set(kinds) <= {'updates', 'followup'}:
            sys.exit(USAGE)
        found = contacts()
        for kind in kinds:
            print(f"== {'Release and update notices' if kind == 'updates' else 'Follow-up questions'}"
                  f" ({len(found[kind])})")
            for email, since in found[kind]:
                print(f"   {email}  (since {since})")
            print()
        return
    if cmd != 'inbox':
        sys.exit(USAGE)
    for row in inbox(*(args[:1] or [30])):
        ts, ref, kind, title, text, contact, version, osname, steamos, diag = (str(v or '') for v in row[:10])
        # Reports from before contact_followup existed only carried an address given for a reply.
        reply = contact and (row[10] is None or _yes(row[10]))
        print(f"== {ts[:16].replace('T', ' ')}  {ref}  [{kind}] {title}")
        print(f"   {version} on {osname}, SteamOS {steamos or 'unknown'}"
              f"{', may follow up at ' + contact if reply else ''}"
              f"{', follow-up permission since withdrawn' if row[10] == 'withdrawn' else ''}")
        print('   ' + text.replace('\n', '\n   '))
        if diag:
            print('   --- diagnostics\n   ' + diag.replace('\n', '\n   '))
        print()


if __name__ == '__main__':
    main()
