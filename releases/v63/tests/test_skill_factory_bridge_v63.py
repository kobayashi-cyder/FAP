import json, tempfile, unittest
from pathlib import Path
from fap_autonomy.skill_factory_bridge import SkillFactoryOutputAdapter, SkillFactoryOutputError

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=Path(self.td.name); self.c=self.root/'c'; self.c.mkdir(); (self.c/'skill.py').write_text('x=1\n'); self.h=self.root/'h.jsonl'; self.h.write_text('{}\n')
    def tearDown(self): self.td.cleanup()
    def manifest(self,**kw):
        d={'capability_id':'c','candidate_dir':str(self.c),'unit_command':['python','-V'],'dev_command':['python','-V'],'holdout_command':['python','-V'],'holdout_paths':[str(self.h)]}; d.update(kw); p=self.root/'m.json'; p.write_text(json.dumps(d)); return p
    def test_valid_manifest(self):
        a=SkillFactoryOutputAdapter().load(str(self.manifest())); self.assertTrue(a['candidate_digest']); self.assertTrue(Path(a['candidate_dir']).is_absolute())
    def test_missing_rejected(self):
        p=self.root/'bad.json'; p.write_text('{}')
        with self.assertRaises(SkillFactoryOutputError): SkillFactoryOutputAdapter().load(str(p))
    def test_missing_holdout_rejected(self):
        with self.assertRaises(SkillFactoryOutputError): SkillFactoryOutputAdapter().load(str(self.manifest(holdout_paths=[])))
