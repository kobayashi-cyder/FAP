from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ast_patch_planner import append_function_patch
from .candidate_race import CandidateRace
from .code_lineage import CodeLineageLedger
from .diagnostic_repair import DiagnosticRepairPlanner
from .patch_engine import RepositoryPatchApplier
from .repo_context import RepositoryContextBuilder
from .repository_code_factory import LocalValidationRunner, CodeFactoryError, digest_tree
from .task_planner import NaturalLanguageTaskPlanner


class V68CodeFactory:
    """TaskPlan -> competing AST/diagnostic patches -> verified candidate workspace."""
    def __init__(self, *, workspace_root: str, timeout_seconds: float=20.0, max_rounds: int=4, max_patch_bytes: int=256_000):
        self.root=Path(workspace_root);self.root.mkdir(parents=True,exist_ok=True)
        self.runner=LocalValidationRunner(timeout_seconds);self.max_rounds=int(max_rounds);self.max_patch_bytes=int(max_patch_bytes)
        if self.max_rounds < 1: raise ValueError('max_rounds must be >=1')
        self.task_planner=NaturalLanguageTaskPlanner();self.repairs=DiagnosticRepairPlanner();self.racer=CandidateRace(runner=self.runner,max_patch_bytes=max_patch_bytes)

    @staticmethod
    def _copy_repo(src:Path,dst:Path):
        for p in src.rglob('*'):
            if p.is_symlink():raise CodeFactoryError('source repository contains symlink')
        shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.git','__pycache__','.venv','venv'))

    def run(self, *, task_id:str, source_repo:str, test_command:List[str], objective:str, structured:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
        source=Path(source_repo).resolve()
        if not source.is_dir():raise CodeFactoryError('source repo missing')
        source_digest=digest_tree(str(source));task=Path(tempfile.mkdtemp(prefix=f'v68_{str(task_id)[:20]}_',dir=str(self.root)));cand=task/'candidate';self._copy_repo(source,cand)
        lineage=CodeLineageLedger(str(task/'lineage.jsonl'));plan=self.task_planner.plan(objective=objective,structured=structured)
        lineage.append('task_planned',{'task_id':task_id,'plan':plan.to_dict(),'source_digest':source_digest})
        applied=[]
        if plan.mode=='create_function':
            patch=append_function_patch(workspace=str(cand),target_path=plan.target_path,function_spec=plan.function_spec)
            a=RepositoryPatchApplier(str(cand),max_patch_bytes=self.max_patch_bytes).apply(patch);applied.append(a);lineage.append('initial_patch',{'reason':patch.reason,**a})
        attempts=[];races=[]
        for round_no in range(1,self.max_rounds+1):
            run=self.runner.run(list(test_command),cwd=str(cand));attempts.append(run);lineage.append('validation',{'round':round_no,'pass':run['pass'],'seconds':run['seconds']})
            if run['pass']:
                if digest_tree(str(source))!=source_digest:raise CodeFactoryError('source repository changed')
                manifest={'schema':2,'kind':'v68_repository_code_candidate','executable':False,'task_id':str(task_id),'objective':objective,'task_plan':plan.to_dict(),
                          'candidate_dir':str(cand),'candidate_digest':digest_tree(str(cand)),'source_digest':source_digest,'rounds':round_no,'patches':applied,'races':races,
                          'lineage_path':str(task/'lineage.jsonl'),'generator':'v68_taskplan_ast_diagnostic_candidate_race','validation':run}
                lineage.append('candidate_ready',{'candidate_digest':manifest['candidate_digest'],'rounds':round_no});manifest['lineage_valid']=lineage.validate()
                mp=task/'candidate_manifest.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
                return {'status':'candidate_ready','manifest':manifest,'manifest_path':str(mp)}
            failure='\n'.join([run.get('stdout',''),run.get('stderr','')]);ctx=RepositoryContextBuilder().build(str(cand))
            patches=self.repairs.candidates(workspace=str(cand),context=ctx,failure_text=failure,keyword_aliases=plan.keyword_aliases or {})
            if not patches:
                lineage.append('repair_unavailable',{'round':round_no});break
            race=self.racer.race(baseline_dir=str(cand),patches=patches,test_command=list(test_command));races.append(race['results']);lineage.append('candidate_race',{'round':round_no,'candidates':race['results']})
            winner=race['winner']
            if winner is None:break
            patch=patches[winner['index']];a=RepositoryPatchApplier(str(cand),max_patch_bytes=self.max_patch_bytes).apply(patch);applied.append(a);lineage.append('race_winner_applied',{'round':round_no,'reason':patch.reason,**a})
        if digest_tree(str(source))!=source_digest:raise CodeFactoryError('source repository changed')
        return {'status':'candidate_rejected','task_id':str(task_id),'task_plan':plan.to_dict(),'candidate_dir':str(cand),'candidate_digest':digest_tree(str(cand)),
                'source_digest':source_digest,'attempts':attempts,'patches':applied,'races':races,'lineage_path':str(task/'lineage.jsonl'),'lineage_valid':lineage.validate(),'executable':False}
