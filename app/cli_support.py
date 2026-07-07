from __future__ import annotations

import argparse
import re
import shutil
import string
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASE_ROOT = PROJECT_ROOT / "case_workspace"
CASE_TEMPLATE_ROOT = CASE_ROOT / "_template"


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def add_case_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case", required=True, dest="case_id", help="Case folder name")


def validate_case_id(case_id: str) -> None:
    allowed = set(string.ascii_letters + string.digits + "_-")
    if not case_id or any(char not in allowed for char in case_id):
        raise SystemExit(
            "Case id may contain only Latin letters, numbers, underscores, and hyphens."
        )
    if case_id in {".", "..", "_template"}:
        raise SystemExit(f"Reserved case id: {case_id}")


def case_path(case_id: str) -> Path:
    validate_case_id(case_id)
    return CASE_ROOT / case_id


def create_case_from_template(case_id: str, task_type: str) -> Path:
    workflow_value = workflow_for(task_type)
    target = case_path(case_id)
    if target.exists():
        raise SystemExit(f"Case folder already exists and was not changed: {target}")
    if not CASE_TEMPLATE_ROOT.exists():
        raise SystemExit(f"Missing case template folder: {CASE_TEMPLATE_ROOT}")

    shutil.copytree(CASE_TEMPLATE_ROOT, target)
    config_path = target / "case_config.yaml"
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        text = text.replace("__CASE_ID__", case_id)
        text = text.replace("task_type: eb1a_petition", f"task_type: {task_type}")
        text = text.replace("workflow: workflows/eb1a_petition.yaml", workflow_value)
        if task_type == "eb1a_rfe_response":
            text = _rfe_case_config_text(text)
        elif task_type == "o1b_petition":
            text = _o1b_case_config_text(text)
        elif task_type == "document_layout":
            text = _document_layout_case_config_text(text)
        config_path.write_text(text, encoding="utf-8")

    if task_type == "eb1a_petition":
        source = PROJECT_ROOT / "templates" / "EB1A" / "case_folders_template"
        destination = target / "source_documents" / "originals"
        if source.exists():
            for child in source.iterdir():
                child_destination = destination / child.name
                if child.is_dir():
                    shutil.copytree(child, child_destination)
                else:
                    shutil.copy2(child, child_destination)
    elif task_type == "eb1a_rfe_response":
        _create_eb1a_rfe_structure(target)
    elif task_type == "o1b_petition":
        source = PROJECT_ROOT / "templates" / "O1B" / "case_folders_template"
        destination = target / "source_documents" / "originals"
        if source.exists():
            for child in source.iterdir():
                child_destination = destination / child.name
                if child.is_dir():
                    shutil.copytree(child, child_destination)
                else:
                    shutil.copy2(child, child_destination)
    elif task_type == "document_layout":
        (target / "document_layout").mkdir(parents=True, exist_ok=True)

    return target


def workflow_for(task_type: str) -> str:
    mapping = {
        "eb1a_petition": "workflow: workflows/eb1a_petition.yaml",
        "eb1a_rfe_response": "workflow: workflows/eb1a_rfe_response.yaml",
        "o1b_petition": "workflow: workflows/o1b_petition.yaml",
        "document_layout": "workflow: workflows/document_layout.yaml",
    }
    if task_type not in mapping:
        supported = ", ".join(sorted(mapping))
        raise SystemExit(
            f"Task type {task_type!r} is not implemented yet. Supported task types: {supported}. "
            "Add and test its workflow YAML before enabling case creation."
        )
    return mapping[task_type]


