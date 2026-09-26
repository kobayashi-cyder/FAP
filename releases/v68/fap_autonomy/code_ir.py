from __future__ import annotations

import ast
import keyword
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


class CodeIRError(ValueError):
    pass


_ALLOWED_CALLS = {'abs', 'min', 'max', 'round'}
_ALLOWED_BIN = {
    'add': ast.Add, 'sub': ast.Sub, 'mul': ast.Mult, 'div': ast.Div,
    'floordiv': ast.FloorDiv, 'mod': ast.Mod, 'pow': ast.Pow,
}
_ALLOWED_CMP = {
    'eq': ast.Eq, 'ne': ast.NotEq, 'lt': ast.Lt, 'le': ast.LtE,
    'gt': ast.Gt, 'ge': ast.GtE,
}


def _ident(name: str) -> str:
    name = str(name)
    if not name.isidentifier() or keyword.iskeyword(name) or name.startswith('__'):
        raise CodeIRError(f'invalid identifier: {name}')
    return name


def _expr(obj: Any, allowed_vars: set[str]) -> ast.expr:
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return ast.Constant(obj)
    if not isinstance(obj, dict) or len(obj) != 1:
        raise CodeIRError('expression must be a scalar or single-key object')
    op, value = next(iter(obj.items()))
    if op == 'var':
        name = _ident(value)
        if name not in allowed_vars:
            raise CodeIRError(f'unknown variable: {name}')
        return ast.Name(id=name, ctx=ast.Load())
    if op in _ALLOWED_BIN:
        if not isinstance(value, list) or len(value) != 2:
            raise CodeIRError(f'{op} requires two operands')
        return ast.BinOp(_expr(value[0], allowed_vars), _ALLOWED_BIN[op](), _expr(value[1], allowed_vars))
    if op in _ALLOWED_CMP:
        if not isinstance(value, list) or len(value) != 2:
            raise CodeIRError(f'{op} requires two operands')
        return ast.Compare(_expr(value[0], allowed_vars), [_ALLOWED_CMP[op]()], [_expr(value[1], allowed_vars)])
    if op == 'if':
        if not isinstance(value, dict) or set(value) != {'cond', 'then', 'else'}:
            raise CodeIRError('if requires cond/then/else')
        return ast.IfExp(_expr(value['cond'], allowed_vars), _expr(value['then'], allowed_vars), _expr(value['else'], allowed_vars))
    if op == 'call':
        if not isinstance(value, dict):
            raise CodeIRError('call requires object')
        fn = str(value.get('fn', ''))
        if fn not in _ALLOWED_CALLS:
            raise CodeIRError('call is not whitelisted')
        args = value.get('args', [])
        if not isinstance(args, list):
            raise CodeIRError('call args must be list')
        return ast.Call(ast.Name(id=fn, ctx=ast.Load()), [_expr(x, allowed_vars) for x in args], [])
    raise CodeIRError(f'unsupported op: {op}')


@dataclass(frozen=True)
class FunctionIR:
    name: str
    args: List[str]
    expression: Any
    doc: str = ''

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> 'FunctionIR':
        if not isinstance(obj, dict):
            raise CodeIRError('function spec must be an object')
        name = _ident(obj.get('name', ''))
        args = [_ident(x) for x in obj.get('args', [])]
        if len(args) != len(set(args)):
            raise CodeIRError('duplicate arguments')
        return cls(name, args, obj.get('expression'), str(obj.get('doc', '')))

    def to_source(self) -> str:
        allowed = set(self.args)
        body = []
        if self.doc:
            body.append(ast.Expr(ast.Constant(self.doc)))
        body.append(ast.Return(_expr(self.expression, allowed)))
        fn = ast.FunctionDef(
            name=self.name,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=a) for a in self.args], vararg=None,
                               kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=body, decorator_list=[], returns=None, type_comment=None,
        )
        mod = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
        source = ast.unparse(mod).strip() + '\n'
        if any(x in source for x in ('TODO', 'NotImplementedError', '\n    pass\n')):
            raise CodeIRError('placeholder output is forbidden')
        compile(source, '<generated>', 'exec')
        return source
