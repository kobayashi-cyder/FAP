from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from .promotion_ledger import digest_tree


class RuntimeDispatchError(ValueError):
    pass


class SandboxRunner(Protocol):
    def execute(self, *, slot: str, request: Dict[str, Any]) -> Dict[str, Any]: ...


class ActiveRuntimeDispatcher:
    """Resolve a verified active slot without importing candidate code."""

    def __init__(self, active_state_path: str):
        self.path = Path(active_state_path)

    def _state(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {'schema': 1, 'active': {}}
        obj = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(obj, dict) or not isinstance(obj.get('active', {}), dict):
            raise RuntimeDispatchError('invalid active-state manifest')
        return obj

    def resolve(self, capability_id: str) -> Optional[Dict[str, Any]]:
        entry = (self._state().get('active') or {}).get(capability_id)
        if not entry:
            return None
        expected = str(entry.get('candidate_digest', ''))
        raw_slot = Path(str(entry.get('slot', '')))
        if len(expected) != 64 or not raw_slot.is_absolute() or not raw_slot.is_dir():
            raise RuntimeDispatchError('invalid active slot')
        if raw_slot.is_symlink() or any(p.is_symlink() for p in raw_slot.rglob('*')):
            raise RuntimeDispatchError('active slot contains symlink')
        slot = raw_slot.resolve()
        if digest_tree(str(slot)) != expected:
            raise RuntimeDispatchError('active slot digest mismatch')
        return dict(entry, slot=str(slot))

    @staticmethod
    def canary_bucket(request_id: str) -> float:
        value = int.from_bytes(hashlib.sha256(str(request_id).encode('utf-8')).digest()[:8], 'big')
        return value / float(2**64 - 1)

    def route(self, capability_id: str, *, request_id: str, canary_ratio: float = 1.0,
              baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ratio = float(canary_ratio)
        if not 0.0 <= ratio <= 1.0:
            raise ValueError('canary_ratio must be in 0..1')
        active = self.resolve(capability_id)
        use_active = active is not None and self.canary_bucket(request_id) < ratio
        return {'arm': 'active', 'entry': active} if use_active else {'arm': 'baseline', 'entry': baseline}


class SandboxedRuntimeBridge:
    """Pass only a verified slot to an injected trusted OS/container runner."""

    def __init__(self, dispatcher: ActiveRuntimeDispatcher, runner: SandboxRunner):
        self.dispatcher = dispatcher
        self.runner = runner

    def execute(self, capability_id: str, *, request_id: str, request: Dict[str, Any],
                canary_ratio: float = 1.0, baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        route = self.dispatcher.route(capability_id, request_id=request_id,
                                      canary_ratio=canary_ratio, baseline=baseline)
        if route['arm'] != 'active':
            return {'arm': 'baseline', 'result': None, 'entry': route.get('entry')}
        entry = route['entry']
        result = self.runner.execute(slot=entry['slot'], request=dict(request))
        return {'arm': 'active', 'result': result, 'entry': entry}
