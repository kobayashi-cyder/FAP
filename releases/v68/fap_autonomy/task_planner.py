from __future__ import annotations

import ast
import keyword
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


class TaskPlanError(ValueError):
    pass


_ALLOWED_CALLS = {'abs', 'min', 'max', 'round'}
_BIN = {
    ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'div',
    ast.FloorDiv: 'floordiv', ast.Mod: 'mod', ast.Pow: 'pow',
}
_CMP = {ast.Eq:'eq', ast.NotEq:'ne', ast.Lt:'lt', ast.LtE:'le', ast.Gt:'gt', ast.GtE:'ge'}


def _ident(name: str) -> str:
    name = str(name).strip()
    if not name.isidentifier() or keyword.iskeyword(name) or name.startswith('__'):
        raise TaskPlanError(f'invalid identifier: {name}')
    return name


def _expr_to_ir(node: ast.AST, args: set[str]) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, float, bool)) or node.value is None:
            return node.value
        raise TaskPlanError('unsupported constant')
    if isinstance(node, ast.Name):
        if node.id not in args:
            raise TaskPlanError(f'unknown variable: {node.id}')
        return {'var': node.id}
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return {_BIN[type(node.op)]: [_expr_to_ir(node.left,args), _expr_to_ir(node.right,args)]}
    if isinstance(node, ast.Compare) and len(node.ops)==1 and len(node.comparators)==1 and type(node.ops[0]) in _CMP:
        return {_CMP[type(node.ops[0])]: [_expr_to_ir(node.left,args), _expr_to_ir(node.comparators[0],args)]}
    if isinstance(node, ast.IfExp):
        return {'if': {'cond': _expr_to_ir(node.test,args), 'then': _expr_to_ir(node.body,args), 'else': _expr_to_ir(node.orelse,args)}}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_CALLS and not node.keywords:
        return {'call': {'fn': node.func.id, 'args': [_expr_to_ir(x,args) for x in node.args]}}
    raise TaskPlanError(f'unsupported expression node: {type(node).__name__}')


def expression_text_to_ir(text: str, args: List[str]) -> Any:
    try:
        tree = ast.parse(str(text).strip(), mode='eval')
    except SyntaxError as e:
        raise TaskPlanError(f'invalid expression: {e}')
    return _expr_to_ir(tree.body, set(args))


@dataclass(frozen=True)
class TaskPlan:
    mode: str
    objective: str
    target_path: Optional[str] = None
    function_spec: Optional[Dict[str, Any]] = None
    keyword_aliases: Optional[Dict[str, str]] = None
    defaults: Optional[Dict[str, Any]] = None
    source: str = 'structured'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NaturalLanguageTaskPlanner:
    """Constrained NL/structured request -> non-executable TaskPlan.

    Natural-language grammar intentionally covers only explicit function contracts,
    e.g. `function add(a,b) = a+b in calc.py` or `関数 add(a,b) = a+b ファイル calc.py`.
    Everything else becomes a repair-only plan rather than fabricated code.
    """
    _FN = re.compile(r'(?:function|関数)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:=|returns?\s+|は\s*)(.+?)(?:\s+(?:in|into|to|file|ファイル)\s+([A-Za-z0-9_./-]+\.py))?\s*$', re.I)
    _PATH = re.compile(r'([A-Za-z0-9_./-]+\.py)')

    def plan(self, *, objective: str, structured: Optional[Dict[str, Any]] = None) -> TaskPlan:
        objective = str(objective).strip()
        if not objective and not structured:
            raise TaskPlanError('objective is required')
        if structured is not None:
            if not isinstance(structured, dict):
                raise TaskPlanError('structured request must be object')
            mode = str(structured.get('mode','repair')).strip()
            if mode not in {'create_function','repair'}:
                raise TaskPlanError('unsupported task mode')
            target = structured.get('target_path')
            fspec = structured.get('function_spec')
            if mode == 'create_function':
                if not isinstance(target,str) or not target.endswith('.py') or not isinstance(fspec,dict):
                    raise TaskPlanError('create_function requires target_path and function_spec')
            aliases = structured.get('keyword_aliases') or {}
            defaults = structured.get('defaults') or {}
            if not isinstance(aliases,dict) or not isinstance(defaults,dict):
                raise TaskPlanError('aliases/defaults must be objects')
            return TaskPlan(mode, objective, target, fspec, {str(k):str(v) for k,v in aliases.items()}, defaults, 'structured')

        m = self._FN.search(objective)
        if not m:
            return TaskPlan('repair', objective, source='natural_language')
        name = _ident(m.group(1))
        args = [_ident(x.strip()) for x in m.group(2).split(',') if x.strip()]
        if len(args) != len(set(args)):
            raise TaskPlanError('duplicate function args')
        expr = m.group(3).strip()
        target = m.group(4)
        if not target:
            paths = self._PATH.findall(objective)
            target = paths[-1] if paths else f'{name}.py'
        fspec = {'name':name,'args':args,'expression':expression_text_to_ir(expr,args),'doc':'Generated from constrained V68 TaskPlan.'}
        return TaskPlan('create_function', objective, target, fspec, {}, {}, 'natural_language')
