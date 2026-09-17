import unittest
from fap_media.video_skill import VideoGenerationSkill, VideoRequest, Scene

class TestVideoSkill(unittest.TestCase):
    def test_deterministic_plan(self):
        req=VideoRequest((Scene("a",1.0),Scene("b",0.5)),fps=30)
        plan=VideoGenerationSkill().render_plan(req)
        self.assertEqual(plan["total_frames"],45)
        self.assertEqual(plan["scenes"][1]["start_frame"],30)

    def test_missing_renderer_is_explicit(self):
        result=VideoGenerationSkill().run(VideoRequest((Scene("a",1.0),)))
        self.assertEqual(result.status,"needs_provider")

if __name__=="__main__": unittest.main()
