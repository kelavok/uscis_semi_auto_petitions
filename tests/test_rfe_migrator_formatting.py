import unittest
from pathlib import Path
from unittest.mock import patch

from app.memo_builder import (
    _is_rfe_thesis_heading,
    _rfe_draft_runs,
    _rfe_group_requests_quote,
)
from app.workflow import LoadedCase, _rfe_strategy_citation_plan


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

    def test_base_rfe_keeps_statutory_exhibit_mapping(self) -> None:
        loaded = LoadedCase(
            "case",
            Path("case"),
            {"task_type": "eb1a_rfe_response", "eb1a_rfe_template_variant": "base"},
            {},
        )
        with patch("app.rfe_strategy.effective_strategy_units", return_value=self.units):
            self.assertEqual(
                _rfe_strategy_citation_plan(loaded, "media_two"),
                {"exhibit_number": "3", "item_prefix": "3.2."},
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
