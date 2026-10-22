import csv
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import bundle_workflow as bundle, evidence, memo_builder, workflow
from stage0_support import SyntheticCase


class Stage0IntegrationTests(SyntheticCase):
    def complete_eb1a(self):
        self.create()
        memo_builder.apply_case_intake(self.case_id, {}, claimed_criteria=["awards"])
        self.source(text="Synthetic original award evidence")
        self.source(text="Synthetic English translation evidence", translation=True)
        evidence.scan_documents(self.case_id)
        evidence.link_translations(self.case_id)
        self.assertEqual(self.rows()[1]["parent_document_id"], self.rows()[0]["document_id"])
        prompt = workflow.build_prompt(self.case_id, "criterion_awards_episode", [], episode_id="1", episode_folder="1. Award")
        self.assertIn("Synthetic English translation evidence", prompt.read_text(encoding="utf-8"))
        self.import_payload()
        section = workflow.insert_section(self.case_id, "criterion_awards_episode", episode_id="1")
        self.assertTrue(section.exists())
        memo = memo_builder.build_working_memo(self.case_id)
        with zipfile.ZipFile(memo.docx_path) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                if name.endswith(".xml"):
                    ElementTree.fromstring(archive.read(name))
        bundle.build_exhibit_index(self.case_id)
        catalog = bundle.bundle_catalog(self.case_id)
        exhibits = [str(item["exhibit_number"]) for item in catalog]
        documents = [row["document_id"] for row in self.rows()]
        prepared = bundle.prepare_selected_bundle(self.case_id, exhibits, documents)
        self.assertGreater(prepared.separator_pdfs, 0)
        self.assertEqual(prepared.plan.missing_items, 0)
        return bundle.build_evidence_bundle(self.case_id), memo

    def test_eb1a_full_intake_to_docx_exhibit_separators_and_pdf(self):
        result, memo = self.complete_eb1a()
        reader = PdfReader(result.final_pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Synthetic original award evidence", text)
        self.assertIn("Synthetic English translation evidence", text)
        self.assertLess(text.index("Synthetic original award evidence"), text.index("Synthetic English translation evidence"))
        with result.plan_csv_path.open(encoding="utf-8-sig", newline="") as handle:
            items = list(csv.DictReader(handle))
        self.assertEqual(len(reader.pages), len(items))
        previous_docx = workflow.extract_docx_text(memo.docx_path)
        memo_builder.build_working_memo(self.case_id)
        self.assertEqual(workflow.extract_docx_text(memo.docx_path), previous_docx)
        self.assertEqual(previous_docx.count(self.payload()["draft_text"]), 1)

    def test_bundle_preflight_rejects_missing_corrupt_unsupported_and_preserves_pdf(self):
        result, _ = self.complete_eb1a()
        previous = result.final_pdf_path.read_bytes()
        original = self.case_dir / self.rows()[0]["file_path"]
        saved = original.read_bytes()
        original.unlink()
        with self.assertRaisesRegex(SystemExit, "missing, invalid or unsupported"):
            bundle.build_evidence_bundle(self.case_id)
        self.assertEqual(result.final_pdf_path.read_bytes(), previous)
        original.write_bytes(saved)
        separators = sorted((self.case_dir / "bundle/separators/pdf").glob("*.pdf"))
        separators[0].write_bytes(b"%PDF-1.4\n%%EOF\n")
        with self.assertRaises(SystemExit):
            bundle.build_evidence_bundle(self.case_id)
        self.assertEqual(result.final_pdf_path.read_bytes(), previous)
        self.assertEqual(bundle._source_document_status(separators[0])[0], "invalid_pdf")
        unsupported = self.root / "synthetic.xlsx"
        unsupported.write_bytes(b"synthetic unsupported format")
        self.assertEqual(bundle._source_document_status(unsupported)[0], "unsupported")

    def test_failed_separator_regeneration_preserves_previous_generation(self):
        result, _ = self.complete_eb1a()
        directory = self.case_dir / "bundle/separators/pdf"
        previous = {path.name: path.read_bytes() for path in directory.iterdir()}
        with patch("reportlab.platypus.SimpleDocTemplate.build", side_effect=ValueError("Synthetic render failure")):
            with self.assertRaises(ValueError):
                bundle.render_separator_pdfs(self.case_id)
        self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, previous)

    def test_failed_office_conversion_keeps_previous_pdf(self):
        target = self.root / "converted.pdf"
        target.write_bytes(b"previous completed PDF")
        source = self.root / "synthetic.docx"
        with patch.object(bundle, "_find_soffice", return_value="synthetic-office"), patch.object(bundle.subprocess, "run", side_effect=OSError("Synthetic conversion failure")):
            with self.assertRaises(OSError):
                bundle._convert_docx_to_pdf(source, target)
        self.assertEqual(target.read_bytes(), b"previous completed PDF")

    def test_o1b_repeatable_units_import_insert_and_rebuild_without_duplicates(self):
        self.create("o1b_petition")
        folder = "2.critical_reviews_or_other_published_materials_by_or_about_the_beneficiary"
        names = {1: "Alpha Festival", 2: "Zebra Magazine"}
        for number in (1, 2):
            self.source(name="press.txt", text=f"Synthetic press publication {number}", folder=f"{folder}/{names[number]}")
        evidence.scan_documents(self.case_id)
        step_id = "o1b_criterion_ii_episode"
        for number in (1, 2):
            episode = workflow._episode_id_from_folder_name(names[number])
            prompt = workflow.build_prompt(self.case_id, step_id, [], episode_id=episode, episode_folder=names[number])
            self.assertIn(f"Synthetic press publication {number}", prompt.read_text(encoding="utf-8"))
            loaded = workflow.load_case(self.case_id)
            selected = workflow.selected_documents_for_step(loaded, workflow.find_step(loaded.workflow, step_id), workflow.PromptOptions(episode_id=episode, episode_folder=names[number]))
            data = self.payload(step=step_id, episode=episode, text=f"Synthetic publication number {number} recognizes Alex Example for distinguished artistic achievements and professional recognition.")
            data["used_documents"] = [{"document_id": row["document_id"], "document_title": f"Synthetic press publication {number}", "used_for": "Published recognition"} for row in selected]
            self.import_payload(data)
            workflow.insert_section(self.case_id, step_id, episode_id=episode)
        summary = memo_builder.build_working_memo(self.case_id)
        text = workflow.extract_docx_text(summary.docx_path)
        for number in (1, 2):
            self.assertEqual(text.count(f"Synthetic publication number {number} recognizes"), 1)
        memo_builder.build_working_memo(self.case_id)
        self.assertEqual(workflow.extract_docx_text(summary.docx_path), text)
