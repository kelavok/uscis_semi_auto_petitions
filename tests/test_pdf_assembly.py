import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.errors import LimitReachedError
from reportlab.pdfgen import canvas

from app.pdf_assembly import merge_pdfs, pdf_page_count


def _load_pikepdf_or_skip(test_case):
    try:
        import pikepdf  # type: ignore
    except (ImportError, OSError) as exc:
        test_case.skipTest(f"pikepdf is unavailable or blocked: {exc}")
    return pikepdf


def _make_pdf(path: Path, text: str) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, text)
    pdf.save()


class PdfAssemblyTests(unittest.TestCase):
    def test_stream_limit_does_not_block_lossless_assembly(self):
        pikepdf = _load_pikepdf_or_skip(self)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root/'source.pdf', root/'result.pdf'
            with pikepdf.Pdf.new() as pdf:
                page = pdf.add_blank_page()
                page.Contents = pdf.make_stream(b'q Q\n' * 1000)
                pdf.save(source, compress_streams=False)
            original = source.read_bytes()
            with patch('pypdf.filters.MAX_DECLARED_STREAM_LENGTH', 1000):
                with self.assertRaises(LimitReachedError):
                    PdfWriter().add_page(PdfReader(source).pages[0])
                merge_pdfs([source, source], target, number_from_page=2)
            with pikepdf.open(target) as pdf:
                self.assertEqual(len(pdf.pages), 2)
                self.assertEqual(pdf.pages[0].Contents.read_bytes(), b'q Q\n' * 1000)
            self.assertIn('2', PdfReader(target).pages[1].extract_text())
            self.assertEqual(original, source.read_bytes())

    def test_pypdf_fallback_runs_when_pikepdf_is_blocked(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first, second, target = root/'first.pdf', root/'second.pdf', root/'result.pdf'
            _make_pdf(first, "first source")
            _make_pdf(second, "second source")
            with patch("app.pdf_assembly._load_pikepdf", side_effect=ImportError("blocked")):
                merge_pdfs([first, second], target, strip_annotations=True, number_from_page=2)
                self.assertEqual(pdf_page_count(target), 2)
            reader = PdfReader(target)
            self.assertIn("first source", reader.pages[0].extract_text())
            self.assertIn("2", reader.pages[1].extract_text())

    def test_pypdf_fallback_runs_when_pikepdf_merge_fails(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first, target = root/'first.pdf', root/'result.pdf'
            _make_pdf(first, "first source")
            with patch("app.pdf_assembly._merge_pdfs_with_pikepdf", side_effect=ValueError("bad named destination")):
                merge_pdfs([first], target)
            self.assertEqual(pdf_page_count(target), 1)
            self.assertIn("first source", PdfReader(target).pages[0].extract_text())

    def test_failure_preserves_previous_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            target=root/'result.pdf'
            target.write_bytes(b'previous output')
            broken=root/'broken.pdf'
            broken.write_bytes(b'broken')
            with self.assertRaises(ValueError):
                merge_pdfs([broken], target)
            self.assertEqual(target.read_bytes(), b'previous output')
            self.assertFalse(list(root.glob('*.assembling.pdf')))
