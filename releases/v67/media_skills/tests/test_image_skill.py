import unittest
from fap_media.image_skill import ImageRequest, ImageGenerationSkill
from fap_media.contracts import MediaArtifact

class Provider:
    def generate_image(self, request):
        return MediaArtifact("image", "image/png", b"\x89PNGx")

class TestImageSkill(unittest.TestCase):
    def test_missing_provider_is_explicit(self):
        self.assertEqual(ImageGenerationSkill().run(ImageRequest("dog")).status, "needs_provider")

    def test_provider_artifact(self):
        result = ImageGenerationSkill(Provider()).run(ImageRequest("dog"))
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.artifact.mime_type.startswith("image/"))

    def test_bad_dimensions(self):
        with self.assertRaises(ValueError):
            ImageRequest("x", width=10).validate()

if __name__ == "__main__":
    unittest.main()
