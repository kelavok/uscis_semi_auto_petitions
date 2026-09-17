import unittest
from pathlib import Path
from unittest.mock import patch

from app.memo_builder import (
    _markdown_runs,
    _is_rfe_thesis_heading,
    _rfe_draft_runs,
    _rfe_group_requests_quote,
    _styles_xml,
)
from app.workflow import LoadedCase, _eb1a_exhibit_numbers, _rfe_strategy_citation_plan


class RfeMigratorFormattingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.units = [
            {"unit_id": "media_one", "criterion_role": "media"},
            {"unit_id": "media_two", "criterion_role": "media"},
            {"unit_id": "salary", "criterion_role": "high_salary"},
            {"unit_id": "membership", "criterion_role": "memberships"},
        ]

    def test_migrator_exhibits_follow_first_appearance_not_criterion_number(self) -> None:
        loaded = LoadedCase(
            "case",
            Path("case"),
            {"task_type": "eb1a_rfe_response", "eb1a_rfe_template_variant": "migrator"},
            {},
        )
        with patch("app.rfe_strategy.effective_strategy_units", return_value=self.units):
            self.assertEqual(
                _rfe_strategy_citation_plan(loaded, "media_two"),
                {"exhibit_number": "1", "item_prefix": "1.2."},
            )
            self.assertEqual(
                _rfe_strategy_citation_plan(loaded, "salary"),
                {"exhibit_number": "2", "item_prefix": "2.1."},
            )
            self.assertEqual(
                _rfe_strategy_citation_plan(loaded, "membership"),
                {"exhibit_number": "3", "item_prefix": "3.1."},
            )

    def test_base_rfe_also_uses_consecutive_exhibit_mapping(self) -> None:
        loaded = LoadedCase(
            "case",
            Path("case"),
            {"task_type": "eb1a_rfe_response", "eb1a_rfe_template_variant": "base"},
            {},
        )
        with patch("app.rfe_strategy.effective_strategy_units", return_value=self.units):
            self.assertEqual(
                _rfe_strategy_citation_plan(loaded, "media_two"),
                {"exhibit_number": "1", "item_prefix": "1.2."},
            )

    def test_eb1a_petition_exhibits_are_consecutive_when_criteria_are_missing(self) -> None:
        workflow = {
            "steps": [
                {"step_id": "comparable_evidence_episode"},
                {"step_id": "employment_plan"},
            ]
        }
        loaded = LoadedCase(
            "case",
            Path("case"),
            {
                "task_type": "eb1a_petition",
                "claimed_criteria": ["awards", "media", "high_salary"],
            },
            workflow,
        )
        with (
            patch("app.workflow._step_enabled_for_case", return_value=True),
            patch("app.workflow._repeatable_episode_candidates", return_value=[("1", Path("1"))]),
        ):
            self.assertEqual(
                _eb1a_exhibit_numbers(loaded),
                {
                    "awards": "1",
                    "media": "2",
                    "high_salary": "3",
                    "comparable_evidence": "4",
                    "employment_plan": "5",
                },
            )

    def test_noncriterion_rfe_quote_is_strategy_controlled(self) -> None:
        self.assertFalse(
            _rfe_group_requests_quote(
                [{"section_type": "final_merits", "criterion_role": "", "strategy": "Synthesize the record."}]
            )
        )
        self.assertTrue(
            _rfe_group_requests_quote(
                [{"section_type": "final_merits", "criterion_role": "", "strategy": "Quote the RFE concern first."}]
            )
        )
        self.assertFalse(
            _rfe_group_requests_quote(
                [
                    {
                        "section_type": "final_merits",
                        "criterion_role": "",
                        "strategy": "Quote the RFE concern first.",
                        "include_rfe_quote": False,
                    }
                ]
            )
        )

    def test_migrator_word_styles_and_inline_exhibit_citations(self) -> None:
        styles = _styles_xml("Times New Roman")
        self.assertIn('w:line="360"', styles)
        self.assertRegex(styles, r'styleId="Heading1".*?<w:sz w:val="32"/>')
        self.assertRegex(styles, r'styleId="Heading2".*?<w:sz w:val="28"/>')
        citation = (
            "Text before (Please refer to Exhibit 0, page PAGE: 0.2 - Curriculum Vitae.) "
            "text after."
        )
        citation_runs = [item for item in _markdown_runs(citation) if "Please refer" in item[0]]
        self.assertEqual(len(citation_runs), 1)
        self.assertEqual(citation_runs[0][1], {"bold": True, "italic": True})

    def test_markdown_web_links_are_rendered_without_visible_artifacts(self) -> None:
        same_url = "Archive [https://example.com/path](https://example.com/path) end."
        rendered = "".join(text for text, _props in _markdown_runs(same_url))
        self.assertEqual(rendered, "Archive https://example.com/path end.")
        self.assertNotIn("[", rendered)
        self.assertNotIn("](", rendered)

        named = "See [Commerce supply-chain review](https://commerce.gov/review)."
        named_rendered = "".join(text for text, _props in _markdown_runs(named))
        self.assertEqual(
            named_rendered,
            "See Commerce supply-chain review (https://commerce.gov/review).",
        )

        rfe_rendered = "".join(
            text
            for text, _props in _rfe_draft_runs(
                "Source: <https://example.com/source> and [https://example.com/a](https://example.com/a)."
            )
        )
        self.assertEqual(
            rfe_rendered,
            "Source: https://example.com/source and https://example.com/a.",
        )

    def test_thesis_quotes_and_exhibit_references_receive_required_formatting(self) -> None:
        heading = "Independent Evidence Establishes the Outlet's Professional Standing"
        self.assertTrue(_is_rfe_thesis_heading(heading))
        self.assertEqual(_rfe_draft_runs(heading), [(heading, {"bold": True})])
        self.assertTrue(
            _is_rfe_thesis_heading(
                "Population-Normalized Readership Shows a Scale Comparable to Major U.S. Trade Media"
            )
        )

        rfe_text = 'In the RFE, the officer states: “The evidence was insufficient.”'
        rfe_runs = _rfe_draft_runs(rfe_text)
        self.assertTrue(any(props.get("italic") for _text, props in rfe_runs))
        self.assertTrue(any(props.get("bold") for _text, props in rfe_runs))

        citation_text = "The record is complete. (Please refer to Exhibit 2, page PAGE: 2.1.1 - Salary records.)"
        citation_runs = _rfe_draft_runs(citation_text)
        self.assertTrue(
            any(props.get("bold") and props.get("italic") for _text, props in citation_runs)
        )


if __name__ == "__main__":
    unittest.main()
