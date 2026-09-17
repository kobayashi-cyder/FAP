import tempfile, unittest
from pathlib import Path
from fap_autonomy.activation import AtomicActivationManager
from fap_autonomy.post_activation_monitor import PostActivationMonitor
from fap_autonomy.provenance import PatchHistory
from fap_autonomy.v63_orchestrator import V63Orchestrator
from fap_autonomy.promotion_ledger import digest_tree

class FakeRegistry:
    def __init__(self,entry): self.entry=entry
    def get(self,_): return self.entry
class FakePipeline:
    def __init__(self,result): self.result=result
    def evaluate_once(self,**kw): return dict(self.result)

class OrchestratorTests(unittest.TestCase):
    def test_registered_candidate_activates_and_history_written(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); c=root/'c'; c.mkdir(); (c/'skill.py').write_text('x=1\n'); d=digest_tree(str(c))
            entry={'candidate_digest':d,'evidence':{'candidate_digest':d,'lifecycle':{'state':'consolidated'}}}
            o=V63Orchestrator(pipeline=FakePipeline({'registered':True,'status':'candidate_evaluated','candidate_digest':d,'lifecycle':{'state':'consolidated'}}),registry=FakeRegistry(entry),activation=AtomicActivationManager(str(root/'active.json'),str(root/'hist')),monitor=PostActivationMonitor(str(root/'m.db'),min_cases=2),history=PatchHistory(str(root/'history.jsonl')))
            r=o.evaluate_candidate(capability_id='c',artifact={'candidate_dir':str(c)},trial_id='t',baseline_dev_score=.5)
            self.assertIn('activation',r); self.assertEqual(len(o.history.read_all()),2)
