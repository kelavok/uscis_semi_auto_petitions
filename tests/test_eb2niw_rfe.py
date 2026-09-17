from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import cli_support
from app.bundle_workflow import _exhibit_metadata_for_output, _exhibit_number_for_output
from app.evidence import scan_documents
from app.memo_builder import build_working_memo
from app.rfe_strategy import (
    apply_strategy_output,
    build_strategy_bootstrap_prompt,
    import_evidence_and_scan_inputs,
    render_strategy_unit_context,
)
from app.workflow import load_case


class Eb2NiwRfeWorkflowTests(unittest.TestCase):
    def test_full_strategy_initial_filing_prompt_and_exhibit_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(cli_support, "CASE_ROOT", root):
                case_dir = cli_support.create_case_from_template(
                    "niw_rfe_test", "eb2niw_rfe_response"
                )
                config_text = (case_dir / "case_config.yaml").read_text(encoding="utf-8")
                self.assertIn("task_type: eb2niw_rfe_response", config_text)
                self.assertIn("templates/RFE/EB2NIW/EB2_NIW_RFE_response_human_template.docx", config_text)
                self.assertTrue(
                    (
                        case_dir
                        / "source_documents/rfe_response/new_documents/originals"
                        / "3. (2) Пронг - Хорошая подготовка"
                        / "3. Прочие достижения"
                        / "8.Рек письма США"
                    ).is_dir()
                )

                strategy = root / "strategy.txt"
                strategy.write_text("STRATEGY-CONTEXT-UNIQUE", encoding="utf-8")
                rfe = root / "rfe.txt"
                rfe.write_text("RFE-FULL-CONTEXT-UNIQUE", encoding="utf-8")
                bootstrap = build_strategy_bootstrap_prompt(
                    "niw_rfe_test", str(strategy), str(rfe)
                )
                bootstrap_text = bootstrap.prompt_path.read_text(encoding="utf-8")
                self.assertIn("EB-2 NIW RFE strategy JSON", bootstrap_text)
                self.assertIn('"const": "eb2niw_rfe_response"', bootstrap_text)
                self.assertIn("STRATEGY-CONTEXT-UNIQUE", bootstrap_text)
                self.assertIn("RFE-FULL-CONTEXT-UNIQUE", bootstrap_text)

                output = _strategy_output()
                summary = apply_strategy_output("niw_rfe_test", output)
                self.assertEqual(summary.unit_count, 2)

                initial = root / "initial.txt"
                initial.write_text("INITIAL-FILING-FULL-CONTEXT-UNIQUE", encoding="utf-8")
                new_docs = root / "new_docs"
                evidence_folder = new_docs / "originals" / "2. Prong 1" / "National Importance"
                evidence_folder.mkdir(parents=True)
                (evidence_folder / "Federal Initiative.txt").write_text(
                    "FEDERAL-EVIDENCE-CONTENT-UNIQUE", encoding="utf-8"
                )
                import_evidence_and_scan_inputs(
                    "niw_rfe_test", str(initial), str(new_docs)
                )
                scan_documents("niw_rfe_test")

                loaded = load_case("niw_rfe_test")
                context = render_strategy_unit_context(loaded, "prong1_national_importance")
                self.assertIn("STRATEGY-CONTEXT-UNIQUE", context)
                self.assertIn("RFE-FULL-CONTEXT-UNIQUE", context)
                self.assertIn("INITIAL-FILING-FULL-CONTEXT-UNIQUE", context)
                self.assertIn("FEDERAL-EVIDENCE-CONTENT-UNIQUE", context)
                self.assertIn("DOC000", context)

                memo = build_working_memo("niw_rfe_test")
                self.assertTrue(memo.docx_path.exists())
                self.assertGreater(memo.docx_path.stat().st_size, 20_000)
                self.assertEqual(
                    _exhibit_number_for_output(
                        loaded,
                        {
                            "step_id": "rfe_dynamic_section",
                            "episode_id": "prong1_national_importance",
                        },
                    ),
                    "2",
                )
                self.assertEqual(
                    _exhibit_metadata_for_output(
                        loaded,
                        {
                            "step_id": "rfe_dynamic_section",
                            "episode_id": "prong1_national_importance",
                        },
                    )[0],
                    "First Prong: The Proposed Endeavor Has Both Substantial Merit and National Importance",
                )


