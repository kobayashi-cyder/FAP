from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Optional

from .code_ir import FunctionIR
from .patch_engine import FilePatch, PatchSet
from .repo_context import RepositoryContext


class GenerationError(ValueError):
    pass


_TRACE_FILE = re.compile(r'File ["\'](.+?\.py)["\'], line \d+')
_NAME_ERROR = re.compile(r"NameError: name ['\"]([A-Za-z_]\w*)['\"] is not defined")


def _module_from_path(path: str) -> str:
    p = Path(path)
    parts = list(p.with_suffix('').parts)
    if parts and parts[-1] == '__init__':
        parts.pop()
    if not parts:
        raise GenerationError('cannot import repository root __init__')
    return '.'.join(parts)


class NativePatchGenerator:
    """Constrained native generator: safe-IR source synthesis + deterministic missing-import repair."""

    @staticmethod
    def generate_function(*, target_path: str, function_spec: dict, base_sha256: Optional[str] = None) -> PatchSet:
        if not str(target_path).endswith('.py'):
            raise GenerationError('generated target must be .py')
        source = FunctionIR.from_dict(function_spec).to_source()
        return PatchSet('safe_ir_function_generation', (FilePatch(str(target_path), source, base_sha256),))

    @staticmethod
    def repair_missing_import(*, workspace: str, context: RepositoryContext, failure_text: str) -> PatchSet:
        names = _NAME_ERROR.findall(str(failure_text))
        files = _TRACE_FILE.findall(str(failure_text))
        if not names or not files:
            raise GenerationError('no supported NameError diagnostic found')
        symbol = names[-1]
        raw_target = files[-1].replace('\\', '/')
        root = Path(workspace).resolve()
        target = Path(raw_target)
        if target.is_absolute():
            try:
                rel = target.resolve().relative_to(root).as_posix()
            except ValueError:
                raise GenerationError('traceback target outside workspace')
        else:
            rel = Path(raw_target).as_posix()
        candidates = [p for p in context.symbol_index.get(symbol, ()) if p != rel]
        if len(candidates) != 1:
            raise GenerationError(f'symbol {symbol} must resolve uniquely; got {len(candidates)} definitions')
        source_path = candidates[0]
        dest = (root / rel).resolve()
        try:
            dest.relative_to(root)
        except ValueError:
            raise GenerationError('target escapes workspace')
        if not dest.is_file() or dest.is_symlink():
            raise GenerationError('target file missing or symlink')
        old = dest.read_text(encoding='utf-8')
        module = _module_from_path(source_path)
        import_line = f'from {module} import {symbol}'
        if import_line in old.splitlines():
            raise GenerationError('required import already exists')
        try:
            tree = ast.parse(old)
        except SyntaxError as e:
            raise GenerationError(f'target syntax invalid before repair: {e}')
        insert_after = 0
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant) and isinstance(node.value.value, str) and node.lineno == 1:
                insert_after = getattr(node, 'end_lineno', node.lineno)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                insert_after = getattr(node, 'end_lineno', node.lineno)
                continue
            break
        lines = old.splitlines()
        lines.insert(insert_after, import_line)
        new = '\n'.join(lines) + ('\n' if old.endswith('\n') or not lines else '\n')
        compile(new, rel, 'exec')
        base = hashlib.sha256(old.encode('utf-8')).hexdigest()
        return PatchSet(f'missing_import:{symbol}', (FilePatch(rel, new, base),))