def _o1b_case_config_text(text: str) -> str:
    text = text.replace(
        "source_folder_template: templates/EB1A/case_folders_template",
        "source_folder_template: templates/O1B/case_folders_template",
    )
    text = text.replace(
        "working_document_template: templates/EB1A/EB1A_working_document_structure.yaml",
        "working_document_template: templates/O1B/O1B_working_document_structure.yaml",
    )
    text = re.sub(
        r"(?m)^procedural_context:\s*.*$",
        "procedural_context: Initial O-1B petition",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^drafting_objective:\s*.*$",
        "drafting_objective: Prepare O-1B petition memorandum and supporting employment documents",
        text,
        count=1,
    )
    o1b_roles = (
        "o1b_folder_roles:\n"
        '  identity_cv_education: "!CV_passport_linkedin_education"\n'
        '  us_work_documents: "!!offer_contracts_agent_itinerary_letter"\n'
        '  lead_starring_productions: "1.lead_starring_or_critical_role_for_organizations_and_establishments"\n'
        '  published_recognition: "2.critical_reviews_or_other_published_materials_by_or_about_the_beneficiary"\n'
        '  organization_role: "3.leading_critical_role_for_organization"\n'
        '  commercial_critical_success: "4.commercial_or_critically_acclaimed_successes"\n'
        '  significant_recognition: "5.significant_recognition_for_achievements"\n'
        '  high_salary: "6.high_salary_or_remuneration"\n'
        '  comparable_evidence: "7. Comparable_evidence"\n'
        '  advisory_opinion: "advisory_opinion"\n'
        '  recommendation_letters: "recommendation_letters"\n\n'
    )
    text = re.sub(
        r"(?ms)^eb1a_folder_roles:\n.*?(?=^approvals:)",
        o1b_roles,
        text,
        count=1,
    )
    marker = "drafting_objective: Prepare O-1B petition memorandum and supporting employment documents\n"
    if marker in text and "o1b_track:" not in text:
        text = text.replace(
            marker,
            marker
            + "o1b_track: arts\n"
            + "petitioner:\n"
            + "  company_name: __REQUIRED__\n"
            + "  company_address: __REQUIRED__\n"
            + "  petitioner_type: us_employer\n"
            + "  authorized_signatory: __REQUIRED__\n"
            + "filing:\n"
            + "  processing: Regular Processing\n"
            + "  validity_start: __REQUIRED__\n"
            + "  validity_end: __REQUIRED__\n"
            + "  uscis_address: __REQUIRED__\n"
            + "us_work:\n"
            + "  position_or_role: __REQUIRED__\n"
            + "  compensation: __REQUIRED__\n"
            + "  work_location: __REQUIRED__\n"
            + "  duties_summary: __REQUIRED__\n\n",
            1,
        )
    return text


def _rfe_case_config_text(text: str) -> str:
    text = text.replace(
        "source_folder_template: templates/EB1A/case_folders_template",
        "source_folder_template: templates/RFE/EB1",
    )
    text = re.sub(
        r"(?m)^procedural_context:\s*.*$",
        "procedural_context: RFE response",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^drafting_objective:\s*.*$",
        "drafting_objective: Prepare EB-1A RFE response",
        text,
        count=1,
    )
    marker = "  source_other: source_documents/other\n"
    if marker in text and "source_rfe_notice:" not in text:
        text = text.replace(
            marker,
            marker
            + "  source_rfe_notice: source_documents/rfe/notice\n"
            + "  source_rfe_strategy: source_documents/rfe/strategy\n"
            + "  source_initial_filing_memo: source_documents/initial_filing/memorandum\n"
            + "  source_rfe_new_originals: source_documents/rfe_response/new_documents/originals\n"
            + "  source_rfe_new_translations: source_documents/rfe_response/new_documents/translations\n"
            + "  rfe_strategy_root: case_strategy\n",
        )
    if "rfe_metadata:" not in text:
        text += (
            "\n"
            "rfe_metadata:\n"
            "  case_number: __REQUIRED__\n"
            "  receipt_date: __REQUIRED__\n"
            "  rfe_date: __REQUIRED__\n"
            "  response_deadline: __REQUIRED__\n"
            "  uscis_address: __REQUIRED__\n"
            "  petition_type: EB-1A Form I-140\n"
            "\n"
            "rfe_response:\n"
            "  plan_file: rfe_response_plan.md\n"
            "  template_file: templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.yaml\n"
            "  human_template_file: templates/RFE/EB1/rfe draft template.docx\n"
            "  strategy_manifest: case_strategy/strategy_manifest.json\n"
            "  attachment_label: Attachment\n"
            "  initial_filing_label: Initial Filing Exhibit\n"
            "  default_issue_step: rfe_dynamic_section\n"
            "\n"
            "rfe_folder_roles:\n"
            "  rfe_notice: .\n"
            "  rfe_issue_text: .\n"
            "  initial_filing_memo: .\n"
            "  initial_filing_issue_text: .\n"
            "  new_issue_documents: .\n"
            "  strategy: .\n"
            "\n"
            "rfe_enabled_issues: []\n"
        )
    return text


