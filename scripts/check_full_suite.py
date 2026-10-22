"""Run the complete offline suite and reject silently skipped PDF coverage."""
import importlib.util
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
missing = [name for name in ("yaml", "docx", "pypdf", "pikepdf", "pdfplumber", "reportlab")
           if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("Install .[pdf] before the full suite; missing: " + ", ".join(missing))
suite = unittest.defaultTestLoader.discover(str(root / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)
passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped) - len(result.expectedFailures)
print(f"passed={passed} failed={len(result.failures)} errors={len(result.errors)} skipped={len(result.skipped)}")
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
