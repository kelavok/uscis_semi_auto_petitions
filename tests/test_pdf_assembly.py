import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import pikepdf
from pypdf import PdfReader, PdfWriter
from pypdf.errors import LimitReachedError
from app.pdf_assembly import merge_pdfs


class PdfAssemblyTests(unittest.TestCase):
    def test_stream_limit_does_not_block_lossless_assembly(self):
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
