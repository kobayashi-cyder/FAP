from __future__ import annotations
from typing import Any, Dict


class V68CodeFactoryCoordinator:
    def __init__(self, *, code_factory, outbox): self.code_factory=code_factory;self.outbox=outbox
    def generate(self, request_record:Dict[str,Any], *, source_repo:str, test_command, objective:str, structured=None):
        req=request_record.get('request') or request_record
        if (req.get('metadata') or {}).get('executable',True):raise ValueError('only non-executable requests accepted')
        task_id=request_record.get('request_sha256') or req.get('request_id') or req.get('capability_id')
        out=self.code_factory.run(task_id=str(task_id),source_repo=source_repo,test_command=list(test_command),objective=objective,structured=structured)
        if out.get('status')!='candidate_ready':return out
        published=self.outbox.publish_candidate_manifest(request_sha256=str(task_id),manifest=out['manifest'])
        return {'status':'candidate_published','generation':out,'published':published}
