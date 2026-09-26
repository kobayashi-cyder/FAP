import tempfile
import unittest
from pathlib import Path
from fap_autonomy.request_queue import SkillFactoryRequestQueue


class RequestQueueTests(unittest.TestCase):
    def test_atomic_deduplicated_non_executable_queue(self):
        with tempfile.TemporaryDirectory() as td:
            q=SkillFactoryRequestQueue(td)
            spec={'capability_id':'math_gap','metadata':{'executable':False},'x':1}
            a=q.enqueue(spec); b=q.enqueue(spec)
            self.assertTrue(a['queued'])
            self.assertTrue(b['duplicate'])
            self.assertEqual(len(list(Path(td).glob('*.json'))),1)

    def test_rejects_executable_payload(self):
        with tempfile.TemporaryDirectory() as td:
            q=SkillFactoryRequestQueue(td)
            with self.assertRaises(ValueError):
                q.enqueue({'capability_id':'bad','metadata':{'executable':True}})
