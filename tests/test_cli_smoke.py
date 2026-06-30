import unittest
import importlib.util
import zipfile
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from app import bundle, draft, web
from app import cli_support
from app import evidence as evidence_module
from app import workflow as workflow_module
from app.bundle_workflow import (
    build_bundle_plan,
    build_exhibit_index,
    generate_separator_pages,
    render_separator_pdfs,
)
from app.evidence import link_translations, manual_link_translation, scan_documents, unlink_translation
from app.memo_builder import apply_case_intake, build_working_memo, parse_machine_template
from app.workflow import find_step, load_yaml_file
from app.simple_yaml import load_yaml_subset


class CliSmokeTests(unittest.TestCase):
    def test_simple_yaml_accepts_indentless_sequence(self) -> None:
        parsed = load_yaml_subset("claimed_criteria:\n- awards\n- judging\nnext_key: value\n")
        self.assertEqual(parsed["claimed_criteria"], ["awards", "judging"])
        self.assertEqual(parsed["next_key"], "value")

    def test_load_yaml_file_falls_back_when_pyyaml_rejects_plaintext_bang_value(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "case_config.yaml"
            path.write_text("eb1a_folder_roles:\n  identity_cv_education: !CV, Passport\n", encoding="utf-8")
            parsed = load_yaml_file(path)
        self.assertEqual(parsed["eb1a_folder_roles"]["identity_cv_education"], "!CV, Passport")

    def test_translation_match_handles_moved_folders_and_eng_suffix(self) -> None:
        original = {
            "document_id": "DOC0001",
            "category": "awards",
            "file_path": "source_documents/originals/1. Награды/NBA full title/О награде/Положение.pdf",
        }
        translation = {
            "document_id": "DOC0002",
            "category": "awards",
            "file_path": "source_documents/translations/1. Награды/NBA_eng/О награде_eng/Положение_eng.pdf",
        }
        decision = evidence_module._translation_match_decision(translation, [original])
        self.assertEqual(decision.candidate, original)
        self.assertIn(decision.method, {"unique_normalized_name_in_category", "matched_episode+fuzzy_name"})

    def test_translation_match_handles_cyrillic_latin_recommender_name(self) -> None:
        original = {
            "document_id": "DOC0001",
            "category": "recommendation_letters",
            "file_path": "source_documents/originals/Рекомендательные письма/Александр Богданов_рекписьмо.pdf",
        }
        translation = {
            "document_id": "DOC0002",
            "category": "recommendation_letters",
            "file_path": "source_documents/translations/Рекомендательные письма/Alexander_Bogdanov_Recommendation_Translation.pdf",
        }
        decision = evidence_module._translation_match_decision(translation, [original])
        self.assertEqual(decision.candidate, original)

    def test_safe_path_component_accepts_cyrillic_episode_names(self) -> None:
        self.assertEqual(
            workflow_module.safe_path_component("Вклад - подтверждение"),
            "Вклад_-_подтверждение",
        )

    def test_episode_id_from_folder_name_keeps_enough_detail_to_avoid_collisions(self) -> None:
        federal = workflow_module._episode_id_from_folder_name("CRE Federal awards Sep 25, 2025")
        moscow = workflow_module._episode_id_from_folder_name("CRE Moscow awards Apr 24, 2025")
        self.assertNotEqual(federal, moscow)
        self.assertEqual(federal, "CRE_Federal_awards_Sep_25_2025")
        self.assertEqual(moscow, "CRE_Moscow_awards_Apr_24_2025")

    def test_repeatable_candidates_skip_empty_template_and_merge_eng_translation_folder(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = root / "case_workspace" / "case_001"
            originals = case_dir / "source_documents" / "originals" / "1. Награды"
            translations = case_dir / "source_documents" / "translations" / "1. Награды"
            other = case_dir / "source_documents" / "other" / "1. Награды"
            for folder in [originals / "1 episode", originals / "NBA full title", translations / "NBA_eng", other]:
                folder.mkdir(parents=True, exist_ok=True)
            (originals / "NBA full title" / "award.txt").write_text("award", encoding="utf-8")
            (translations / "NBA_eng" / "award translation.txt").write_text("award translation", encoding="utf-8")
            loaded = workflow_module.LoadedCase(
                case_id="case_001",
                case_dir=case_dir,
                config={
                    "paths": {
                        "source_originals": "source_documents/originals",
                        "source_translations": "source_documents/translations",
                        "source_other": "source_documents/other",
                    },
                    "eb1a_folder_roles": {"awards": "1. Награды"},
                },
                workflow={},
            )
            step = {"step_id": "criterion_awards_episode", "evidence_folder_roles": ["awards"]}
            candidates = workflow_module._repeatable_episode_candidates(loaded, step)
            self.assertEqual(candidates, [("NBA_full_title", "NBA full title")])
            resolved = workflow_module._episode_folders_for(
                translations,
                workflow_module.PromptOptions(episode_id="NBA_full_title", episode_folder="NBA full title"),
            )
            self.assertEqual([path.name for path in resolved], ["NBA_eng"])

    def test_repeatable_candidates_merge_cyrillic_acronym_with_full_association_name(self) -> None:
        with TemporaryDirectory() as temp:
            case_dir = Path(temp)
            originals = case_dir / "source_documents" / "originals" / "2. Ассоциации"
            translations = case_dir / "source_documents" / "translations" / "2. Ассоциации"
            (originals / "Московская ассоциация предпринимателей, Октябрь 2024").mkdir(parents=True)
            (translations / "МАП").mkdir(parents=True)
            (originals / "Московская ассоциация предпринимателей, Октябрь 2024" / "rules.txt").write_text(
                "rules", encoding="utf-8"
            )
            (translations / "МАП" / "rules translation.txt").write_text("translation", encoding="utf-8")
            loaded = workflow_module.LoadedCase(
                case_id="case_001",
                case_dir=case_dir,
                config={
                    "paths": {
                        "source_originals": "source_documents/originals",
                        "source_translations": "source_documents/translations",
                        "source_other": "source_documents/other",
                    },
                    "eb1a_folder_roles": {"memberships": "2. Ассоциации"},
                },
                workflow={},
            )
            step = {"step_id": "criterion_memberships_episode", "evidence_folder_roles": ["memberships"]}
            candidates = workflow_module._repeatable_episode_candidates(loaded, step)
            self.assertEqual(
                candidates,
                [
                    (
                        "Московская_ассоциация_предпринимателей_Октябрь_2024",
                        "Московская ассоциация предпринимателей, Октябрь 2024",
                    )
                ],
            )
            self.assertGreater(
                workflow_module._episode_folder_similarity(
                    "МАП", "Московская ассоциация предпринимателей, Октябрь 2024"
                ),
                0.9,
            )

    def test_petition_draft_validator_rejects_workflow_language_and_wrong_criterion_prefix(self) -> None:
        with TemporaryDirectory() as temp:
            case_dir = Path(temp)
            episode = case_dir / "source_documents" / "originals" / "2. Ассоциации" / "MEA"
            episode.mkdir(parents=True)
            (episode / "membership.txt").write_text("membership", encoding="utf-8")
            loaded = workflow_module.LoadedCase(
                case_id="case_001",
                case_dir=case_dir,
                config={
                    "paths": {
                        "source_originals": "source_documents/originals",
                        "source_translations": "source_documents/translations",
                        "source_other": "source_documents/other",
                    },
                    "eb1a_folder_roles": {"memberships": "2. Ассоциации"},
                },
                workflow={},
            )
            step = {
                "step_id": "criterion_memberships_episode",
                "execution": "llm_manual_repeatable",
                "evidence_folder_roles": ["memberships"],
            }
            options = workflow_module.PromptOptions(episode_id="MEA", episode_folder="MEA")
            with self.assertRaisesRegex(SystemExit, "internal workflow/AI language"):
                workflow_module._validate_human_facing_draft_text(
                    "Source prompt and selected evidence reviewed: this episode concerns membership.",
                    loaded,
                    step,
                    options,
                )
            with self.assertRaisesRegex(SystemExit, "wrong criterion"):
                workflow_module._validate_human_facing_draft_text(
                    "Within the Exhibit, the following documents are attached:\n\n1.1.1. Membership certificate.",
                    loaded,
                    step,
                    options,
                )

    def test_custom_unit_instructions_are_persisted_and_rendered_as_highest_priority(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = root / "case_workspace" / "case_001"
            schema_dir = root / "schemas"
            case_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            (schema_dir / "llm_section_output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
            loaded = workflow_module.LoadedCase(
                case_id="case_001",
                case_dir=case_dir,
                config={"task_type": "eb1a_petition", "paths": {"final_memo": "final_memo"}},
                workflow={"task_type": "eb1a_petition", "instruction_sources": {}},
            )
            step = {
                "step_id": "professional_biography",
                "execution": "llm_manual",
                "title": "Biography",
                "objective": "Draft biography.",
            }
            workflow_module.save_custom_prompt_instructions(
                loaded,
                "professional_biography",
                "",
                "Emphasize the 110,000 sq. m. portfolio and avoid generic praise.",
            )
            with patch.object(workflow_module, "PROJECT_ROOT", root):
                prompt = workflow_module.render_prompt(loaded, step, [])
            self.assertIn("Custom instructions for this drafting unit (highest priority)", prompt)
            self.assertIn("Emphasize the 110,000 sq. m. portfolio", prompt)
            self.assertEqual(
                workflow_module.read_custom_prompt_instructions(loaded, "professional_biography"),
                "Emphasize the 110,000 sq. m. portfolio and avoid generic praise.",
            )

    def test_web_parser_accepts_host_and_port(self) -> None:
        args = web.build_parser().parse_args(["--host", "127.0.0.1", "--port", "8010"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8010)

    def test_web_run_next_keeps_full_explanation(self) -> None:
        report = "Case: case_001\nNext action: edit_case_config\n\nMissing procedural_context"
        with patch.object(web, "run_next_report", return_value=report):
            message = web.handle_action("run_next", "case_001", {"build_prompt": "on"})
        self.assertEqual(message, report)

    def test_init_case_creates_eb1a_rfe_workspace(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            template_root = case_root / "_template"
            (template_root / "source_documents" / "originals").mkdir(parents=True)
            (template_root / "source_documents" / "translations").mkdir(parents=True)
            (template_root / "source_documents" / "other").mkdir(parents=True)
            (template_root / "indexes").mkdir(parents=True)
            (template_root / "generated_prompts").mkdir(parents=True)
            (template_root / "llm_outputs").mkdir(parents=True)
            (template_root / "validated_outputs").mkdir(parents=True)
            (template_root / "draft_sections").mkdir(parents=True)
            (template_root / "extracted_text").mkdir(parents=True)
            (template_root / "manual_descriptions").mkdir(parents=True)
            (template_root / "case_config.yaml").write_text(
                "case_id: __CASE_ID__\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "field: __REQUIRED__\n"
                "specialization: __REQUIRED__\n"
                "procedural_context: __REQUIRED__\n"
                "drafting_objective: __REQUIRED__\n"
                "source_folder_template: templates/EB1A/case_folders_template\n"
                "beneficiary:\n"
                "  full_name: __REQUIRED__\n"
                "  preferred_reference: __REQUIRED__\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  extracted_text: extracted_text\n"
                "  document_index: indexes/document_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  validated_outputs: validated_outputs\n",
                encoding="utf-8",
            )
            (template_root / "indexes" / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            eb1a_folder = root / "templates" / "EB1A" / "case_folders_template" / "1. Награды" / "1 episode"
            eb1a_folder.mkdir(parents=True)

            with (
                patch.object(cli_support, "PROJECT_ROOT", root),
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(cli_support, "CASE_TEMPLATE_ROOT", template_root),
            ):
                case_dir = cli_support.create_case_from_template("rfe_001", "eb1a_rfe_response")

            self.assertTrue((case_dir / "source_documents" / "rfe" / "notice").is_dir())
            self.assertTrue((case_dir / "source_documents" / "initial_filing" / "memorandum").is_dir())
            self.assertTrue((case_dir / "source_documents" / "rfe_response" / "new_documents" / "issues").is_dir())
            self.assertTrue((case_dir / "rfe_response_plan.md").exists())
            self.assertTrue(
                (case_dir / "source_documents" / "rfe_response" / "new_documents" / "issues" / "1. Награды").is_dir()
            )
            config = (case_dir / "case_config.yaml").read_text(encoding="utf-8")
            self.assertIn("task_type: eb1a_rfe_response", config)
            self.assertIn("source_rfe_notice: source_documents/rfe/notice", config)
            self.assertIn("rfe_metadata:", config)

    def test_web_lists_cases_from_case_root(self) -> None:
        with TemporaryDirectory() as temp:
            case_root = Path(temp) / "case_workspace"
            (case_root / "_template").mkdir(parents=True)
            (case_root / "case_002").mkdir()
            (case_root / "case_001").mkdir()

            with patch.object(web, "CASE_ROOT", case_root):
                self.assertEqual(web.list_cases(), ["case_001", "case_002"])

    def test_web_file_route_blocks_path_escape(self) -> None:
        with TemporaryDirectory() as temp:
            case_root = Path(temp) / "case_workspace"
            case_dir = case_root / "case_001"
            case_dir.mkdir(parents=True)
            (case_dir / "safe.txt").write_text("safe", encoding="utf-8")

            with patch.object(web, "CASE_ROOT", case_root):
                self.assertEqual(web.read_case_file("case_001", "safe.txt"), "safe")
                with self.assertRaises(ValueError):
                    web.read_case_file("case_001", "../outside.txt")

    def test_web_case_search_accepts_quoted_absolute_windows_path(self) -> None:
        case_dir = Path("C:/Cases/kim_test")
        query = web._case_search_query(
            '"C:\\Cases\\kim_test\\source_documents\\originals\\Biography.docx"',
            case_dir,
        )
        self.assertEqual(query, "source_documents/originals/biography.docx")

    def test_draft_parser_accepts_expected_command(self) -> None:
        args = draft.build_parser().parse_args(
            ["build-prompt", "--case", "case_001", "--step", "criterion_awards_episode", "--episode-id", "1"]
        )
        self.assertEqual(args.command, "build-prompt")
        self.assertEqual(args.case_id, "case_001")
        self.assertEqual(args.step, "criterion_awards_episode")
        self.assertEqual(args.episode_id, "1")

    def test_bundle_parser_accepts_dry_run(self) -> None:
        args = bundle.build_parser().parse_args(
            ["build", "--case", "case_001", "--dry-run"]
        )
        self.assertEqual(args.command, "build")
        self.assertTrue(args.dry_run)

    def test_bundle_parser_accepts_build_index(self) -> None:
        args = bundle.build_parser().parse_args(["build-index", "--case", "case_001"])
        self.assertEqual(args.command, "build-index")
        self.assertEqual(args.case_id, "case_001")

    def test_bundle_parser_accepts_separators(self) -> None:
        args = bundle.build_parser().parse_args(["separators", "--case", "case_001"])
        self.assertEqual(args.command, "separators")
        self.assertEqual(args.case_id, "case_001")

    def test_bundle_parser_accepts_separator_pdfs(self) -> None:
        args = bundle.build_parser().parse_args(["separator-pdfs", "--case", "case_001"])
        self.assertEqual(args.command, "separator-pdfs")
        self.assertEqual(args.case_id, "case_001")

    def test_draft_parser_accepts_scan_documents(self) -> None:
        args = draft.build_parser().parse_args(["scan-documents", "--case", "case_001"])
        self.assertEqual(args.command, "scan-documents")
        self.assertEqual(args.case_id, "case_001")

    def test_draft_parser_accepts_link_translations(self) -> None:
        args = draft.build_parser().parse_args(["link-translations", "--case", "case_001"])
        self.assertEqual(args.command, "link-translations")
        self.assertEqual(args.case_id, "case_001")

    def test_draft_parser_accepts_status(self) -> None:
        args = draft.build_parser().parse_args(["status", "--case", "case_001"])
        self.assertEqual(args.command, "status")
        self.assertEqual(args.case_id, "case_001")

    def test_draft_parser_accepts_run_next(self) -> None:
        args = draft.build_parser().parse_args(["run-next", "--case", "case_001", "--build-prompt"])
        self.assertEqual(args.command, "run-next")
        self.assertEqual(args.case_id, "case_001")
        self.assertTrue(args.build_prompt)

    def test_init_case_creates_workspace_and_refuses_overwrite(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            template_root = case_root / "_template"
            (template_root / "source_documents" / "originals").mkdir(parents=True)
            (template_root / "case_config.yaml").write_text(
                "case_id: __CASE_ID__\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n",
                encoding="utf-8",
            )
            eb1a_folder = root / "templates" / "EB1A" / "case_folders_template" / "1. Награды"
            eb1a_folder.mkdir(parents=True)

            with (
                patch.object(cli_support, "PROJECT_ROOT", root),
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(cli_support, "CASE_TEMPLATE_ROOT", template_root),
            ):
                target = cli_support.create_case_from_template("case_001", "eb1a_petition")
                self.assertTrue((target / "case_config.yaml").exists())
                self.assertTrue((target / "source_documents" / "originals" / "1. Награды").is_dir())
                config = (target / "case_config.yaml").read_text(encoding="utf-8")
                self.assertIn("case_id: case_001", config)
                with self.assertRaises(SystemExit):
                    cli_support.create_case_from_template("case_001", "eb1a_petition")

    def test_eb1a_workflow_is_valid_yaml_and_has_first_drafting_step(self) -> None:
        workflow = load_yaml_file(Path("workflows/eb1a_petition.yaml"))
        self.assertEqual(workflow["task_type"], "eb1a_petition")
        step = find_step(workflow, "professional_biography")
        self.assertEqual(step["execution"], "llm_manual")

    def test_machine_templates_are_parseable_for_working_memo_builder(self) -> None:
        eb1a = parse_machine_template(Path("templates/EB1A/EB1A_unified_template_LLM.docx"))
        rfe = parse_machine_template(Path("templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.txt"))
        self.assertGreaterEqual(eb1a.placeholder_count, 10)
        self.assertGreaterEqual(eb1a.section_count, 20)
        self.assertIn("__BENEFICIARY_FULL_NAME__", eb1a.placeholders)
        self.assertGreaterEqual(rfe.section_count, 10)
        self.assertGreaterEqual(rfe.placeholder_count, 10)
        self.assertIn("[CASE_NO]", rfe.placeholders)
        self.assertTrue(any("COVER LETTER" in section.title for section in rfe.sections))

    def test_apply_intake_and_build_working_memo_docx(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            template_dir = root / "templates" / "EB1A"
            indexes_dir = case_dir / "indexes"
            external_originals = root / "incoming originals"
            external_translations = root / "incoming translations"
            source_dir = case_dir / "source_documents" / "originals" / "1. Награды" / "1 episode"
            for folder in [
                workflow_dir,
                template_dir,
                indexes_dir,
                source_dir,
                case_dir / "source_documents" / "translations",
                case_dir / "source_documents" / "other",
                case_dir / "final_memo",
                case_dir / "reports",
                case_dir / "generated_prompts",
                case_dir / "validated_outputs",
                case_dir / "extracted_text",
                case_dir / "manual_descriptions",
            ]:
                folder.mkdir(parents=True, exist_ok=True)
            external_originals.mkdir(parents=True)
            external_translations.mkdir(parents=True)
            (source_dir / "award.txt").write_text("Award evidence", encoding="utf-8")
            (external_originals / "new-original.txt").write_text("Original", encoding="utf-8")
            (external_translations / "new-translation.txt").write_text("Translation", encoding="utf-8")
            (template_dir / "machine_template.txt").write_text(
                "EB-1A TEMPLATE\n\n"
                "__BENEFICIARY_FULL_NAME__\n"
                "__FIELD__\n"
                "1. COVER LETTER\n"
                "2. EVIDENCE MAP\n",
                encoding="utf-8",
            )
            (template_dir / "working_structure.yaml").write_text(
                "document:\n"
                "  petition_title: Petition for Permanent Residence under Extraordinary Ability (EB-1A)\n"
                "table_of_contents: []\n"
                "criteria:\n"
                "  awards:\n"
                "    roman: i\n"
                "    section: B.i.\n"
                "    title: Evidence of receipt of nationally or internationally recognized prizes or awards for excellence.\n"
                "    cover_text: Evidence of {possessive_reference} receipt of nationally or internationally recognized prizes or awards for excellence\n"
                "    step_ids: [criterion_awards_episode]\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "field: __REQUIRED__\n"
                "specialization: __REQUIRED__\n"
                "procedural_context: Initial petition\n"
                "drafting_objective: Prepare EB1A memo\n"
                "working_document_template: templates/EB1A/working_structure.yaml\n"
                "beneficiary:\n"
                "  full_name: __REQUIRED__\n"
                "  preferred_reference: __REQUIRED__\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  final_memo: final_memo\n"
                "  document_index: indexes/document_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  validated_outputs: validated_outputs\n"
                "eb1a_folder_roles:\n"
                "  awards: \"1. Награды\"\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
                patch("app.memo_builder.PROJECT_ROOT", root),
            ):
                intake = apply_case_intake(
                    "case_001",
                    {
                        "beneficiary_full_name": "Jane Doe",
                        "preferred_reference": "Ms. Doe",
                        "field": "Arts",
                        "specialization": "Film production",
                    },
                    source_folder_paths={
                        "source_originals": f'"{external_originals}"',
                        "source_translations": str(external_translations),
                        "source_other": "",
                    },
                )
                summary = build_working_memo(
                    "case_001",
                    template_path="templates/EB1A/machine_template.txt",
                )

            self.assertGreaterEqual(intake.fields_updated, 4)
            self.assertTrue(summary.docx_path.exists())
            self.assertTrue(summary.markdown_path.exists())
            self.assertTrue(summary.template_report_path.exists())
            with zipfile.ZipFile(summary.docx_path) as archive:
                self.assertIn("word/document.xml", archive.namelist())
                document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("Jane Doe", document_xml)
            self.assertIn("nationally or internationally recognized prizes", document_xml)
            self.assertNotIn("__REQUIRED__", document_xml)
            self.assertTrue((case_dir / "source_documents" / "originals" / "new-original.txt").exists())
            self.assertTrue((case_dir / "source_documents" / "translations" / "new-translation.txt").exists())
            saved_config = (case_dir / "case_config.yaml").read_text(encoding="utf-8")
            self.assertIn("source_imports:", saved_config)
            self.assertIn(str(external_originals), saved_config)

    def test_eb1a_rfe_issue_prompt_includes_rfe_initial_and_new_docs(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "rfe_001"
            workflow_dir = root / "workflows"
            instructions_dir = root / "instructions" / "task_types" / "eb1a_rfe_response" / "sections"
            task_rules_dir = root / "instructions" / "task_types" / "eb1a_rfe_response"
            schema_dir = root / "schemas"
            template_dir = root / "templates" / "RFE" / "EB1"
            indexes_dir = case_dir / "indexes"
            rfe_issue_dir = case_dir / "source_documents" / "rfe" / "issues" / "awards"
            initial_issue_dir = case_dir / "source_documents" / "initial_filing" / "issues" / "awards"
            new_issue_dir = case_dir / "source_documents" / "rfe_response" / "new_documents" / "issues" / "awards"
            strategy_dir = case_dir / "source_documents" / "rfe_response" / "strategy"
            for folder in [
                workflow_dir,
                instructions_dir,
                task_rules_dir,
                schema_dir,
                template_dir,
                indexes_dir,
                rfe_issue_dir,
                initial_issue_dir,
                new_issue_dir,
                strategy_dir,
                case_dir / "generated_prompts",
                case_dir / "validated_outputs",
                case_dir / "extracted_text",
                case_dir / "manual_descriptions",
                case_dir / "source_documents" / "originals",
                case_dir / "source_documents" / "translations",
                case_dir / "source_documents" / "other",
            ]:
                folder.mkdir(parents=True, exist_ok=True)
            (schema_dir / "llm_section_output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
            (task_rules_dir / "task_rules.md").write_text("RFE task rules", encoding="utf-8")
            (instructions_dir / "rfe_issue_response.md").write_text("Issue response rules", encoding="utf-8")
            (template_dir / "EB1A_RFE_response_unified_LLM_template.txt").write_text(
                "RFE response template", encoding="utf-8"
            )
            (rfe_issue_dir / "rfe.txt").write_text("USCIS says the award evidence is insufficient.", encoding="utf-8")
            (initial_issue_dir / "initial.txt").write_text("Initial filing cited Exhibit E-1 for awards.", encoding="utf-8")
            (new_issue_dir / "new.txt").write_text("New award confirmation letter.", encoding="utf-8")
            (strategy_dir / "strategy.md").write_text("Strategy: argue USCIS overlooked Exhibit E-1.", encoding="utf-8")
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (case_dir / "case_config.yaml").write_text(
                "case_id: rfe_001\n"
                "task_type: eb1a_rfe_response\n"
                "workflow: workflows/eb1a_rfe_response.yaml\n"
                "field: Arts\n"
                "specialization: Film production\n"
                "procedural_context: RFE response\n"
                "drafting_objective: Prepare RFE response\n"
                "beneficiary:\n"
                "  full_name: Jane Doe\n"
                "  preferred_reference: Ms. Doe\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  source_rfe_issues: source_documents/rfe/issues\n"
                "  source_initial_filing_issues: source_documents/initial_filing/issues\n"
                "  source_rfe_new_issue_documents: source_documents/rfe_response/new_documents/issues\n"
                "  source_rfe_strategy: source_documents/rfe_response/strategy\n"
                "  extracted_text: extracted_text\n"
                "  document_index: indexes/document_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  validated_outputs: validated_outputs\n"
                "rfe_metadata:\n"
                "  case_number: SRC0000000000\n"
                "  receipt_date: 2026-01-01\n"
                "  rfe_date: 2026-06-01\n"
                "  response_deadline: 2026-09-01\n"
                "  uscis_address: USCIS\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_rfe_response.yaml").write_text(
                "task_type: eb1a_rfe_response\n"
                "instruction_sources:\n"
                "  universal: []\n"
                "  visa_or_rfe_specific:\n"
                "    - templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.txt\n"
                "  task_type:\n"
                "    - instructions/task_types/eb1a_rfe_response/task_rules.md\n"
                "steps:\n"
                "  - step_id: rfe_issue_response\n"
                "    execution: llm_manual_repeatable\n"
                "    title: RFE issue response\n"
                "    objective: Draft one issue.\n"
                "    section_instructions: instructions/task_types/eb1a_rfe_response/sections/rfe_issue_response.md\n"
                "    evidence_sources:\n"
                "      - label: RFE text for this issue\n"
                "        path_key: source_rfe_issues\n"
                "        folder: .\n"
                "        use_episode_folder: true\n"
                "      - label: Initial filing text/evidence list for this issue\n"
                "        path_key: source_initial_filing_issues\n"
                "        folder: .\n"
                "        use_episode_folder: true\n"
                "      - label: New documents for this RFE issue\n"
                "        path_key: source_rfe_new_issue_documents\n"
                "        folder: .\n"
                "        use_episode_folder: true\n"
                "      - label: Global and issue-specific strategy notes\n"
                "        path_key: source_rfe_strategy\n"
                "        folder: .\n"
                "    destination_pattern: draft_sections/rfe/issues/{episode_id}.md\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                scan_documents("rfe_001")
                prompt_path = workflow_module.build_prompt(
                    "rfe_001",
                    "rfe_issue_response",
                    [],
                    episode_id="awards",
                    episode_folder="awards",
                )

            prompt = prompt_path.read_text(encoding="utf-8")
            self.assertIn("USCIS says the award evidence is insufficient.", prompt)
            self.assertIn("Initial filing cited Exhibit E-1 for awards.", prompt)
            self.assertIn("New award confirmation letter.", prompt)
            self.assertIn("Strategy: argue USCIS overlooked Exhibit E-1.", prompt)

    def test_scan_documents_indexes_text_and_image_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            source_dir = case_dir / "source_documents" / "originals" / "1. Награды"
            translation_dir = case_dir / "source_documents" / "translations"
            other_dir = case_dir / "source_documents" / "other"
            indexes_dir = case_dir / "indexes"
            extracted_dir = case_dir / "extracted_text"
            source_dir.mkdir(parents=True)
            translation_dir.mkdir(parents=True)
            other_dir.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            (source_dir / "award.txt").write_text("Award text", encoding="utf-8")
            (source_dir / "photo.jpg").write_bytes(b"fake-image")
            (indexes_dir / "document_index.csv").write_text(
                ",".join([
                    "document_id",
                    "original_file_name",
                    "display_title",
                    "file_path",
                    "document_type",
                    "category",
                    "task_type_relevance",
                    "memo_section_relevance",
                    "exhibit_number",
                    "parent_document_id",
                    "translation_status",
                    "relationship_type",
                    "document_date",
                    "person_or_organization",
                    "short_description",
                    "extraction_status",
                    "text_extraction_path",
                    "user_approval_status",
                    "separator_title_type",
                    "final_bundle_order",
                    "source_fingerprint",
                    "last_scanned_at",
                    "manual_edit_lock",
                    "notes",
                ])
                + "\n",
                encoding="utf-8",
            )
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  extracted_text: extracted_text\n"
                "  document_index: indexes/document_index.csv\n"
                "eb1a_folder_roles:\n"
                "  awards: \"1. Награды\"\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = scan_documents("case_001")

            self.assertEqual(summary.scanned_files, 2)
            self.assertEqual(summary.added_rows, 2)
            self.assertEqual(summary.extracted_texts, 1)
            self.assertEqual(summary.non_text_files, 1)
            self.assertTrue((extracted_dir / "DOC0001.txt").exists())
            manual_description = case_dir / "manual_descriptions" / "DOC0002.md"
            self.assertTrue(manual_description.exists())
            index_text = (indexes_dir / "document_index.csv").read_text(encoding="utf-8")
            self.assertIn("text_extracted", index_text)
            self.assertIn("image_or_photo", index_text)

            manual_description.write_text(
                "# Manual description for DOC0002\n\n"
                "## Description for LLM\n\n"
                "The photo shows the award certificate issued to the beneficiary.\n",
                encoding="utf-8",
            )
            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                second_summary = scan_documents("case_001")

            self.assertEqual(second_summary.extracted_texts, 2)
            index_text = (indexes_dir / "document_index.csv").read_text(encoding="utf-8")
            self.assertIn("manual_description_available", index_text)
            self.assertIn("manual_descriptions/DOC0002.md", index_text)

    def test_repeatable_episode_prompt_import_and_insert(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            template_root = case_root / "_template"
            workflow_dir = root / "workflows"
            instructions_dir = root / "instructions" / "task_types" / "eb1a_petition" / "sections"
            schema_dir = root / "schemas"
            template_source = root / "templates" / "EB1A" / "case_folders_template" / "1. Награды" / "1 episode"
            (template_root / "source_documents" / "originals").mkdir(parents=True)
            (template_root / "source_documents" / "translations").mkdir(parents=True)
            (template_root / "source_documents" / "other").mkdir(parents=True)
            (template_root / "indexes").mkdir(parents=True)
            (template_root / "extracted_text").mkdir(parents=True)
            (template_root / "generated_prompts").mkdir(parents=True)
            (template_root / "llm_outputs").mkdir(parents=True)
            (template_root / "validated_outputs").mkdir(parents=True)
            (template_root / "draft_sections").mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            instructions_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            template_source.mkdir(parents=True)
            (template_source / "award.txt").write_text("Award evidence", encoding="utf-8")
            (instructions_dir / "criterion_episode.md").write_text("Criterion instruction", encoding="utf-8")
            (schema_dir / "llm_section_output.schema.json").write_text(
                '{"type":"object"}', encoding="utf-8"
            )
            (template_root / "case_config.yaml").write_text(
                "case_id: __CASE_ID__\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  extracted_text: extracted_text\n"
                "  document_index: indexes/document_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  llm_outputs: llm_outputs\n"
                "  validated_outputs: validated_outputs\n"
                "eb1a_folder_roles:\n"
                "  awards: \"1. Награды\"\n",
                encoding="utf-8",
            )
            (template_root / "indexes" / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\n"
                "instruction_sources:\n"
                "  universal: []\n"
                "  task_type: []\n"
                "  visa_or_rfe_specific: []\n"
                "steps:\n"
                "  - step_id: criterion_awards_episode\n"
                "    execution: llm_manual_repeatable\n"
                "    title: Awards episode\n"
                "    objective: Draft awards episode.\n"
                "    section_instructions: instructions/task_types/eb1a_petition/sections/criterion_episode.md\n"
                "    evidence_folder_roles:\n"
                "      - awards\n"
                "    destination_pattern: draft_sections/criteria/awards/{episode_id}.md\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "PROJECT_ROOT", root),
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(cli_support, "CASE_TEMPLATE_ROOT", template_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                case_dir = cli_support.create_case_from_template("case_001", "eb1a_petition")
                scan_documents("case_001")
                prompt_path = workflow_module.build_prompt(
                    "case_001",
                    "criterion_awards_episode",
                    [],
                    episode_id="1",
                    episode_folder="1 episode",
                )
                self.assertIn("criterion_awards_episode.1.", prompt_path.name)
                output_path = case_dir / "llm_outputs" / "award.json"
                output_path.write_text(
                    "{\n"
                    '  "case_id": "case_001",\n'
                    '  "task_type": "eb1a_petition",\n'
                    '  "step_id": "criterion_awards_episode",\n'
                    '  "episode_id": "1",\n'
                    '  "draft_text": "Award criterion text with enough substance for validation checks.",\n'
                    '  "used_documents": [{"document_id": "DOC0001", "document_title": "award.txt", "used_for": "episode evidence"}],\n'
                    '  "unsupported_claims": [],\n'
                    '  "questions_for_user": [],\n'
                    '  "quality_flags": [],\n'
                    '  "revision_notes": []\n'
                    "}\n",
                    encoding="utf-8",
                )
                workflow_module.import_llm_output(
                    "case_001", "criterion_awards_episode", str(output_path), episode_id="1"
                )
                target = workflow_module.insert_section(
                    "case_001", "criterion_awards_episode", episode_id="1"
                )

            self.assertEqual(target.name, "1.md")
            self.assertEqual(
                target.read_text(encoding="utf-8").strip(),
                "Award criterion text with enough substance for validation checks.",
            )

    def test_run_next_reports_config_then_builds_first_prompt(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            instructions_dir = root / "instructions" / "task_types" / "eb1a_petition" / "sections"
            schema_dir = root / "schemas"
            indexes_dir = case_dir / "indexes"
            case_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            instructions_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)
            (case_dir / "source_documents" / "originals").mkdir(parents=True)
            (case_dir / "source_documents" / "translations").mkdir(parents=True)
            (case_dir / "source_documents" / "other").mkdir(parents=True)
            (case_dir / "user_case_instructions.md").write_text("", encoding="utf-8")
            (schema_dir / "llm_section_output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
            (instructions_dir / "opening_context_intake.md").write_text("Opening intake instruction", encoding="utf-8")
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (indexes_dir / "exhibit_index.csv").write_text(
                "exhibit_id,exhibit_number,parent_exhibit_id,display_title,evidentiary_thesis,"
                "task_type,memo_section,separator_title_type,document_ids,original_translation_order,"
                "final_bundle_order,user_approval_status,manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\n"
                "instruction_sources:\n"
                "  universal: []\n"
                "  task_type: []\n"
                "  visa_or_rfe_specific: []\n"
                "  case_specific: user_case_instructions.md\n"
                "steps:\n"
                "  - step_id: opening_context_intake\n"
                "    execution: llm_manual\n"
                "    title: Opening context\n"
                "    objective: Read context only.\n"
                "    section_instructions: instructions/task_types/eb1a_petition/sections/opening_context_intake.md\n"
                "    destination: draft_sections/_context_notes.md\n",
                encoding="utf-8",
            )
            config_path = case_dir / "case_config.yaml"
            config_path.write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "beneficiary:\n"
                "  full_name: __REQUIRED__\n"
                "  preferred_reference: __REQUIRED__\n"
                "field: __REQUIRED__\n"
                "specialization: __REQUIRED__\n"
                "procedural_context: __REQUIRED__\n"
                "drafting_objective: __REQUIRED__\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  document_index: indexes/document_index.csv\n"
                "  exhibit_index: indexes/exhibit_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  validated_outputs: validated_outputs\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                report = workflow_module.run_next_report("case_001")
                self.assertIn("edit_case_config", report)

                config_path.write_text(
                    config_path.read_text(encoding="utf-8")
                    .replace("__REQUIRED__", "Jane Doe", 1)
                    .replace("__REQUIRED__", "Dr. Doe", 1)
                    .replace("__REQUIRED__", "AI Engineering", 1)
                    .replace("__REQUIRED__", "Machine learning systems", 1)
                    .replace("__REQUIRED__", "Initial petition", 1)
                    .replace("__REQUIRED__", "Prepare EB1A memo", 1),
                    encoding="utf-8",
                )
                report = workflow_module.run_next_report("case_001", build_prompt_file=True)

            self.assertIn("Created prompt:", report)
            self.assertTrue((case_dir / "generated_prompts" / "opening_context_intake.latest.prompt.md").exists())

    def test_link_translations_pairs_original_then_translation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            instructions_dir = root / "instructions" / "task_types" / "eb1a_petition" / "sections"
            schema_dir = root / "schemas"
            original_dir = case_dir / "source_documents" / "originals" / "1. Награды" / "1 episode"
            translation_dir = case_dir / "source_documents" / "translations" / "1. Награды" / "1 episode"
            indexes_dir = case_dir / "indexes"
            (case_dir / "source_documents" / "other").mkdir(parents=True)
            original_dir.mkdir(parents=True)
            translation_dir.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            instructions_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            (original_dir / "award.jpg").write_bytes(b"fake-original-image")
            (translation_dir / "award translation.txt").write_text(
                "English translation of the award certificate.", encoding="utf-8"
            )
            (schema_dir / "llm_section_output.schema.json").write_text(
                '{"type":"object"}', encoding="utf-8"
            )
            (instructions_dir / "criterion_episode.md").write_text("Instruction", encoding="utf-8")
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n",
                encoding="utf-8",
            )
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  source_originals: source_documents/originals\n"
                "  source_translations: source_documents/translations\n"
                "  source_other: source_documents/other\n"
                "  extracted_text: extracted_text\n"
                "  manual_descriptions: manual_descriptions\n"
                "  document_index: indexes/document_index.csv\n"
                "  generated_prompts: generated_prompts\n"
                "  validated_outputs: validated_outputs\n"
                "translation_order: original_then_translation\n"
                "eb1a_folder_roles:\n"
                "  awards: \"1. Награды\"\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\n"
                "instruction_sources:\n"
                "  universal: []\n"
                "  task_type: []\n"
                "  visa_or_rfe_specific: []\n"
                "steps:\n"
                "  - step_id: criterion_awards_episode\n"
                "    execution: llm_manual_repeatable\n"
                "    title: Awards episode\n"
                "    objective: Draft awards episode.\n"
                "    section_instructions: instructions/task_types/eb1a_petition/sections/criterion_episode.md\n"
                "    evidence_folder_roles:\n"
                "      - awards\n"
                "    destination_pattern: draft_sections/criteria/awards/{episode_id}.md\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                scan_documents("case_001")
                summary = link_translations("case_001")
                prompt_path = workflow_module.build_prompt(
                    "case_001",
                    "criterion_awards_episode",
                    [],
                    episode_id="1",
                    episode_folder="1 episode",
                )

            self.assertEqual(summary.linked_translations, 1)
            index_text = (indexes_dir / "document_index.csv").read_text(encoding="utf-8")
            self.assertIn("relationship_type", index_text)
            self.assertIn("translation", index_text)
            self.assertIn("DOC0001", index_text)
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("parent_document_id: DOC0001", prompt_text)
            self.assertIn("bundle_order_hint: original first, then this translation", prompt_text)

    def test_manual_translation_link_reassigns_original_and_supports_intentional_sharing(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            original = case_dir / "source_documents" / "originals" / "original.pdf"
            translation_one = case_dir / "source_documents" / "translations" / "translation-one.pdf"
            translation_two = case_dir / "source_documents" / "translations" / "translation-two.pdf"
            indexes_dir = case_dir / "indexes"
            workflow_dir = root / "workflows"
            original.parent.mkdir(parents=True)
            translation_one.parent.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            original.write_bytes(b"original")
            translation_one.write_bytes(b"translation-one")
            translation_two.write_bytes(b"translation-two")
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  document_index: indexes/document_index.csv\n",
                encoding="utf-8",
            )
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,file_path,translation_status,parent_document_id,relationship_type,notes\n"
                "DOC0001,original.pdf,source_documents/originals/original.pdf,original,,,\n"
                "DOC0002,translation-one.pdf,source_documents/translations/translation-one.pdf,translation,,,\n"
                "DOC0003,translation-two.pdf,source_documents/translations/translation-two.pdf,translation,,,\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = manual_link_translation("case_001", "DOC0002", f'"{original}"')
                self.assertEqual(summary.original_document_id, "DOC0001")
                reassigned = manual_link_translation("case_001", "DOC0003", "DOC0001")
                self.assertEqual(reassigned.displaced_translation_ids, ("DOC0002",))
                link_translations("case_001", auto_match=False)
                shared = manual_link_translation(
                    "case_001", "DOC0002", "DOC0001", allow_shared_original=True
                )
                self.assertEqual(shared.translation_document_id, "DOC0002")
                self.assertEqual(shared.displaced_translation_ids, ())
                unlink_translation("case_001", "DOC0002")

            index_text = (indexes_dir / "document_index.csv").read_text(encoding="utf-8")
            self.assertIn("DOC0003", index_text)
            self.assertIn("DOC0001", index_text)
            doc_two_row = next(line for line in index_text.splitlines() if line.startswith("DOC0002,"))
            doc_three_row = next(line for line in index_text.splitlines() if line.startswith("DOC0003,"))
            self.assertNotIn(",DOC0001,", doc_two_row)
            self.assertIn(",DOC0001,", doc_three_row)

    def test_build_exhibit_index_orders_original_before_translation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            indexes_dir = case_dir / "indexes"
            indexes_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "translation_order: original_then_translation\n"
                "paths:\n"
                "  document_index: indexes/document_index.csv\n"
                "  exhibit_index: indexes/exhibit_index.csv\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n"
                "DOC0001,award.jpg,Award Original,source_documents/originals/1. Награды/1 episode/award.jpg,image,awards,,awards,E-1,,original,original,,,,image_or_photo,,pending,document,,,,false,\n"
                "DOC0002,award translation.txt,Award Translation,source_documents/translations/1. Награды/1 episode/award translation.txt,text,awards,,awards,E-1,DOC0001,translation,translation,,,,text_extracted,extracted_text/DOC0002.txt,pending,document,,,,false,\n",
                encoding="utf-8",
            )
            (indexes_dir / "exhibit_index.csv").write_text(
                "exhibit_id,exhibit_number,parent_exhibit_id,display_title,evidentiary_thesis,"
                "task_type,memo_section,separator_title_type,document_ids,original_translation_order,"
                "final_bundle_order,user_approval_status,manual_edit_lock,notes\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = build_exhibit_index("case_001")

            self.assertEqual(summary.exhibits_created, 1)
            exhibit_text = (indexes_dir / "exhibit_index.csv").read_text(encoding="utf-8")
            self.assertIn("DOC0001;DOC0002", exhibit_text)
            self.assertIn("original_then_translation", exhibit_text)
            document_text = (indexes_dir / "document_index.csv").read_text(encoding="utf-8")
            self.assertIn("DOC0001", document_text)
            self.assertIn("DOC0002", document_text)

    def test_generate_separator_pages_from_indexes(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            indexes_dir = case_dir / "indexes"
            indexes_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "translation_order: original_then_translation\n"
                "paths:\n"
                "  document_index: indexes/document_index.csv\n"
                "  exhibit_index: indexes/exhibit_index.csv\n"
                "  bundle_root: bundle\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n"
                "DOC0001,award.jpg,Award Original,source_documents/originals/1. Награды/1 episode/award.jpg,image,awards,,awards,E-1,,original,original,,,,Award certificate original,image_or_photo,,pending,document,1,,,false,\n"
                "DOC0002,award translation.txt,Award Translation,source_documents/translations/1. Награды/1 episode/award translation.txt,text,awards,,awards,E-1,DOC0001,translation,translation,,,,English translation,text_extracted,extracted_text/DOC0002.txt,pending,document,2,,,false,\n",
                encoding="utf-8",
            )
            (indexes_dir / "exhibit_index.csv").write_text(
                "exhibit_id,exhibit_number,parent_exhibit_id,display_title,evidentiary_thesis,"
                "task_type,memo_section,separator_title_type,document_ids,original_translation_order,"
                "final_bundle_order,user_approval_status,manual_edit_lock,notes\n"
                "EXH001,E-1,,Exhibit E-1,Award evidence,eb1a_petition,awards,exhibit,DOC0001;DOC0002,original_then_translation,1,pending,false,\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = generate_separator_pages("case_001")

            self.assertEqual(summary.exhibit_pages_written, 1)
            self.assertEqual(summary.document_pages_written, 2)
            exhibit_page = case_dir / "bundle" / "separators" / "generated" / "001_exhibit_E-1.md"
            translation_page = case_dir / "bundle" / "separators" / "generated" / "001_002_DOC0002.md"
            self.assertTrue(exhibit_page.exists())
            self.assertTrue(translation_page.exists())
            self.assertIn("DOC0001 - Award Original", exhibit_page.read_text(encoding="utf-8"))
            self.assertIn("translation of DOC0001", translation_page.read_text(encoding="utf-8"))

    def test_build_bundle_plan_reports_missing_separators_and_ready_source(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            indexes_dir = case_dir / "indexes"
            source_dir = case_dir / "source_documents" / "originals"
            indexes_dir.mkdir(parents=True)
            source_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            (source_dir / "award.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  document_index: indexes/document_index.csv\n"
                "  exhibit_index: indexes/exhibit_index.csv\n"
                "  bundle_root: bundle\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (indexes_dir / "document_index.csv").write_text(
                "document_id,original_file_name,display_title,file_path,document_type,category,"
                "task_type_relevance,memo_section_relevance,exhibit_number,parent_document_id,"
                "translation_status,relationship_type,document_date,person_or_organization,"
                "short_description,extraction_status,text_extraction_path,user_approval_status,"
                "separator_title_type,final_bundle_order,source_fingerprint,last_scanned_at,"
                "manual_edit_lock,notes\n"
                "DOC0001,award.pdf,Award PDF,source_documents/originals/award.pdf,pdf,awards,,awards,E-1,,original,original,,,,text_extracted,,pending,document,1,,,false,\n",
                encoding="utf-8",
            )
            (indexes_dir / "exhibit_index.csv").write_text(
                "exhibit_id,exhibit_number,parent_exhibit_id,display_title,evidentiary_thesis,"
                "task_type,memo_section,separator_title_type,document_ids,original_translation_order,"
                "final_bundle_order,user_approval_status,manual_edit_lock,notes\n"
                "EXH001,E-1,,Exhibit E-1,Award evidence,eb1a_petition,awards,exhibit,DOC0001,original_then_translation,1,pending,false,\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = build_bundle_plan("case_001")

            self.assertEqual(summary.total_items, 3)
            self.assertEqual(summary.source_documents, 1)
            self.assertEqual(summary.separator_pdfs, 2)
            self.assertEqual(summary.missing_items, 2)
            self.assertTrue(summary.plan_csv_path.exists())

    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "reportlab is not installed")
    def test_render_separator_pdfs_when_reportlab_available(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            case_root = root / "case_workspace"
            case_dir = case_root / "case_001"
            workflow_dir = root / "workflows"
            separator_dir = case_dir / "bundle" / "separators" / "generated"
            separator_dir.mkdir(parents=True)
            workflow_dir.mkdir(parents=True)
            (case_dir / "case_config.yaml").write_text(
                "case_id: case_001\n"
                "task_type: eb1a_petition\n"
                "workflow: workflows/eb1a_petition.yaml\n"
                "paths:\n"
                "  bundle_root: bundle\n",
                encoding="utf-8",
            )
            (workflow_dir / "eb1a_petition.yaml").write_text(
                "task_type: eb1a_petition\nsteps: []\n", encoding="utf-8"
            )
            (separator_dir / "001_exhibit_E-1.md").write_text(
                "# Exhibit E-1\n\n## Documents included\n\n1. DOC0001 - Award Original\n",
                encoding="utf-8",
            )

            with (
                patch.object(cli_support, "CASE_ROOT", case_root),
                patch.object(workflow_module, "PROJECT_ROOT", root),
            ):
                summary = render_separator_pdfs("case_001")

            self.assertEqual(summary.pdf_pages_written, 1)
            self.assertTrue((case_dir / "bundle" / "separators" / "pdf" / "001_exhibit_E-1.pdf").exists())


if __name__ == "__main__":
    unittest.main()
