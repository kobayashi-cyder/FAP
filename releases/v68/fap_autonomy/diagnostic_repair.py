from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .ast_patch_planner import qualified_name_patch, reexport_symbol_patch, keyword_compatibility_patches, syntax_expected_colon_patch
from .native_patch_generator import NativePatchGenerator, GenerationError
from .patch_engine import PatchSet
from .repo_context import RepositoryContext


class DiagnosticRepairError(ValueError):
    pass


_TRACE = re.compile(r'File ["\'](.+?\.py)["\'], line \d+')
_NAME = re.compile(r"NameError: name ['\"]([A-Za-z_]\w*)['\"] is not defined")
_ATTR = re.compile(r"AttributeError: module ['\"]([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)['\"] has no attribute ['\"]([A-Za-z_]\w*)['\"]")
_IMPORT = re.compile(r"ImportError: cannot import name ['\"]([A-Za-z_]\w*)['\"] from ['\"]([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)['\"]")
_KW = re.compile(r"TypeError: ([A-Za-z_]\w*)\(\) got an unexpected keyword argument ['\"]([A-Za-z_]\w*)['\"]")
_SYNTAX_COLON = re.compile(r"SyntaxError: expected ':'")
_TRACE_LINE = re.compile(r'File [\"\'](.+?\.py)[\"\'], line (\d+)')


def _rel_trace(workspace: str, text: str) -> str:
    files=_TRACE.findall(text)
    if not files:
        raise DiagnosticRepairError('traceback target unavailable')
    root=Path(workspace).resolve();p=Path(files[-1])
    if p.is_absolute():
        try:return p.resolve().relative_to(root).as_posix()
        except ValueError: raise DiagnosticRepairError('trace outside workspace')
    return p.as_posix()


def _module_path(workspace: str, module: str) -> str:
    root=Path(workspace).resolve(); base=Path(*module.split('.'))
    for rel in (base.with_suffix('.py'), base/'__init__.py'):
        p=(root/rel).resolve()
        try:p.relative_to(root)
        except ValueError:continue
        if p.is_file() and not p.is_symlink():return rel.as_posix()
    raise DiagnosticRepairError(f'module file not found: {module}')


def _module_from_path(path: str) -> str:
    p=Path(path).with_suffix('');parts=list(p.parts)
    if parts and parts[-1]=='__init__':parts.pop()
    if not parts: raise DiagnosticRepairError('root init module unsupported')
    return '.'.join(parts)


class DiagnosticRepairPlanner:
    def candidates(self, *, workspace: str, context: RepositoryContext, failure_text: str,
                   keyword_aliases: Dict[str,str] | None = None) -> List[PatchSet]:
        text=str(failure_text); out=[]
        if _NAME.search(text):
            try: out.append(NativePatchGenerator.repair_missing_import(workspace=workspace,context=context,failure_text=text))
            except GenerationError: pass
            symbol=_NAME.findall(text)[-1]
            rel=_rel_trace(workspace,text)
            defs=[p for p in context.symbol_index.get(symbol,()) if p!=rel]
            if len(defs)==1:
                out.append(qualified_name_patch(workspace=workspace,target_path=rel,symbol=symbol,module=_module_from_path(defs[0])))
        m=_ATTR.search(text)
        if m:
            module,symbol=m.groups();defs=list(context.symbol_index.get(symbol,()))
            target=_module_path(workspace,module);defs=[p for p in defs if p!=target]
            if len(defs)==1:
                out.append(reexport_symbol_patch(workspace=workspace,target_path=target,symbol=symbol,source_module=_module_from_path(defs[0])))
        m=_IMPORT.search(text)
        if m:
            symbol,module=m.groups();defs=list(context.symbol_index.get(symbol,()));target=_module_path(workspace,module);defs=[p for p in defs if p!=target]
            if len(defs)==1:
                out.append(reexport_symbol_patch(workspace=workspace,target_path=target,symbol=symbol,source_module=_module_from_path(defs[0])))
        if _SYNTAX_COLON.search(text):
            matches=_TRACE_LINE.findall(text)
            if matches:
                raw,line=matches[-1];root=Path(workspace).resolve();p=Path(raw)
                if p.is_absolute():
                    try: rel=p.resolve().relative_to(root).as_posix()
                    except ValueError: rel=''
                else: rel=p.as_posix()
                if rel:
                    try: out.append(syntax_expected_colon_patch(workspace=workspace,target_path=rel,line_no=int(line)))
                    except Exception: pass
        m=_KW.search(text)
        if m and keyword_aliases:
            fn,kw=m.groups();defs=list(context.symbol_index.get(fn,()))
            if len(defs)==1:
                out.extend(keyword_compatibility_patches(workspace=workspace,target_path=defs[0],function_name=fn,unexpected_keyword=kw,aliases=keyword_aliases))
        uniq={}
        for p in out: uniq.setdefault(p.digest(),p)
        return list(uniq.values())
