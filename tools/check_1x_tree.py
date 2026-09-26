#!/usr/bin/env python3
from __future__ import annotations
import re
import subprocess
import sys

LEGACY = re.compile(r'(^|[/_.-])[vV](?:[2-9]\\d+)(?=$|[/_.-])')
EXPLICIT = {
    '53',
    'FAP_DEVELOPMENT_CHAT_CONTEXT.md',
    'FAP_LATEST.md',
    'INTEGRATION_NOTES.md',
    'RUN_FAP_CHAT_LATEST.cmd',
    'RUN_FAP_CHAT_LATEST.ps1',
    'RUN_FAP_CHAT_LATEST.sh',
}

paths = subprocess.check_output(['git', 'ls-files'], text=True, encoding='utf-8').splitlines()
bad = sorted(p for p in paths if p in EXPLICIT or LEGACY.search(p))
if bad:
    print('legacy-versioned paths are not allowed in public 1.x:', file=sys.stderr)
    for path in bad:
        print(' -', path, file=sys.stderr)
    raise SystemExit(1)
print(f'1.x tree gate: PASS ({len(paths)} tracked paths)')
