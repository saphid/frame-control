"""How compatibility reports turn into a verdict. The reports themselves live
in Frame Control's private database (ui/frame_compat_db.py, a Lakebed capsule
in compat-db/); this module is the pure logic shared by the build and the app.

A report: package, version, result (runs | crashes | install_failed |
instance_failed, from an automated test), rating (works | issues | broken, from
a person), notes, via (harness | probe | user), date, steamos, lepton, runtime.
Newest wins, and a person's rating beats an automated result.

An install_failed report saying the file had no arm64-v8a build (or needed a
newer Android) is about that one APK file, often the wrong per-ABI download of
an app that has an arm64 build, so it says nothing about the app and is left out.
"""
import re

FILE_FAULT = re.compile(r'no arm64-v8a build|needs Android API')


def about_app(r):
    """False for reports about one wrong APK file rather than the app itself."""
    return not (r.get('result') == 'install_failed' and not r.get('rating')
                and FILE_FAULT.search(r.get('notes') or ''))


def verdict(reports):
    """(verdict, summary lines) for one package's reports, or None."""
    reports = [r for r in reports or () if about_app(r)]
    if not reports:
        return None
    rs = sorted(reports, key=lambda r: r.get('date') or '')
    people = [r for r in rs if r.get('rating')]
    best = people[-1] if people else rs[-1]
    kind = best.get('rating') or best.get('result')
    v = {'works': 'works', 'runs': 'works', 'issues': 'maybe'}.get(kind, 'no')
    n_ok = sum((r.get('rating') or r.get('result')) in ('works', 'runs') for r in rs)
    lines = [f"Reported on a Frame {(best.get('date') or '')[:10]} (v{best.get('version')}): "
             f"{kind}{' – ' + best['notes'] if best.get('notes') else ''}"]
    if len(rs) > 1:
        lines.append(f'{len(rs)} reports, {n_ok} working')
    return v, lines


def by_package(reports):
    out = {}
    for r in reports:
        out.setdefault(r['package'], []).append(r)
    return out
