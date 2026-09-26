from __future__ import annotations

from typing import Any, Dict


class V67CodeFactoryCoordinator:
    """Connect a non-executable Skill Factory request to the native repository coder.

    Promotion/activation remains owned by V62-V66 verification layers.
    """
    def __init__(self, *, code_factory, outbox):
        self.code_factory = code_factory
        self.outbox = outbox

    def generate(self, request_record: Dict[str, Any], *, source_repo: str, test_command, objective: str,
                 initial_generation=None):
        req = request_record.get('request') or request_record
        if (req.get('metadata') or {}).get('executable', True):
            raise ValueError('V67 accepts only non-executable generation requests')
        task_id = request_record.get('request_sha256') or req.get('request_id') or req.get('capability_id')
        result = self.code_factory.run(task_id=str(task_id), source_repo=source_repo,
                                       test_command=list(test_command), objective=objective,
                                       initial_generation=initial_generation)
        if result.get('status') != 'candidate_ready':
            return result
        manifest = result['manifest']
        published = self.outbox.publish_candidate_manifest(request_sha256=str(task_id), manifest=manifest)
        return {'status': 'candidate_published', 'generation': result, 'published': published}
