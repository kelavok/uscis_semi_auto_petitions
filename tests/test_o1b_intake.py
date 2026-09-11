import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import cli_support, web
from app.o1b_folders import resolve_o1b_folders
from app.o1b_exhibits import exhibit_roles
from app.stages import build_llm_stage
from app.workflow import load_case


class O1BIntakeTests(unittest.TestCase):
    def test_exhibits_are_consecutive_when_unclaimed_criteria_are_absent(self):
        with TemporaryDirectory() as temp:
            case_dir = Path(temp)
            roles = {
                "identity_cv_education": "general",
                "published_recognition": "published",
                "organization_role": "role",
                "significant_recognition": "recognition",
                "us_work_documents": "employment",
            }
            for folder in roles.values():
                target = case_dir / "source_documents" / "originals" / folder
                target.mkdir(parents=True)
                (target / "evidence.pdf").write_bytes(b"evidence")
            loaded = SimpleNamespace(
                case_dir=case_dir,
                config={
                    "claimed_criteria": [
                        "published_recognition",
                        "organization_role",
                        "significant_recognition",
                    ],
                    "o1b_folder_roles": roles,
                    "paths": {
                        "source_originals": "source_documents/originals",
                        "source_translations": "source_documents/translations",
                        "source_other": "source_documents/other",
                    },
                },
            )

            self.assertEqual(
                exhibit_roles(loaded),
                {
                    "identity_cv_education": "1",
                    "published_recognition": "2",
                    "organization_role": "3",
                    "significant_recognition": "4",
                    "us_work_documents": "5",
                },
            )

    def test_import_indexes_and_keeps_similar_episodes_separate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "cases"
            template = case_root / "_template"
            shutil.copytree(cli_support.CASE_TEMPLATE_ROOT, template)
            source = root / "source"
            for folder, name in [
                ("2.critical reviews/Publication 2024", "first"),
                ("2.critical reviews/Publication 2025", "second"),
                ("3.role/AMMG/1. Leading role and corporate docs - role, control, ownership", "role"),
                ("3.role/AMMG/2. Distinguished reputation of the organization", "reputation"),
            ]:
                target = source / folder
                target.mkdir(parents=True)
                (target / f"{name}.txt").write_text(name)
            with patch.object(cli_support, "CASE_ROOT", case_root), patch.object(
                cli_support, "CASE_TEMPLATE_ROOT", template
            ):
                cli_support.create_case_from_template("sample", "o1b_petition")
                result = web.handle_action("apply_intake", "sample", {
                    "source_originals_path": str(source),
                    "claimed_criteria_present": "1",
                    "criterion_published_recognition": "on",
                    "criterion_organization_role": "on",
                })
                self.assertIn("indexed 4 document(s)", result)
                units = build_llm_stage("sample").units
                publications = [u for u in units if u.step_id == "o1b_criterion_ii_episode"]
                self.assertEqual(len(publications), 2)
                self.assertTrue(all(len(u.selected_documents) == 1 for u in publications))
                self.assertNotEqual(publications[0].selected_documents, publications[1].selected_documents)
                for step, title in [("role", "role"), ("reputation", "reputation")]:
                    unit = next(u for u in units if u.step_id == f"o1b_criterion_iii_{step}")
                    self.assertEqual([d[1] for d in unit.selected_documents], [title])
                self.assertEqual(load_case("sample").config["o1b_folder_roles"]["organization_role"], "3.role")

    def test_ambiguous_and_explicit_folders_are_not_remapped(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "2.one").mkdir()
            (root / "2.two").mkdir()
            config = {"task_type": "o1b_petition", "paths": {"source_originals": "."},
                      "o1b_folder_roles": {"published_recognition": "2.original"}}
            self.assertEqual(resolve_o1b_folders(config, root), 0)
            config["o1b_folder_roles"]["published_recognition"] = "2.one"
            self.assertEqual(resolve_o1b_folders(config, root), 0)
