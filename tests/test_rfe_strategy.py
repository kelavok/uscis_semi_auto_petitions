import json
import shutil
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from docx import Document

from app import cli_support, web
from app.bundle_workflow import inspect_layout_index_status, refresh_layout_indexes
from app.evidence import scan_documents
from app.memo_builder import build_working_memo
from app.rfe_strategy import (
    apply_strategy_output,
    build_strategy_bootstrap_prompt,
    import_evidence_and_scan_inputs,
)
from app.stages import build_llm_stage
from app.workflow import build_prompt


class RfeStrategyTests(unittest.TestCase):
    def test_strategy_manifest_drives_template_units_and_prompt_context(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            template_root = case_root / "_template"
            shutil.copytree(cli_support.CASE_TEMPLATE_ROOT, template_root)
            strategy = root / "strategy.txt"
            rfe = root / "rfe.txt"
            strategy.write_text("Argue each criterion using the mapped evidence.", encoding="utf-8")
            rfe.write_text("Case IOE123. Awards were not accepted.", encoding="utf-8")

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(cli_support, "CASE_TEMPLATE_ROOT", template_root),
                patch.object(web, "CASE_ROOT", case_root),
            ):
                case_dir = cli_support.create_case_from_template("rfe_test", "eb1a_rfe_response")
                bootstrap = build_strategy_bootstrap_prompt(
                    "rfe_test", str(strategy), str(rfe)
                )
                self.assertIn("Human strategy", bootstrap.prompt_path.read_text(encoding="utf-8"))
                bootstrap_html = web.render_rfe_panel("rfe_test")
                self.assertIn("RFE Stage 1A", bootstrap_html)
                self.assertIn("Generated bootstrap prompt", bootstrap_html)
                output = {
                    "case_id": "rfe_test",
                    "task_type": "eb1a_rfe_response",
                    "case_metadata": {
                        "beneficiary_full_name": "Jane Doe",
                        "preferred_reference": "Ms. Doe",
                        "field": "Business",
                        "specialization": "Software Engineering",
                        "case_number": "IOE123",
                        "receipt_date": "January 1, 2026",
                        "rfe_date": "May 1, 2026",
                        "response_deadline": "July 1, 2026",
                        "uscis_address": "USCIS Test Address",
                        "rfe_response_date": "June 15, 2026",
                        "uscis_office_or_service_center": "Nebraska Service Center",
                        "officer_name": "Jane Officer",
                        "office_chief_name": "",
                        "salutation": "Dear Ms. Jane Officer and Officer:",
                        "submitter_name": "Jane Doe",
                        "submitter_title": "Petitioner and Beneficiary",
                        "petition_type": "EB-1A Form I-140",
                    },
                    "global_strategy": "Answer the exact RFE defect and distinguish commentary from evidence.",
                    "accepted_criteria": ["judging"],
                    "challenged_criteria": ["awards"],
                    "rfe_issues": [
                        {
                            "issue_id": "awards_legitimacy",
                            "topic": "Awards",
                            "issue_type": "criterion",
                            "status": "not_accepted",
                            "criterion_role": "awards",
                            "exact_rfe_quote": "Awards were not accepted because national recognition was not established.",
                            "defect": "Recognition was not established.",
                            "response_strategy": "Use independent recognition evidence.",
                            "elements_not_disputed_do_not_discuss": ["Receipt of the award"],
                            "evidence_actions": ["Resubmit the award regulations."],
                        }
                    ],
                    "sections": [
                        {
                            "section_id": "cover",
                            "order": 1,
                            "title": "Cover Letter",
                            "section_type": "cover_letter",
                            "required": True,
                            "strategy": "Summarize the response order.",
                            "rfe_issue_ids": [],
                            "starter_text": "Dear USCIS Officer:",
                            "episodes": [],
                        },
                        {
                            "section_id": "awards",
                            "order": 2,
                            "title": "Awards",
                            "section_type": "criterion",
                            "criterion_role": "awards",
                            "required": True,
                            "strategy": "Lead with independent evidence.",
                            "rfe_issue_ids": ["awards_legitimacy"],
                            "starter_text": "",
                            "initial_filing_heading_hints": ["Awards criterion"],
                            "episodes": [
                                {
                                    "episode_id": "award_nba",
                                    "title": "Technologies and Innovations Award",
                                    "source_folder": "1. Награды/1 episode",
                                    "strategy": "Explain the selection process.",
                                    "rfe_issue_ids": ["awards_legitimacy"],
                                    "planned_subheadings": [
                                        "The Award Has National Recognition in the Field"
                                    ],
                                    "initial_filing_heading_hints": [],
                                }
                            ],
                        },
                    ],
                    "template_decisions": {
                        "structure_rationale": "Cover first, then the challenged criterion.",
                        "include_general_response": False,
                        "include_employment_section": False,
                        "include_final_merits": False,
                        "attachment_label": "Attachment",
                    },
                    "open_questions": [],
                }
                imported = apply_strategy_output("rfe_test", output)
                self.assertEqual(imported.unit_count, 2)
                accepted_html = web.render_rfe_panel("rfe_test")
                self.assertIn("Accepted: 2 drafting unit(s)", accepted_html)
                self.assertIn("RFE Stage 1C", accepted_html)

                initial_memo = root / "initial_memo.txt"
                initial_memo.write_text(
                    "Documentation of receipt of lesser nationally recognized prizes or awards\n\n"
                    "The beneficiary received the technology award.\n\n"
                    "Documentation of membership in associations\n\nMembership evidence.",
                    encoding="utf-8",
                )
                new_docs = root / "new_docs" / "originals" / "1. Награды" / "1 episode"
                new_docs.mkdir(parents=True)
                (new_docs / "organizer_letter.txt").write_text("New organizer letter", encoding="utf-8")
                (new_docs / "extracts.txt").write_text(
                    "The attached ceremony screenshot identifies Jane Doe as the category winner.",
                    encoding="utf-8",
                )
                (new_docs / "info.txt").write_text(
                    "LLM instruction: emphasize the independent organizer confirmation first.",
                    encoding="utf-8",
                )
                info_docx = Document()
                info_docx.add_paragraph("DOCX guidance: rely on the organizer letter, not this note.")
                info_docx.save(new_docs / "info.docx")
                (new_docs / "README.md").write_text(
                    "Use the ceremony screenshot and organizer letter as one evidence set.",
                    encoding="utf-8",
                )
                (new_docs / "broken_scan.docx").write_bytes(
                    b"This is an image export incorrectly named as a DOCX file."
                )
                (new_docs / "citation.xlsx").write_bytes(b"unsupported spreadsheet placeholder")
                (new_docs / "~$open_in_word.docx").write_bytes(b"Office lock file")
                evidence = import_evidence_and_scan_inputs(
                    "rfe_test",
                    str(initial_memo),
                    str(root / "new_docs"),
                )
                self.assertGreaterEqual(evidence.initial_sections, 1)
                scan_documents("rfe_test")
                document_index = (case_dir / "indexes/document_index.csv").read_text(
                    encoding="utf-8-sig"
                )
                self.assertNotIn("extracts.txt", document_index)
                self.assertNotIn("info.txt", document_index)
                self.assertNotIn("info.docx", document_index)
                self.assertNotIn("README.md", document_index)
                self.assertIn("broken_scan.docx", document_index)
                self.assertIn("docx_invalid_or_corrupt", document_index)
                self.assertNotIn("~$open_in_word.docx", document_index)
                stage = build_llm_stage("rfe_test")
                self.assertNotIn("cover", [unit.episode_id for unit in stage.units])
                award_unit = next(unit for unit in stage.units if unit.criterion == "awards")
                self.assertTrue(award_unit.selected_documents)
                prompt_path = build_prompt(
                    "rfe_test",
                    "rfe_dynamic_section",
                    [],
                    episode_id=award_unit.episode_id,
                    episode_folder="1. Награды/1 episode",
                )
                prompt_text = prompt_path.read_text(encoding="utf-8")
                self.assertIn("Explain the selection process", prompt_text)
                self.assertIn("The beneficiary received the technology award", prompt_text)
                self.assertIn("organizer_letter.txt", prompt_text)
                self.assertIn("The attached ceremony screenshot identifies Jane Doe", prompt_text)
                self.assertIn("prompt-only folder sidecar (extracts.txt)", prompt_text)
                self.assertIn("do not add to document/exhibit indexes", prompt_text)
                self.assertIn("emphasize the independent organizer confirmation first", prompt_text)
                self.assertIn("prompt-only folder sidecar (info.txt)", prompt_text)
                self.assertIn("DOCX guidance: rely on the organizer letter", prompt_text)
                self.assertIn("prompt-only folder sidecar (info.docx)", prompt_text)
                self.assertIn("additional instructions and explanations", prompt_text)
                self.assertIn("Use the ceremony screenshot and organizer letter as one evidence set", prompt_text)
                self.assertIn("prompt-only folder sidecar (README.md)", prompt_text)
                self.assertIn("Technical document selection for this unit", prompt_text)
                self.assertIn("must be copied exactly", prompt_text)

                selected_document_id = next(
                    document_id
                    for document_id, title in award_unit.selected_documents
                    if "organizer" in title.casefold()
                )
                spreadsheet_document_id = next(
                    document_id
                    for document_id, title in award_unit.selected_documents
                    if "citation" in title.casefold()
                )
                validated_path = case_dir / "validated_outputs" / f"rfe_dynamic_section.{award_unit.episode_id}.json"
                validated_path.write_text(
                    json.dumps(
                        {
                            "case_id": "rfe_test",
                            "task_type": "eb1a_rfe_response",
                            "step_id": "rfe_dynamic_section",
                            "episode_id": award_unit.episode_id,
                            "draft_text": "Awards response.",
                            "used_documents": [
                                {
                                    "document_id": selected_document_id,
                                    "document_title": "Organizer letter",
                                    "used_for": "award evidence",
                                },
                                {
                                    "document_id": spreadsheet_document_id,
                                    "document_title": "Citation table",
                                    "used_for": "award evidence",
                                },
                            ],
                            "unsupported_claims": [],
                            "questions_for_user": [],
                            "quality_flags": [],
                            "revision_notes": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                before_refresh = inspect_layout_index_status("rfe_test")
                self.assertTrue(before_refresh.refresh_required)
                before_layout = web.render_layout_page("rfe_test", {})
                self.assertIn("Index refresh required", before_layout)
                self.assertIn("Refresh indexes", before_layout)
                next(case_dir.rglob("citation.xlsx")).with_suffix(".pdf").write_bytes(
                    b"%PDF-1.4\n%%EOF\n"
                )
                refreshed = refresh_layout_indexes("rfe_test")
                self.assertEqual(refreshed.replacement_documents_rebound, 1)
                self.assertEqual(refreshed.status.assigned_used_documents, 2)
                self.assertEqual(refreshed.status.exhibit_count, 1)
                self.assertTrue(refreshed.status.ready_for_separators)
                self.assertFalse(refreshed.status.unsupported_documents)
                layout_page = web.render_layout_page("rfe_test", {})
                self.assertIn("Evidence indexes ready", layout_page)
                self.assertIn("Select & prepare", layout_page)
                self.assertIn("Prepare selected bundle", layout_page)
                self.assertIn("Build selected PDF", layout_page)
                refreshed_index = (case_dir / "indexes/document_index.csv").read_text(
                    encoding="utf-8-sig"
                )
                selected_row = next(
                    line for line in refreshed_index.splitlines() if line.startswith(f"{selected_document_id},")
                )
                self.assertIn(",1,", selected_row)
                spreadsheet_row = next(
                    line
                    for line in refreshed_index.splitlines()
                    if line.startswith(f"{spreadsheet_document_id},")
                )
                self.assertIn("citation.pdf", spreadsheet_row)

                stage = build_llm_stage("rfe_test")
                self.assertEqual([unit.criterion for unit in stage.units], ["awards"])
                self.assertNotEqual(stage.units[0].episode_id, "award_nba")
                memo = build_working_memo("rfe_test")
                with zipfile.ZipFile(memo.docx_path) as archive:
                    document_xml = archive.read("word/document.xml").decode("utf-8")
                self.assertIn("episode", document_xml)
                self.assertIn("Dear Ms. Jane Officer and Officer:", document_xml)
                self.assertIn("Awards were not accepted because national recognition was not established", document_xml)
                self.assertIn("The Award Has National Recognition in the Field", document_xml)


if __name__ == "__main__":
    unittest.main()
