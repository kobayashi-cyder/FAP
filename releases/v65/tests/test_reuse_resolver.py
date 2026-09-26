import unittest
from fap_autonomy.failure_analyzer import FailureClusterAnalyzer
from fap_autonomy.models import BenchmarkCase, BenchmarkResult
from fap_autonomy.priority_engine import CapabilityPriorityEngine
from fap_autonomy.reuse_resolver import CapabilityReuseResolver


class ReuseResolverTests(unittest.TestCase):
    def test_existing_math_skill_is_extended_when_present_in_failures(self):
        rows=[]
        for i in range(4):
            case=BenchmarkCase(str(i),'math','multi-step percentage word problem',metadata={'gap_path':['word_problem','quantity_relation','multi_step']})
            rows.append(BenchmarkResult(case,False,verified=True,metadata={'selected_skills':['math','reason']}))
        a=FailureClusterAnalyzer(); clusters=a.cluster(rows)
        d=CapabilityPriorityEngine().rank(CapabilityPriorityEngine().from_clusters(clusters,len(rows)))[0]
        r=CapabilityReuseResolver(a).assess(d,rows)
        self.assertEqual(r.mode,'extend_existing_skill')
        self.assertEqual(r.target_skill,'math')
