import tempfile, unittest
from pathlib import Path
from fap_autonomy.activation import AtomicActivationManager, ActivationError
from fap_autonomy.promotion_ledger import digest_tree

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=Path(self.td.name)
        self.mgr=AtomicActivationManager(str(self.root/'active.json'), str(self.root/'history'))
    def tearDown(self): self.td.cleanup()
    def candidate(self,name,body='x=1\n'):
        p=self.root/name; p.mkdir(); (p/'skill.py').write_text(body,encoding='utf-8'); return p
    def entry(self,p,state='consolidated'):
        d=digest_tree(str(p)); return {'candidate_digest':d,'evidence':{'candidate_digest':d,'lifecycle':{'state':state}}}
    def test_requires_consolidated(self):
        p=self.candidate('a')
        with self.assertRaises(ActivationError): self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(p)},registry_entry=self.entry(p,'shadow'))
    def test_rejects_digest_mismatch(self):
        p=self.candidate('a'); e=self.entry(p); (p/'skill.py').write_text('x=2\n',encoding='utf-8')
        with self.assertRaises(ActivationError): self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(p)},registry_entry=e)
    def test_activation_pointer_only(self):
        p=self.candidate('a'); r=self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(p)},registry_entry=self.entry(p))
        self.assertEqual(r['candidate_digest'],digest_tree(str(p))); self.assertEqual(self.mgr.current()['source_release'],'v63')
    def test_rollback_previous(self):
        a=self.candidate('a','x=1\n'); b=self.candidate('b','x=2\n')
        self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(a)},registry_entry=self.entry(a))
        self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(b)},registry_entry=self.entry(b))
        r=self.mgr.rollback(reason='regression'); self.assertEqual(r['candidate_digest'],digest_tree(str(a))); self.assertEqual(r['rollback_reason'],'regression')
    def test_no_previous_rollback_fails(self):
        p=self.candidate('a'); self.mgr.activate(capability_id='c',artifact={'candidate_dir':str(p)},registry_entry=self.entry(p))
        with self.assertRaises(ActivationError): self.mgr.rollback(reason='x')
