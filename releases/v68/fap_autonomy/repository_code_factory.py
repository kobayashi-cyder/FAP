from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .code_lineage import CodeLineageLedger
from .native_patch_generator import NativePatchGenerator, GenerationError
from .patch_engine import RepositoryPatchApplier
from .repo_context import RepositoryContextBuilder


class CodeFactoryError(ValueError):
    pass


def digest_tree(root: str) -> str:
    base = Path(root).resolve(); h = hashlib.sha256()
    for p in sorted(base.rglob('*')):
        if p.is_symlink():
            raise CodeFactoryError('candidate contains symlink')
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if '__pycache__' in p.parts:
                continue
            h.update(rel.encode()); h.update(b'\0'); h.update(p.read_bytes()); h.update(b'\0')
    return h.hexdigest()


class LocalValidationRunner:
    """Validation transport for a pre-isolated workspace; not an OS security sandbox."""
    def __init__(self, timeout_seconds: float = 20.0):
        self.timeout_seconds = float(timeout_seconds)

    def run(self, command: List[str], *, cwd: str) -> Dict[str, Any]:
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise CodeFactoryError('test command must be argv list')
        exe = Path(command[0]).name.lower()
        if exe not in {Path(sys.executable).name.lower(), 'python', 'python3', 'py'}:
            raise CodeFactoryError('only Python validation commands are accepted')
        if '-c' in command:
            raise CodeFactoryError('python -c is forbidden')
        t0 = time.perf_counter()
        try:
            cp = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=self.timeout_seconds,
                                env={'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PATH':os.environ.get('PATH','')})
            return {'pass': cp.returncode == 0, 'returncode': cp.returncode,
                    'stdout': cp.stdout[-12000:], 'stderr': cp.stderr[-12000:], 'seconds': time.perf_counter()-t0}
        except subprocess.TimeoutExpired as e:
            return {'pass': False, 'returncode': None, 'stdout': (e.stdout or '')[-12000:] if isinstance(e.stdout,str) else '',
                    'stderr': 'timeout', 'seconds': self.timeout_seconds}


class NativeRepositoryCodeFactory:
    """V67 stage-1 repository coder.

    Produces candidate code in a quarantine workspace. It never modifies the source repository and never activates code.
    """
    def __init__(self, *, workspace_root: str, timeout_seconds: float = 20.0, max_rounds: int = 4,
                 max_patch_bytes: int = 256_000):
        self.workspace_root = Path(workspace_root); self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.runner = LocalValidationRunner(timeout_seconds)
        self.max_rounds = int(max_rounds)
        self.max_patch_bytes = int(max_patch_bytes)
        if self.max_rounds < 1:
            raise ValueError('max_rounds must be >=1')

    @staticmethod
    def _copy_repo(source: Path, dest: Path):
        for p in source.rglob('*'):
            if p.is_symlink():
                raise CodeFactoryError('source repository contains symlink')
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('.git','__pycache__','.venv','venv'))

    def run(self, *, task_id: str, source_repo: str, test_command: List[str], objective: str,
            initial_generation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        source = Path(source_repo).resolve()
        if not source.is_dir():
            raise CodeFactoryError('source repo missing')
        source_before = digest_tree(str(source))
        task_dir = Path(tempfile.mkdtemp(prefix=f'v67_{str(task_id)[:20]}_', dir=str(self.workspace_root)))
        candidate = task_dir / 'candidate'
        self._copy_repo(source, candidate)
        lineage = CodeLineageLedger(str(task_dir/'lineage.jsonl'))
        lineage.append('task_started', {'task_id': task_id, 'objective': objective, 'source_digest': source_before})

        applier = RepositoryPatchApplier(str(candidate), max_patch_bytes=self.max_patch_bytes)
        context = RepositoryContextBuilder().build(str(candidate))
        lineage.append('context_built', {'digest': context.digest, 'files': len(context.files)})
        patches = []
        if initial_generation:
            patch = NativePatchGenerator.generate_function(
                target_path=initial_generation['target_path'],
                function_spec=initial_generation['function_spec'],
                base_sha256=initial_generation.get('base_sha256'),
            )
            applied = applier.apply(patch); patches.append(applied)
            lineage.append('patch_applied', {'round': 0, **applied, 'reason': patch.reason})

        attempts = []
        for round_no in range(1, self.max_rounds + 1):
            run = self.runner.run(list(test_command), cwd=str(candidate))
            attempts.append(run)
            lineage.append('validation', {'round': round_no, 'pass': run['pass'], 'returncode': run['returncode'], 'seconds': run['seconds']})
            if run['pass']:
                final_digest = digest_tree(str(candidate))
                source_after = digest_tree(str(source))
                if source_after != source_before:
                    raise CodeFactoryError('source repository changed during generation')
                manifest = {
                    'schema': 1, 'kind': 'native_repository_code_candidate', 'executable': False,
                    'task_id': str(task_id), 'objective': str(objective), 'candidate_dir': str(candidate),
                    'candidate_digest': final_digest, 'source_digest': source_before, 'rounds': round_no,
                    'patches': patches, 'lineage_path': str(task_dir/'lineage.jsonl'),
                    'lineage_valid': lineage.validate(), 'validation': run,
                    'generator': 'v67_native_safe_ir_plus_diagnostic_repair',
                }
                lineage.append('candidate_ready', {'candidate_digest': final_digest, 'rounds': round_no})
                manifest['lineage_valid'] = lineage.validate()
                (task_dir/'candidate_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
                return {'status': 'candidate_ready', 'manifest': manifest, 'manifest_path': str(task_dir/'candidate_manifest.json')}
            failure = '\n'.join([run.get('stdout',''), run.get('stderr','')])
            context = RepositoryContextBuilder().build(str(candidate))
            try:
                patch = NativePatchGenerator.repair_missing_import(workspace=str(candidate), context=context, failure_text=failure)
            except GenerationError as e:
                lineage.append('repair_unavailable', {'round': round_no, 'error': str(e)})
                break
            applied = applier.apply(patch); patches.append(applied)
            lineage.append('repair_applied', {'round': round_no, **applied, 'reason': patch.reason})

        source_after = digest_tree(str(source))
        if source_after != source_before:
            raise CodeFactoryError('source repository changed during generation')
        return {
            'status': 'candidate_rejected', 'task_id': str(task_id), 'candidate_dir': str(candidate),
            'source_digest': source_before, 'candidate_digest': digest_tree(str(candidate)),
            'attempts': attempts, 'patches': patches, 'lineage_path': str(task_dir/'lineage.jsonl'),
            'lineage_valid': lineage.validate(), 'executable': False,
        }
