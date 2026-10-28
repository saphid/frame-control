#!/usr/bin/env python3
"""Check a locked Frame smoke result against the exact release commit."""

import json
import re
import sys
from pathlib import Path


REQUIRED_STEPS = {
    'cleanup: leftovers from earlier runs',
    'devkit service: properties.json',
    'status',
    'cleanup: everything this run installed',
    *(f'{kind}: {action}' for kind in ('arm64', 'x86_64', 'exe')
      for action in ('install', 'launch', 'remove')),
}


def verify(result, commit):
    if not isinstance(result, dict):
        raise ValueError('smoke result is not an object')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('expected a full lowercase commit SHA-1')
    if result.get('source') != {'commit': commit, 'clean': True}:
        raise ValueError('smoke source is not the exact clean release commit')
    if result.get('lock_released') is not True:
        raise ValueError('smoke lock release was not recorded')
    steps = result.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('smoke steps are missing')
    names = [step.get('step') for step in steps if isinstance(step, dict)]
    if (len(names) != len(steps) or any(not isinstance(name, str) for name in names) or
            len(names) != len(set(names)) or not REQUIRED_STEPS.issubset(names)):
        raise ValueError('smoke steps are missing or duplicated')
    passed = sum(step.get('ok') is True and not step.get('skipped') for step in steps)
    if (passed != len(steps) or result.get('passed') != passed or
            result.get('skipped') != 0 or result.get('failed') != 0):
        raise ValueError('smoke contains a failed, skipped, or inconsistent step')
    state = result.get('preflight') or {}
    if (not isinstance(state, dict) or state.get('activity') != 3 or
            not isinstance(state.get('proximity'), list) or not state['proximity'] or
            any(type(value) not in (int, float) or value < 0 or value > 10
                for value in state['proximity']) or
            not isinstance(state.get('battery'), list) or not state['battery'] or
            any(type(value) is not int or value < 20 or value > 100
                for value in state['battery'])):
        raise ValueError('locked standby preflight is missing')


def main(argv):
    if len(argv) != 3:
        raise ValueError('usage: verify-frame-smoke-result.py RESULT.json RELEASE_COMMIT_SHA')
    result = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
    verify(result, argv[2])
    print(f'Frame smoke passed for clean release commit {argv[2]}')


if __name__ == '__main__':
    try:
        main(sys.argv)
    except (OSError, ValueError) as error:
        sys.exit(f'Frame smoke gate failed: {error}')
