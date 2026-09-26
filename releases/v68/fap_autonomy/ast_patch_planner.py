from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Dict

from .code_ir import FunctionIR
from .patch_engine import FilePatch, PatchSet


class ASTPatchError(ValueError):
    pass


def _base(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _target(root: str, rel: str) -> Path:
    base = Path(root).resolve(); p = (base/rel).resolve()
    try: p.relative_to(base)
    except ValueError: raise ASTPatchError('target escapes workspace')
    if p.exists() and p.is_symlink(): raise ASTPatchError('target symlink rejected')
    return p


def append_function_patch(*, workspace: str, target_path: str, function_spec: dict) -> PatchSet:
    p = _target(workspace,target_path)
    generated = FunctionIR.from_dict(function_spec).to_source()
    old = p.read_text(encoding='utf-8') if p.exists() else ''
    if old:
        try: tree=ast.parse(old)
        except SyntaxError as e: raise ASTPatchError(f'target syntax invalid: {e}')
        name = function_spec.get('name')
        if any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and getattr(n,'name',None)==name for n in tree.body):
            raise ASTPatchError(f'symbol already exists: {name}')
    sep = '' if not old or old.endswith('\n\n') else ('\n' if old.endswith('\n') else '\n\n')
    new = old + sep + generated
    compile(new,target_path,'exec')
    return PatchSet('append_generated_function',(FilePatch(target_path,new,_base(old) if p.exists() else None),))


def qualified_name_patch(*, workspace: str, target_path: str, symbol: str, module: str) -> PatchSet:
    p=_target(workspace,target_path)
    if not p.is_file(): raise ASTPatchError('target missing')
    old=p.read_text(encoding='utf-8')
    try: tree=ast.parse(old)
    except SyntaxError as e: raise ASTPatchError(str(e))
    alias = module.split('.')[-1]
    existing_import=False
    for n in tree.body:
        if isinstance(n,ast.Import):
            for a in n.names:
                if a.name==module and (a.asname or a.name.split('.')[-1])==alias: existing_import=True
    if not existing_import:
        tree.body.insert(0,ast.Import(names=[ast.alias(name=module,asname=None)]))
    class R(ast.NodeTransformer):
        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load) and node.id==symbol:
                return ast.copy_location(ast.Attribute(value=ast.Name(id=alias,ctx=ast.Load()),attr=symbol,ctx=ast.Load()),node)
            return node
    tree=R().visit(tree);ast.fix_missing_locations(tree)
    new=ast.unparse(tree).strip()+'\n';compile(new,target_path,'exec')
    return PatchSet(f'qualified_symbol:{symbol}',(FilePatch(target_path,new,_base(old)),))


def reexport_symbol_patch(*, workspace: str, target_path: str, symbol: str, source_module: str) -> PatchSet:
    p=_target(workspace,target_path)
    old=p.read_text(encoding='utf-8') if p.exists() else ''
    line=f'from {source_module} import {symbol}'
    if line in old.splitlines(): raise ASTPatchError('re-export already exists')
    try: tree=ast.parse(old or '')
    except SyntaxError as e: raise ASTPatchError(str(e))
    insert=0
    for n in tree.body:
        if isinstance(n,ast.Expr) and isinstance(getattr(n,'value',None),ast.Constant) and isinstance(n.value.value,str) and n.lineno==1:
            insert=getattr(n,'end_lineno',n.lineno);continue
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            insert=getattr(n,'end_lineno',n.lineno);continue
        break
    lines=old.splitlines();lines.insert(insert,line)
    new='\n'.join(lines)+'\n';compile(new,target_path,'exec')
    return PatchSet(f'reexport:{symbol}',(FilePatch(target_path,new,_base(old) if p.exists() else None),))


def keyword_compatibility_patches(*, workspace: str, target_path: str, function_name: str, unexpected_keyword: str,
                                  aliases: Dict[str,str]) -> list[PatchSet]:
    if unexpected_keyword not in aliases:
        return []
    old_name=aliases[unexpected_keyword]
    p=_target(workspace,target_path)
    if not p.is_file(): return []
    old=p.read_text(encoding='utf-8')
    try: tree=ast.parse(old)
    except SyntaxError: return []
    fn=next((n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function_name),None)
    if fn is None: return []
    args=[a.arg for a in fn.args.args]
    if old_name not in args or unexpected_keyword in args: return []

    ta=ast.parse(old); fa=next(n for n in ta.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function_name)
    for a in fa.args.args:
        if a.arg==old_name: a.arg=unexpected_keyword
    class Rename(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id==old_name: node.id=unexpected_keyword
            return node
    Rename().visit(fa);ast.fix_missing_locations(ta)
    na=ast.unparse(ta).strip()+'\n';compile(na,target_path,'exec')

    tb=ast.parse(old); fb=next(n for n in tb.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function_name)
    fb.args.kwonlyargs.append(ast.arg(arg=unexpected_keyword));fb.args.kw_defaults.append(ast.Constant(None))
    assign=ast.If(test=ast.Compare(ast.Name(unexpected_keyword,ast.Load()),[ast.IsNot()],[ast.Constant(None)]),
                  body=[ast.Assign([ast.Name(old_name,ast.Store())],ast.Name(unexpected_keyword,ast.Load()))],orelse=[])
    fb.body.insert(0,assign);ast.fix_missing_locations(tb)
    nb=ast.unparse(tb).strip()+'\n';compile(nb,target_path,'exec')
    b=_base(old)
    return [PatchSet(f'keyword_rename:{unexpected_keyword}',(FilePatch(target_path,na,b),)),
            PatchSet(f'keyword_alias:{unexpected_keyword}',(FilePatch(target_path,nb,b),))]


def syntax_expected_colon_patch(*, workspace: str, target_path: str, line_no: int) -> PatchSet:
    """Repair only the narrow, mechanically unambiguous `expected ':'` case."""
    p=_target(workspace,target_path)
    if not p.is_file(): raise ASTPatchError('syntax target missing')
    old=p.read_text(encoding='utf-8');lines=old.splitlines()
    if line_no < 1 or line_no > len(lines): raise ASTPatchError('syntax line outside file')
    raw=lines[line_no-1]; stripped=raw.strip()
    starters=('def ','async def ','if ','elif ','else','for ','while ','class ','try','except','finally','with ','match ','case ')
    if not stripped.startswith(starters) or stripped.endswith(':'):
        raise ASTPatchError('colon repair is not mechanically safe')
    lines[line_no-1]=raw.rstrip()+':'
    new='\n'.join(lines)+('\n' if old.endswith('\n') else '')
    compile(new,target_path,'exec')
    return PatchSet('syntax_expected_colon',(FilePatch(target_path,new,_base(old)),))
