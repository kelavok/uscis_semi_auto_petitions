"""Synthetic, isolated workspaces shared by Stage 0 regression tests."""
import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import cli_support, web, workflow
from app.evidence import scan_documents
from app.memo_builder import apply_case_intake


class SyntheticCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.case_root = self.root / "cases"
        for module in (cli_support, web):
            patcher = patch.object(module, "CASE_ROOT", self.case_root)
            patcher.start()
            self.addCleanup(patcher.stop)

    def create(self, task="eb1a_petition", case="synthetic"):
        self.case_id = case
        self.case_dir = cli_support.create_case_from_template(case, task)
        apply_case_intake(case, {
            "beneficiary_full_name": "Alex Example", "preferred_reference": "Mx. Example",
            "gender": "male", "citizenship": "France", "field": "Arts",
            "specialization": "Synthetic testing", "o1b_track": "arts",
            "petitioner_company_name": "Example Arts LLC", "validity_start": "2026-01-01",
            "validity_end": "2028-12-31", "filing_uscis_address": "Synthetic USCIS address",
            "position_or_role": "Artist", "compensation": "Synthetic compensation",
            "work_location": "Synthetic work location",
        })
        return self.case_dir

    def source(self, name="award.txt", text="Synthetic award evidence", *, translation=False, folder="1. Награды/1. Award"):
        kind = "source_translations" if translation else "source_originals"
        loaded = workflow.load_case(self.case_id)
        path = self.case_dir / loaded.config["paths"][kind] / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def rows(self):
        with (self.case_dir / "indexes/document_index.csv").open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def payload(self, step="criterion_awards_episode", episode="1", text=None):
        loaded = workflow.load_case(self.case_id)
        selected = workflow.selected_documents_for_step(loaded, workflow.find_step(loaded.workflow, step), workflow.PromptOptions(episode_id=episode, episode_folder="1. Award"))
        return {
            "case_id": self.case_id, "task_type": loaded.config["task_type"], "step_id": step,
            "episode_id": episode,
            "draft_text": text or "Alex Example received the Synthetic Award for achievements in the arts. The submitted certificate and English translation document this recognition.",
            "used_documents": [{"document_id": row["document_id"], "document_title": f"Synthetic award document {index}", "used_for": "Award recognition"} for index, row in enumerate(selected, 1)],
            "unsupported_claims": [], "questions_for_user": [], "quality_flags": [], "revision_notes": [],
        }

    def import_payload(self, data=None, **options):
        data = data or self.payload()
        source = self.case_dir / "llm_outputs/synthetic.json"
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return workflow.import_llm_output(self.case_id, data["step_id"], str(source), episode_id=data.get("episode_id") or None, **options)
