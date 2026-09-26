#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

LEGACY_PATH = re.compile(r'(^|[/_.-])[vV](?:[2-9]\d+)(?=$|[/_.-])')
LEGACY_IMPORT = re.compile(
    r'(?m)^\s*(?:from\s+fap_v[2-9]\d*\b|import\s+fap_v[2-9]\d*\b)'
)
LEGACY_ANDROID = re.compile(
    r'\b(?:android-v[2-9]\d*|jp\.fap\.v[2-9]\d*)\b',
    re.I,
)
EXPLICIT = {
    '53',
    'FAP_DEVELOPMENT_CHAT_CONTEXT.md',
    'FAP_LATEST.md',
    'INTEGRATION_NOTES.md',
    'RUN_FAP_CHAT_LATEST.cmd',
    'RUN_FAP_CHAT_LATEST.ps1',
    'RUN_FAP_CHAT_LATEST.sh',
}
TEXT_SUFFIXES = {
    '.py', '.md', '.txt', '.json', '.jsonl', '.toml',
    '.yml', '.yaml', '.java', '.kt', '.kts', '.sh', '.ps1', '.cmd',
}

paths = subprocess.check_output(
    ['git', 'ls-files'],
    text=True,
    encoding='utf-8',
).splitlines()

bad_paths = sorted(
    path for path in paths
    if path in EXPLICIT or LEGACY_PATH.search(path)
)
if bad_paths:
    print('legacy-versioned paths are not allowed in public 1.x:', file=sys.stderr)
    for path in bad_paths:
        print(' -', path, file=sys.stderr)
    raise SystemExit(1)

bad_refs = []
for path in paths:
    candidate = Path(path)
    if candidate.suffix.lower() not in TEXT_SUFFIXES:
        continue
    try:
        text = candidate.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        continue
    if LEGACY_IMPORT.search(text) or LEGACY_ANDROID.search(text):
        bad_refs.append(path)

if bad_refs:
    print('legacy operational references are not allowed in public 1.x:', file=sys.stderr)
    for path in sorted(bad_refs):
        print(' -', path, file=sys.stderr)
    raise SystemExit(1)

print(
    f'1.x tree gate: PASS '
    f'({len(paths)} tracked paths; no legacy paths/imports/android refs)'
)
