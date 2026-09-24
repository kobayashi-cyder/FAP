from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from fap_repository_diff_minimizer import RepositoryDiffMinimizer
from fap_repository_executor import FileEdit


class RepositoryDiffMinimizerTests(unittest.TestCase):
    def test_prefers_smaller_verified_candidate_surface(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = "x = 1\ny = 2\n"
            (root / "a.py").write_text(source, encoding="utf-8")
            digest = sha256(source.encode()).hexdigest()
            small = (FileEdit(path="a.py", operation="modify", before_sha256=digest, content="x = 2\ny = 2\n"),)
            large = (FileEdit(path="a.py", operation="modify", before_sha256=digest, content="x = 2\ny = 3\nz = 4\n"),)
            index, footprint = RepositoryDiffMinimizer(root).choose_smallest((large, small))
            self.assertEqual(index, 1); self.assertEqual(footprint.total_changed_lines, 1)

    def test_stale_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "a.py").write_text("x=1\n", encoding="utf-8")
            edit = FileEdit(path="a.py", operation="modify", before_sha256="0"*64, content="x=2\n")
            with self.assertRaisesRegex(ValueError, "STALE_EDIT"):
                RepositoryDiffMinimizer(root).measure((edit,))

    def test_repository_escape_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for path in ("../escape.py", "/tmp/escape.py", "a/../../escape.py", "a\\..\\escape.py"):
                edit = FileEdit(path=path, operation="create", before_sha256="", content="x\n")
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "path|repository"):
                    RepositoryDiffMinimizer(root).measure((edit,))

    def test_create_contract_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); minimizer = RepositoryDiffMinimizer(root)
            with self.assertRaisesRegex(ValueError, "before hash"):
                minimizer.measure((FileEdit(path="a.py", operation="create", before_sha256="0"*64, content="x\n"),))
            with self.assertRaisesRegex(ValueError, "requires content"):
                minimizer.measure((FileEdit(path="a.py", operation="create", before_sha256="", content=None),))

    def test_unpaired_surrogate_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            edit = FileEdit(path="a.py", operation="create", before_sha256="", content="\ud800")
            with self.assertRaisesRegex(ValueError, "UTF-8"):
                RepositoryDiffMinimizer(td).measure((edit,))

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); target = root / "target.py"; target.write_text("x=1\n", encoding="utf-8")
            link = root / "link.py"
            try: link.symlink_to(target)
            except OSError: self.skipTest("symlinks unavailable")
            digest = sha256(target.read_bytes()).hexdigest()
            edit = FileEdit(path="link.py", operation="modify", before_sha256=digest, content="x=2\n")
            with self.assertRaisesRegex(ValueError, "symlink|unavailable"):
                RepositoryDiffMinimizer(root).measure((edit,))

    def test_crlf_normalization_counts_changed_lines(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = "".join(f"line {i}\r\n" for i in range(100))
            (root / "a.txt").write_bytes(source.encode())
            digest = sha256(source.encode()).hexdigest()
            edit = FileEdit(path="a.txt", operation="modify", before_sha256=digest, content=source.replace("\r\n", "\n"))
            footprint = RepositoryDiffMinimizer(root).measure((edit,))
            self.assertEqual(footprint.total_changed_lines, 100)
            self.assertGreater(footprint.total_changed_bytes, 0)

    def test_equal_size_replacement_counts_changed_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = "a" * 20000 + "\n"
            (root / "a.txt").write_text(source, encoding="utf-8")
            digest = sha256(source.encode()).hexdigest()
            edit = FileEdit(path="a.txt", operation="modify", before_sha256=digest, content="b" * 20000 + "\n")
            footprint = RepositoryDiffMinimizer(root).measure((edit,))
            self.assertEqual(footprint.total_byte_delta, 0)
            self.assertGreaterEqual(footprint.total_changed_bytes, 20000)
            self.assertGreater(footprint.score, 2.0)

    def test_symlink_directory_component_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); real = root / "real"; real.mkdir(); source = real / "a.py"
            source.write_text("x=1\n", encoding="utf-8")
            link = root / "link"
            try: link.symlink_to(real, target_is_directory=True)
            except OSError: self.skipTest("symlinks unavailable")
            digest = sha256(source.read_bytes()).hexdigest()
            edit = FileEdit(path="link/a.py", operation="modify", before_sha256=digest, content="x=2\n")
            with self.assertRaisesRegex(ValueError, "symlink path component"):
                RepositoryDiffMinimizer(root).measure((edit,))


if __name__ == "__main__": unittest.main()
