"""Mailing-list transport. Consent and the retry queue live in frame_contact.py.

The Cloudflare Pages endpoint stores addresses privately in D1. Override
FRAME_CONTROL_MAILING_LIST_URL to use a local server or a future provider adapter.
No analytics identifiers or machine details are sent through this integration.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = 'https://framecontrol.fun/api/mailing-list'


class SendError(Exception):
    pass


def submit(token, rev, email):
    """Set this copy's latest opt-in, or withdraw it with an empty email.

    token is a random capability, separate from analytics and contact IDs. The
    revision makes retries idempotent and prevents delayed joins undoing a removal.
    """
    url = os.environ.get('FRAME_CONTROL_MAILING_LIST_URL', DEFAULT_URL)
    body = json.dumps({'token': token, 'rev': rev, 'email': email,
                       'updates': bool(email)}).encode('utf-8')
    try:
        request = urllib.request.Request(url, data=body, headers={
            'Content-Type': 'application/json', 'User-Agent': 'Frame-Control-mailing-list'})
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.loads(response.read(1024))
            if response.status != 200 or not isinstance(answer, dict) or answer.get('ok') is not True:
                raise SendError('mailing list did not accept the change')
    except (OSError, ValueError, urllib.error.URLError) as err:
        raise SendError('could not reach the mailing list') from err
