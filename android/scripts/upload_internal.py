#!/usr/bin/env python3
"""Upload an already signed AAB to an existing Google Play internal-testing app.

The service account must have Release Manager access to this exact package.
Only CI's temporary files hold the credential; nothing is stored in the repo.
"""
import argparse
import json
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service-account', required=True, type=Path)
    parser.add_argument('--package', required=True)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--version-code', required=True, type=int)
    args = parser.parse_args()
    if not args.package or not args.bundle.is_file() or args.bundle.stat().st_size < 100_000:
        parser.error('An existing package name and signed AAB are required')
    credentials = service_account.Credentials.from_service_account_file(
        str(args.service_account), scopes=['https://www.googleapis.com/auth/androidpublisher'])
    api = build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)
    edit = api.edits().insert(packageName=args.package, body={}).execute()
    edit_id = edit['id']
    bundle = api.edits().bundles().upload(
        packageName=args.package, editId=edit_id,
        media_body=MediaFileUpload(str(args.bundle), mimetype='application/octet-stream', resumable=True)).execute()
    code = int(bundle['versionCode'])
    if code != args.version_code:
        raise SystemExit(f'Google Play returned versionCode {code}; expected {args.version_code}; edit not committed')
    api.edits().tracks().update(packageName=args.package, editId=edit_id, track='internal', body={
        'track': 'internal', 'releases': [{'versionCodes': [str(code)], 'status': 'completed'}],
    }).execute()
    api.edits().commit(packageName=args.package, editId=edit_id).execute()
    print(json.dumps({'package': args.package, 'track': 'internal', 'versionCode': code,
                      'bundleBytes': args.bundle.stat().st_size}, sort_keys=True))


if __name__ == '__main__':
    main()
