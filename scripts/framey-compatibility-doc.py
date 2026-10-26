#!/usr/bin/env python3
"""Render the documentation from the same digest-scoped data used by the store."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(value):
    if isinstance(value, list):
        value = ', '.join(str(v) for v in value) or 'none detected'
    return str(value).replace('|', '&#124;').replace('\n', ' ').replace('<', '&lt;')


def render(data):
    counts = Counter(p['status'] for p in data['plugins'])
    lines = ['# Official Decky store compatibility with Framey', '',
        f"Snapshot: {data['checkedAtUtc']}; {len(data['plugins'])} current visible official plugins from {data['source']}.", '',
        'This table and both store views use [`ui/framey-compatibility.json`](../ui/framey-compatibility.json). '
        'Results apply only to the exact store ID, version and SHA-256. A changed digest/version is **unverified**. '
        'Regenerate this document with `python3 scripts/framey-compatibility-doc.py`; use `--check` in review.', '',
        f"**Works: {counts['works']} · Partial: {counts['partial']} · Broken: {counts['broken']} · N/A: {counts['na']}.**", '',
        '- **Works** requires verified useful plugin behavior with its real backend. Read the reason for the verified scope and remaining limits; it does not imply worn-VR verification.',
        '- **Partial** means a limited frontend/settings surface initialized or rendered. Backend-dependent functionality remains unverified; it is not an end-to-end success claim.',
        '- **Broken** means a concrete archive, frontend or Steam dependency blocks the audited version. An artificial backend/network denial alone is not evidence that the real backend is broken.',
        '- **N/A** means the plugin targets hardware or a display/UI surface that Framey does not provide. The store disables installation for these versions.', '',
        '## Verification limits', '',
        f"All exact archives were hash-checked and statically inspected. The local Chromium host used Framey commit `{data['hostCommit']}`, React 18.3.1 and an opaque `allow-scripts` iframe. "
        'Each frontend was attempted for 1.2 seconds, including React effects. All plugin backend calls, fetches and websockets were denied. '
        'Some plugins attempt mutating actions on mount; none reached a backend. Initialization (`ready`) does not guarantee React rendered, and delayed errors/actions may occur after the observation window. '
        'The JSON preserves initializer errors, capped console observations and attempted method names.', '',
        'The optional full-catalog fake-Frame audit exercises the real HTTP/SSH installer, receipt, frontend bytes and removal, '
        'or expected rejection. It uses a private disposable Compose project with all plugin backend execution stubbed. '
        'It checks archive transport and safeguards, not Python/native execution. Run it with:', '',
        '```sh',
        'python3 scripts/framey-audit-store.py --cache /tmp/framey-archives --output /tmp/framey-observations.json',
        'python3 scripts/framey-audit-fake.py --cache /tmp/framey-archives --output /tmp/framey-fake/results.json',
        'python3 scripts/framey-audit-browser.py --cache /tmp/framey-archives',
        '```', '',
        'Open the browser audit URL in local Chromium, run `runAudit()` and inspect/download `results`. All backend/network actions remain denied.', '',
        'The current published digests are pinned in the JSON; if the store changed, retain/download those exact archives for reproduction. '
        'Audit downloads permit larger ZIPs for inspection; production installer limits remain 50 MiB ZIP / 150 MiB unpacked / 30 MiB per member.', '',
        'After the VR job released the shared lock, this audit acquired it and used a private temporary Decky 3.3.0 ARM64 user service. '
        'Read-only ProtonDB `get_setting` and Steam Status `get_settings` calls succeeded through the live Steam CEF websocket. '
        'The service and private base were removed and the lock released; normal managed services stayed inactive, battery was 100 → 99, '
        'and no power setting was changed. [Redacted results](evidence/framey-official-backend-2026-10-25.json) '
        'record exactly what ran. A [2026-10-26 follow-up](evidence/framey-events-backend-2026-10-26.json) '
        'verified default Notebook drawing/save/reopen across a real backend restart and Simple Timer start/cancel, '
        'countdown/completion events, a visible toast and persisted recents/subtle mode. '
        'Only private test settings were written. Simple Timer remains partial because its own expired-timer startup '
        'raises a missing `timer_task` error; sound/suspend are unsupported. '
        'All other official backends remain unexecuted. '
        'The separate VR job proves Frame Control/sample compositor rendering, not any official plugin. '
        'No worn-VR official-plugin result is claimed. '
        'A [local UI follow-up](evidence/framey-ui-fallbacks-2026-10-26.json) rendered Pause Games and Tailscale Control settings '
        'with all backend/network actions denied; it does not verify process pausing or Tailscale changes. '
        'Earlier focused checks cover [ProtonDB](evidence/framey-browser-2026-10-25.md), '
        '[Steam Status/cache](evidence/framey-cache-browser-2026-10-25.md), '
        '[Storage Cleaner](evidence/framey-api-v1-browser-2026-10-25.md), and '
        '[legacy MusicControl](evidence/framey-legacy-2026-10-25.md).', '',
        '## Every current plugin', '',
        'The API column shows manifest / actual bundled frontend API. Many manifests say v1 while their bundle connects API2. '
        'Missing manifest API is labelled legacy; an unrecognized bundle is unknown. Globals and hardware are static signals, not exhaustive dependencies.', '',
        '| Plugin / version | Manifest / bundle API | Status | Reason | Verified by |',
        '| --- | --- | --- | --- | --- |']
    for p in data['plugins']:
        lines.append('| '+ ' | '.join(map(cell, [f"{p['id']}: {p['name']} {p['version']}",
            f"{p['api']} / {p['frontendApi']}", 'N/A' if p['status']=='na' else p['status'], p['reason'], p['verification']]))+' |')
    lines += ['', '## API, UI and backend inventory', '',
        'DFL includes exports imported through decky-frontend-lib / @decky/ui. Steam stores and router/toaster/QAM signals are listed separately. '
        'No signal means the static scan did not detect one, not that no dependency exists. Native binaries are classified by ELF machine or Windows MZ header; '
        'Python files and source links are preserved in the JSON.', '',
        '| Plugin | SteamClient methods | DFL / @decky/ui exports | Other Steam globals / UI surfaces | Backend | Hardware / OS signals |',
        '| --- | --- | --- | --- | --- | --- |']
    for p in data['plugins']:
        native = sorted({n['arch'] for n in p['native']})
        lines.append('| '+' | '.join(map(cell, [p['name'],p['steamClient'],p['dfl'],p['globals']+p.get('uiSurfaces',[]),
            p['backend']+('; '+', '.join(native) if native else ''),p['hardware']]))+' |')
    lines += ['', '## Native payload portability', '',
        'All published Linux native payloads in this snapshot are x86_64; no published aarch64 payload was found. '
        'The three Windows DLLs belong to Decky-Framegen. The installer still rejects these archives. '
        'Apart from the explicitly described LocalSend experiment, ARM64 builds were not attempted: the constraints below remain unresolved.', '',
        '| Plugin | Native payloads | ARM64 result / remaining blocker |', '| --- | --- | --- |']
    for p in data['plugins']:
        if p['native']:
            binaries = [n['file'].removeprefix(p['folder']+'/') for n in p['native']]
            if len(binaries)>5:
                binaries = binaries[:5]+[f"… {len(binaries)} total; full list in JSON"]
            lines.append('| '+' | '.join(map(cell,[p['name'],binaries,p['nativePort']]))+' |')
    lines += ['', '## Evidence and maintenance', '',
        'The canonical JSON contains full archive hashes, native paths, source URLs, frontend observations and fake-Frame outcomes. '
        'Store compatibility is advisory except known installation/hardware blockers; removal always remains available. '
        'A panel retains its compatibility reason after the initializer reports ready. Upstream fixes require a new digest-scoped audit. '
        'Do not mark a plugin works based on archive installation, fake backend replies or initializer completion.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT/'docs/framey-compatibility.md'
    expected = render(json.loads((ROOT/'ui/framey-compatibility.json').read_text(encoding='utf-8')))
    if args.check:
        if not output.exists() or output.read_text(encoding='utf-8') != expected:
            raise SystemExit('Compatibility documentation differs from canonical store data')
    else:
        output.write_text(expected, encoding='utf-8')


if __name__ == '__main__':
    main()
