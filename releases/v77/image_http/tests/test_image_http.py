import base64
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fap_image_http import ImageHTTPAdapter, ImageHTTPError


class ImageHTTPTests(unittest.TestCase):
    def transport(self, request, timeout_s, max_bytes):
        self.assertEqual(request.full_url, "https://provider.invalid/v1/image")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")
        body = json.loads(request.data.decode())
        self.assertEqual(body["prompt"], "small blue square")
        payload = json.dumps({"mime_type":"image/png", "data_base64":base64.b64encode(b"PNG-test").decode()}).encode()
        return 200, {"Content-Type":"application/json"}, payload

    def test_safe_success_boundary(self):
        with patch.dict(os.environ, {"FAP_IMAGE_TOKEN":"test-token"}, clear=False):
            result = ImageHTTPAdapter("https://provider.invalid/v1/image", token_env="FAP_IMAGE_TOKEN", transport=self.transport).generate("small blue square")
        self.assertEqual(result.mime_type, "image/png")
        self.assertEqual(result.data, b"PNG-test")
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_missing_secret_fails_closed_without_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ImageHTTPError, "credential unavailable"):
                ImageHTTPAdapter("https://provider.invalid/v1/image", token_env="FAP_IMAGE_TOKEN", transport=self.transport).generate("x")

    def test_rejects_insecure_or_embedded_credentials(self):
        for endpoint in ("http://provider.invalid/v1/image", "https://u:p@provider.invalid/v1/image"):
            with self.assertRaises(ValueError):
                ImageHTTPAdapter(endpoint, token_env="FAP_IMAGE_TOKEN")

    def test_non_success_and_oversize_fail_closed(self):
        with patch.dict(os.environ, {"FAP_IMAGE_TOKEN":"secret-value"}, clear=False):
            with self.assertRaises(ImageHTTPError) as cm:
                ImageHTTPAdapter("https://provider.invalid/v1/image", token_env="FAP_IMAGE_TOKEN", transport=lambda *a:(500, {}, b"secret-value")).generate("x")
            self.assertNotIn("secret-value", str(cm.exception))
            with self.assertRaisesRegex(ImageHTTPError, "byte limit"):
                ImageHTTPAdapter("https://provider.invalid/v1/image", token_env="FAP_IMAGE_TOKEN", max_bytes=8, transport=lambda *a:(200, {}, b"123456789")).generate("x")

    def test_invalid_mime_and_base64_fail_closed(self):
        def bad(mime, data):
            return lambda *a:(200, {}, json.dumps({"mime_type":mime,"data_base64":data}).encode())
        with patch.dict(os.environ, {"FAP_IMAGE_TOKEN":"x"}, clear=False):
            with self.assertRaisesRegex(ImageHTTPError, "MIME"):
                ImageHTTPAdapter("https://provider.invalid/x", token_env="FAP_IMAGE_TOKEN", transport=bad("text/plain", "eA==")).generate("x")
            with self.assertRaisesRegex(ImageHTTPError, "base64"):
                ImageHTTPAdapter("https://provider.invalid/x", token_env="FAP_IMAGE_TOKEN", transport=bad("image/png", "%%%" )).generate("x")


if __name__ == "__main__":
    unittest.main()
