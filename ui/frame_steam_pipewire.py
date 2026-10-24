"""Local Linux helper for Steam's own desktop sharing; never a Frame client.

No portal grants/tokens are read or written. KDE owns the manual Revoke UI.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading

MODULE = 'kcm_app-permissions'
GUIDANCE = (
    'In KDE System Settings > Applications > Application Permissions, find the Steam entry '
    '(reported as Steam Linux Runtime 3.0). Under Screen sharing, choose Manage 1 Session '
    '(the count may differ), verify it belongs to Steam, then Revoke only that session. '
    'Do not use Revoke All or change another app. Retry Steam desktop sharing to choose a screen. '
    'If the entry is missing or ambiguous, stop; it can appear intermittently. '
    'If Application Permissions is missing on Ubuntu/Kubuntu, check whether your distribution '
    'provides kde-config-flatpak; the reporter needed that package and a reboot. '
    'Frame Control does not install packages or change permissions.'
)
_lock = threading.Lock()
_launch = None


class HelperError(RuntimeError):
    pass


def unavailable():
    if sys.platform != 'linux' or os.environ.get('FRAME_LOCAL') == '1':
        return 'This helper runs on your Linux PC, not the headset.'
    if os.geteuid() == 0:
        return 'Open Frame Control as your normal desktop user, not root.'
    if Path('/.flatpak-info').exists():
        return 'This sandbox cannot verify host Steam processes. Use a terminal on your PC.'
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_CLIENT'):
        return 'Open Frame Control in your local Wayland desktop session, not over SSH.'
    if (os.environ.get('XDG_SESSION_TYPE', '').lower() != 'wayland'
            or not os.environ.get('WAYLAND_DISPLAY') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        return 'A local Wayland desktop with its session bus is required. X11 and headless sessions are unsupported.'
    return ''


def status():
    reason = unavailable()
    return {'available': not reason, 'reason': reason, 'guidance': GUIDANCE}


def _steam_running(proc=Path('/proc')):
    """Fail closed if our process inventory cannot be read. No command execution.

    Include launch scripts and Flatpak Steam, not just the final Steam binary.
    Other users' processes are irrelevant to this user's Steam instance.
    """
    try:
        entries = list(proc.iterdir())
        if not any(p.name.isdecimal() for p in entries):
            raise OSError('empty process inventory')
        for p in entries:
            if not p.name.isdecimal():
                continue
            try:
                if p.stat().st_uid != os.geteuid():
                    continue
                comm = (p / 'comm').read_text().strip().lower()
                args = (p / 'cmdline').read_bytes().decode('utf-8', 'replace').split('\0')
            except FileNotFoundError:
                continue  # a process exited while scanning
            names = {Path(a).name.lower() for a in args if a}
            if (comm in {'steam', 'steamwebhelper', 'steam.sh'}
                    or names.intersection({'steam', 'steam.sh', 'steamwebhelper', 'com.valvesoftware.steam'})):
                return True
        return False
    except OSError as exc:
        raise HelperError('Cannot verify whether Steam is running. Exit Steam and launch '
                          'steam -pipewire yourself from a local terminal.') from exc


def _spawn(argv):
    try:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        raise HelperError('Could not start the local application. Check it is installed and opens '
                          'from your desktop. No permission was changed.') from exc


def _check_start(child):
    try:
        code = child.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return
    if code:
        raise HelperError('The local application exited with an error. Try opening it from your '
                          'desktop to see its error. No permission was changed.')


def action(body):
    global _launch
    kind = body.get('action')
    if kind not in ('launch', 'permissions'):
        raise HelperError('Unknown Steam helper action.')
    if body.get('confirmed') is not True:
        raise HelperError('Use the Steam helper button to request this action explicitly.')
    reason = unavailable()
    if reason:
        raise HelperError(reason)
    with _lock:
        if kind == 'launch':
            if (_launch is not None and _launch.poll() is None) or _steam_running():
                raise HelperError('Steam is already running or starting. Exit Steam using Steam > Exit '
                                  '(after saving games), then click Launch Steam with PipeWire again. '
                                  'Frame Control will not stop it or change an existing session.')
            steam = shutil.which('steam')
            if not steam:
                raise HelperError('No steam launcher was found on PATH. For a Flatpak-only install, '
                                  'exit Steam and run flatpak run com.valvesoftware.Steam -pipewire '
                                  'yourself from a local terminal. Nothing was launched.')
            _launch = _spawn([steam, '-pipewire'])
            _check_start(_launch)
            return {'launched': True, 'message': 'Requested Steam with -pipewire for this launch only. '
                    'Use Steam\'s desktop-in-headset flow; Steam and your desktop portal control the picker. '
                    'This does not confirm screen sharing started.'}

        # There is no portable verified mapping from Steam's runtime display name
        # to a portal restore token. Never guess an app ID or delete a grant.
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').upper().split(':')
        kcm = shutil.which('kcmshell6') if 'KDE' in desktop else None
        if not kcm:
            return {'reset': False, 'opened': False, 'message': 'No permission was changed. '
                    'KDE Application Permissions could not be opened automatically. ' + GUIDANCE}
        try:
            listing = subprocess.run([kcm, '--list'], capture_output=True, text=True, timeout=5,
                                     stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            listing = None
        if (listing is None or listing.returncode
                or not re.search(r'^\s*' + re.escape(MODULE) + r'\s+-', listing.stdout, re.M)):
            return {'reset': False, 'opened': False, 'message': 'No permission was changed. '
                    'The KDE Application Permissions module is unavailable. ' + GUIDANCE}
        child = _spawn([kcm, MODULE])
        _check_start(child)
        return {'reset': False, 'opened': True, 'message': 'Requested KDE Application Permissions. '
                'No permission was changed by Frame Control. ' + GUIDANCE}