def _document_layout_case_config_text(text: str) -> str:
    text = re.sub(
        r"(?m)^procedural_context:\s*.*$",
        "procedural_context: Standalone document layout assembly",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^drafting_objective:\s*.*$",
        "drafting_objective: Parse an exhibit list, map files manually, and assemble a PDF bundle",
        text,
        count=1,
    )
    marker = "working_document_template: templates/EB1A/EB1A_working_document_structure.yaml\n"
    if marker in text and "document_layout:" not in text:
        text = text.replace(
            marker,
            marker
            + "\n"
            + "document_layout:\n"
            + "  mode: standalone\n"
            + "  originals_dir: \"\"\n"
            + "  translations_dir: \"\"\n"
            + "  list_document_path: \"\"\n",
            1,
        )
    return text


def _create_eb1a_rfe_structure(target: Path) -> None:
    rfe_directories = [
        "source_documents/rfe/notice",
        "source_documents/rfe/strategy",
        "source_documents/initial_filing/memorandum",
        "source_documents/rfe_response/new_documents/originals",
        "source_documents/rfe_response/new_documents/translations",
        "case_strategy/raw",
        "case_strategy/units",
        "case_strategy/initial_filing_sections",
        "draft_sections/rfe/sections",
    ]
    for relative in rfe_directories:
        folder = target / relative
        folder.mkdir(parents=True, exist_ok=True)
        keep = folder / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")

    source = PROJECT_ROOT / "templates" / "RFE" / "EB1" / "case_folders_template" / "new_docs"
    if not source.exists():
        source = PROJECT_ROOT / "templates" / "EB1A" / "case_folders_template"
    if source.exists():
        for destination in [
            target / "source_documents" / "rfe_response" / "new_documents" / "originals",
            target / "source_documents" / "rfe_response" / "new_documents" / "translations",
        ]:
            _copy_children_if_missing(source, destination)

    _write_if_missing(
        target / "rfe_response_plan.md",
        "# RFE response plan\n\n"
        "Use this file to define the order of sections and issue-level strategy.\n\n"
        "## Suggested structure\n\n"
        "1. Cover letter / procedural introduction\n"
        "2. Continued work / U.S. plans, if challenged\n"
        "3. Prospective substantial benefit, if challenged\n"
        "4. Criteria challenged in the RFE, in strategic order\n"
        "5. Final merits determination, if challenged\n"
        "6. Conclusion\n\n"
        "## Issue list\n\n"
        "- issue_id: continued_work\n"
        "  folder: continued_work\n"
        "  strategy: [write instructions]\n\n"
        "- issue_id: awards_1\n"
        "  folder: 1. Награды/1 episode\n"
        "  strategy: [write instructions]\n",
    )
    _write_if_missing(
        target / "source_documents" / "rfe" / "strategy" / "README.md",
        "# RFE strategy notes\n\n"
        "Put additional strategy notes here if they should be included in RFE prompts.\n"
        "Highest-priority custom instructions should also go into `user_case_instructions.md`.\n",
    )


def _copy_children_if_missing(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        child_destination = destination / child.name
        if child_destination.exists():
            continue
        if child.is_dir():
            shutil.copytree(child, child_destination)
        else:
            shutil.copy2(child, child_destination)


def _write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def scaffold_only(command: str, case_id: str, **details: str) -> int:
    rendered = ", ".join(f"{key}={value}" for key, value in details.items() if value)
    suffix = f" ({rendered})" if rendered else ""
    print(f"Stage 1 scaffold only: {command} for {case_id}{suffix}")
    print("No case files were changed.")
    return 0
