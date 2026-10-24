"""Offline, accessible power report. No network requests or external resources."""
import base64
import html
import json


def render(report, csv_text):
    def esc(value):
        return html.escape(str(value), quote=True)

    def download(text, mime, filename, label):
        data = base64.b64encode(text.encode('utf-8')).decode('ascii')
        return f'<a download="{filename}" href="data:{mime};base64,{data}">{label}</a>'

    rows = []
    for metric, item in report['summary'].items():
        numeric = 'mean' in item
        values = [item.get(key) for key in ('min', 'mean', 'max', 'last')]
        cells = ''.join(f'<td>{esc(value) if value is not None else "Unknown"}</td>' for value in values)
        states = ', '.join(item.get('states', [])) or ('Numeric' if numeric else 'Unknown')
        rows.append(f'<tr><th scope="row">{esc(metric)}</th><td>{esc(item["unit"])}</td>'
                    f'{cells}<td>{item["available"]} / {item["unavailable"]}</td>'
                    f'<td>{esc(states)}</td><td>{esc(", ".join(item["sources"]))}</td></tr>')
    missing = sorted({g for sample in report['samples'] for g in sample['unavailableGroups']})
    json_text = json.dumps(report, allow_nan=False, indent=2)
    links = download(json_text, 'application/json', 'frame-power.json', 'Download JSON samples and summary')
    links += ' · ' + download(csv_text, 'text/csv', 'frame-power.csv', 'Download CSV samples')
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Frame power and heat report</title>
<style>body{{font:16px system-ui,sans-serif;line-height:1.5;margin:24px;color:#18212b;background:#fff}}
a{{color:#0645ad}}a:focus-visible{{outline:3px solid #0645ad;outline-offset:4px}}
table{{border-collapse:collapse;width:100%;min-width:1100px}}th,td{{padding:8px;text-align:left;border:1px solid #adb5bd}}
thead th,td{{white-space:nowrap}}th[scope=row]{{min-width:240px;max-width:300px;overflow-wrap:anywhere}}
td:last-child{{min-width:220px;max-width:300px;white-space:normal;overflow-wrap:anywhere}}
thead{{background:#edf1f5}}.scroll{{overflow:auto}}h1{{line-height:1.2}}</style>
<main><h1>Frame power and heat report</h1>
<p>Headset: {esc(report.get("headset", {}).get("alias", "frame"))}</p>
<p>{len(report['samples'])} of {report['requestedSamples']} requested samples received; target interval {esc(report['intervalSeconds'])} seconds.</p>
<p>Collection: {esc(report['stopped'] or 'Completed')}. Results describe only the samples received.</p>
<p>{links}</p>
<p>Unknown means missing, unreadable or invalid, never zero. Means exclude unknown values and are not time-weighted.
Battery watts: positive charging, negative discharge. C means °C, W watts, A amps, MHz megahertz, RPM revolutions per minute.
Raw readings have no inferred percentage or worn threshold. Rails overlap: do not sum them.</p>
<p>Unavailable sensor groups in one or more samples: {esc(', '.join(missing) or 'None reported')}.</p>
<div class="scroll" role="region" aria-label="Metric summary, scroll horizontally for all columns" tabindex="0">
<table><caption>Received measurements, with units and availability counts</caption>
<thead><tr><th scope="col">Metric</th><th scope="col">Unit</th><th scope="col">Min</th><th scope="col">Mean</th><th scope="col">Max</th><th scope="col">Last</th><th scope="col">Available / unknown</th><th scope="col">States</th><th scope="col">Sources</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p>Sensor accuracy is unverified. Suspect negative thermistors remain visible. No temperature safety limits,
energy use or battery-runtime estimates are inferred. JSON includes actual timing, OS builds and per-sample availability.</p>
<p>This file stays on your computer and works offline. Downloaded files contain sensor source paths and OS builds;
review them before sharing. No settings, services, security or passwords were changed.</p></main></html>'''
