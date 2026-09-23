from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata


class PDFIngestError(RuntimeError):
    pass


def normalize_pdf_text(text: str) -> str:
    value = str(text or "")
    table = {code: str(code - 2) for code in range(2, 12)}
    value = value.translate(table)
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+\n", "\n", value)
    return value


@dataclass(frozen=True)
class PDFPage:
    number: int
    text: str
    image_path: str = ""


@dataclass(frozen=True)
class PDFDocument:
    source_path: str
    pages: tuple[PDFPage, ...]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\n\n".join(
            f"--- PAGE {page.number} ---\n{page.text}" for page in self.pages
        )

    def text_for_pages(self, first: int, last: int) -> str:
        rows = [
            page.text
            for page in self.pages
            if int(first) <= page.number <= int(last)
        ]
        return "\n\n".join(rows)


class PDFDocumentIngestor:
    def __init__(self, *, render_images: bool = False, dpi: int = 144) -> None:
        self.render_images = bool(render_images)
        self.dpi = max(72, min(300, int(dpi)))

    @staticmethod
    def available() -> tuple[bool, str]:
        required = ("pdfinfo", "pdftotext")
        missing = [name for name in required if shutil.which(name) is None]
        if missing:
            return False, "missing:" + ",".join(missing)
        return True, "poppler"

    @staticmethod
    def _page_count(path: Path) -> int:
        proc = subprocess.run(
            ["pdfinfo", str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        match = re.search(r"(?mi)^Pages:\s*(\d+)\s*$", proc.stdout)
        if not match:
            raise PDFIngestError("pdfinfo did not report a page count")
        return int(match.group(1))

    @staticmethod
    def _extract_page(path: Path, page: int) -> str:
        proc = subprocess.run(
            [
                "pdftotext",
                "-layout",
                "-enc",
                "UTF-8",
                "-f",
                str(page),
                "-l",
                str(page),
                str(path),
                "-",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return normalize_pdf_text(proc.stdout)

    def _render_page(self, path: Path, page: int, image_dir: Path) -> str:
        if shutil.which("pdftoppm") is None:
            return ""
        image_dir.mkdir(parents=True, exist_ok=True)
        prefix = image_dir / f"page-{page:03d}"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                "-png",
                "-r",
                str(self.dpi),
                str(path),
                str(prefix),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        candidate = prefix.with_suffix(".png")
        return str(candidate) if candidate.exists() else ""

    def read(self, path: str | Path, *, image_dir: str | Path | None = None) -> PDFDocument:
        src = Path(path).expanduser().resolve()
        if not src.is_file():
            raise PDFIngestError(f"PDF not found: {src}")
        if src.suffix.lower() != ".pdf":
            raise PDFIngestError("input is not a .pdf file")

        ok, detail = self.available()
        if not ok:
            raise PDFIngestError(detail)

        count = self._page_count(src)
        target_dir = Path(image_dir).expanduser().resolve() if image_dir else src.parent / (src.stem + "_pages")
        pages: list[PDFPage] = []
        for number in range(1, count + 1):
            text = self._extract_page(src, number)
            image_path = ""
            if self.render_images:
                image_path = self._render_page(src, number, target_dir)
            pages.append(PDFPage(number=number, text=text, image_path=image_path))
        return PDFDocument(source_path=str(src), pages=tuple(pages))
