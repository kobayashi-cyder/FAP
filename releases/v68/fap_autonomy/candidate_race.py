from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .patch_engine import PatchSet, RepositoryPatchApplier
from .repository_code_factory import LocalValidationRunner, digest_tree


class CandidateRace:
    """Evaluate alternative patches on isolated copies and choose the smallest passing candidate."""
    def __init__(self, *, runner: LocalValidationRunner, max_patch_bytes: int = 256_000):
        self.runner=runner;self.max_patch_bytes=int(max_patch_bytes)

    def race(self, *, baseline_dir: str, patches: List[PatchSet], test_command: List[str]) -> Dict[str,Any]:
        base=Path(baseline_dir).resolve()
        results=[]
        for idx,patch in enumerate(patches):
            tmp=Path(tempfile.mkdtemp(prefix=f'v68_race_{idx}_',dir=str(base.parent)))
            cand=tmp/'candidate';shutil.copytree(base,cand)
            try:
                applied=RepositoryPatchApplier(str(cand),max_patch_bytes=self.max_patch_bytes).apply(patch)
                run=self.runner.run(list(test_command),cwd=str(cand))
                results.append({'index':idx,'patch':patch,'patch_digest':patch.digest(),'applied':applied,'run':run,
                                'candidate_digest':digest_tree(str(cand)),
                                'score':(1 if run['pass'] else 0,-applied['bytes'],-run['seconds'])})
            except Exception as e:
                results.append({'index':idx,'patch':patch,'patch_digest':patch.digest(),'error':str(e),'score':(-1,0,0)})
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        passing=[r for r in results if r.get('run',{}).get('pass')]
        if not passing:return {'winner':None,'results':self._serial(results)}
        winner=max(passing,key=lambda r:r['score'])
        return {'winner':winner,'results':self._serial(results)}

    @staticmethod
    def _serial(rows):
        out=[]
        for r in rows:
            x={k:v for k,v in r.items() if k!='patch'}
            x['reason']=r['patch'].reason
            out.append(x)
        return out
