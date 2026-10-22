"""Clipboard search paths must not depend on the operating system running the UI."""
import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.web import _case_search_query


class CaseSearchPathTests(unittest.TestCase):
    def test_windows_clipboard_path_under_posix_path_rules(self):
        root = Path("C:/Cases/example")
        with patch("app.web.Path", PurePosixPath):
            self.assertEqual(
                _case_search_query(r'"C:\Cases\example\source_documents\Evidence.docx"', root),
                "source_documents/evidence.docx",
            )

    def test_windows_drive_paths_support_quotes_slashes_unicode_and_case(self):
        root = Path("C:/Cases/Example Case")
        for value in (
            r'"C:\Cases\Example Case\source_documents\originals\Награда.docx"',
            "'C:/Cases/Example Case/source_documents/originals/Награда.docx'",
            r'«"c:\CASES\EXAMPLE CASE\source_documents\originals\Награда.docx"»',
        ):
            with self.subTest(value=value):
                self.assertEqual(_case_search_query(value, root), "source_documents/originals/награда.docx")

    def test_windows_paths_from_other_cases_or_drives_keep_their_prefix(self):
        root = Path("C:/Cases/example")
        for value in ("C:/Cases/example_other/evidence.pdf", "D:/Cases/example/evidence.pdf", "C:/Cases/other/evidence.pdf"):
            with self.subTest(value=value):
                self.assertEqual(_case_search_query(value, root), value.casefold())

    def test_unc_clipboard_path_is_relative_only_within_the_same_case(self):
        root = Path("//server/share/Example Case")
        self.assertEqual(_case_search_query(r'"\\server\share\Example Case\originals\Evidence.pdf"', root), "originals/evidence.pdf")
        outside = r"\\server\other-share\Example Case\Evidence.pdf"
        self.assertEqual(_case_search_query(outside, root), outside.replace("\\", "/").casefold())

    def test_native_absolute_and_relative_search_paths_are_preserved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "Case With Spaces"
            inside = root / "source_documents" / "Evidence.pdf"
            self.assertEqual(_case_search_query(f'"{inside}"', root), "source_documents/evidence.pdf")
            self.assertEqual(_case_search_query(" source_documents/Evidence.pdf ", root), "source_documents/evidence.pdf")
            self.assertEqual(_case_search_query(" A title in quotes ", root), "a title in quotes")