def _strategy_output() -> dict[str, object]:
    metadata = {
        "beneficiary_full_name": "Alex Example",
        "preferred_reference": "Mr. Example",
        "field": "software engineering",
        "specialization": "public-sector data systems",
        "intended_occupation": "Software Engineer",
        "proposed_endeavor_title": "National public-data interoperability platform",
        "one_sentence_endeavor": "Develop and deploy interoperable public-data systems.",
        "eb2_basis": "advanced_degree",
        "case_number": "IOE0000000000",
        "receipt_date": "January 1, 2026",
        "rfe_date": "July 1, 2026",
        "response_deadline": "September 1, 2026",
        "uscis_address": "USCIS",
        "rfe_response_date": "August 17, 2026",
        "uscis_office_or_service_center": "Service Center",
        "officer_name": "",
        "office_chief_name": "",
        "salutation": "Dear Officer:",
        "submitter_name": "Alex Example",
        "submitter_title": "Petitioner/Beneficiary",
        "petition_type": "EB-2 NIW Form I-140",
    }
    issue = {
        "issue_id": "niw_prong1_national_importance",
        "topic": "National importance",
        "issue_type": "prong1",
        "status": "not_accepted",
        "criterion_role": "prong1",
        "exact_rfe_quote": "The record does not establish prospective national impact.",
        "quote_source_pages": [5],
        "defect": "USCIS found the prospective impact insufficiently documented.",
        "response_strategy": "Connect the specific endeavor to federal priorities and prospective scale.",
        "elements_not_disputed_do_not_discuss": ["substantial merit"],
        "evidence_actions": ["Use the federal initiative document."],
    }
    return {
        "case_id": "niw_rfe_test",
        "task_type": "eb2niw_rfe_response",
        "case_metadata": metadata,
        "global_strategy": "Preserve the original endeavor and answer only disputed findings.",
        "accepted_criteria": ["advanced_degree"],
        "challenged_criteria": ["prong1"],
        "rfe_issues": [issue],
        "sections": [
            {
                "section_id": "cover_letter",
                "order": 1,
                "title": "Cover Letter",
                "section_type": "cover_letter",
                "criterion_role": "",
                "required": True,
                "strategy": "Identify the filing and disputed prong.",
                "rfe_issue_ids": ["niw_prong1_national_importance"],
                "starter_text": "",
                "source_folder": "",
                "initial_filing_heading_hints": [],
                "episodes": [],
            },
            {
                "section_id": "prong1",
                "order": 2,
                "title": "First Prong",
                "section_type": "prong",
                "criterion_role": "prong1",
                "required": True,
                "strategy": "Answer national importance without rearguing substantial merit.",
                "rfe_issue_ids": ["niw_prong1_national_importance"],
                "starter_text": "",
                "source_folder": "2. Prong 1/National Importance",
                "initial_filing_heading_hints": ["national importance"],
                "episodes": [
                    {
                        "episode_id": "prong1_national_importance",
                        "title": "The Endeavor Has Prospective National Impact",
                        "source_folder": "2. Prong 1/National Importance",
                        "strategy": "Use the federal initiative evidence.",
                        "rfe_issue_ids": ["niw_prong1_national_importance"],
                        "planned_subheadings": ["The Endeavor Advances a Federal Priority"],
                        "initial_filing_heading_hints": ["national importance"],
                    }
                ],
            },
        ],
        "template_decisions": {
            "structure_rationale": "Only Prong 1 is disputed.",
            "include_basic_eligibility": False,
            "include_prong1": True,
            "include_prong2": False,
            "include_prong3": False,
            "include_summary": True,
            "attachment_label": "Exhibit",
        },
        "open_questions": [],
    }


if __name__ == "__main__":
    unittest.main()
