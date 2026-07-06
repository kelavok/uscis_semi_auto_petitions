from __future__ import annotations

import csv
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .cli_support import CASE_ROOT, PROJECT_ROOT, case_path
from .simple_yaml import load_yaml_subset
from .json_input import parse_llm_json_object
from .file_rules import is_office_temporary_file, prompt_sidecar_kind


TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
DOCX_EXTENSIONS = {".docx"}
PROMPT_TEXT_LIMIT = 18_000
EVIDENCE_TEXT_LIMIT = 12_000


@dataclass(frozen=True)
class LoadedCase:
    case_id: str
    case_dir: Path
    config: dict[str, Any]
    workflow: dict[str, Any]


@dataclass(frozen=True)
class PromptOptions:
    episode_id: str = ""
    episode_folder: str = ""


@dataclass(frozen=True)
class NextAction:
    action_type: str
    step_id: str = ""
    episode_id: str = ""
    episode_folder: str = ""
    command: str = ""
    reason: str = ""
    prompt_path: Path | None = None


def load_case(case_id: str) -> LoadedCase:
    case_dir = case_path(case_id)
    config_path = case_dir / "case_config.yaml"
    if not config_path.exists():
        raise SystemExit(f"Missing case_config.yaml: {config_path}")
    config = load_yaml_file(config_path)
    workflow_value = str(config.get("workflow", "workflows/eb1a_petition.yaml"))
    workflow_path = PROJECT_ROOT / workflow_value
    if not workflow_path.exists():
        raise SystemExit(f"Missing workflow file: {workflow_path}")
    workflow = load_yaml_file(workflow_path)
    return LoadedCase(case_id=case_id, case_dir=case_dir, config=config, workflow=workflow)


def load_yaml_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
    except ModuleNotFoundError:
        loaded = load_yaml_subset(text)
    except Exception:
        # User-maintained config/template files can contain YAML features or
        # plain-text values (for example a leading `!`) that PyYAML interprets
        # as tags and rejects. Fall back to the project subset parser so the UI
        # stays resilient to these drafting-side files instead of crashing.
        loaded = load_yaml_subset(text)
    if not isinstance(loaded, dict):
        raise SystemExit(f"YAML file did not load as a mapping: {path}")
    return loaded


def find_step(workflow: dict[str, Any], step_id: str) -> dict[str, Any]:
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        raise SystemExit("Workflow field 'steps' must be a list.")
    for step in steps:
        if isinstance(step, dict) and step.get("step_id") == step_id:
            return step
    raise SystemExit(f"Step not found in workflow: {step_id}")


def build_prompt(
    case_id: str,
    step_id: str,
    runtime_instruction_files: list[str],
    *,
    episode_id: str | None = None,
    episode_folder: str | None = None,
    custom_instructions: str | None = None,
) -> Path:
    loaded = load_case(case_id)
    step = find_step(loaded.workflow, step_id)
    options = PromptOptions(episode_id=episode_id or "", episode_folder=episode_folder or "")
    validate_repeatable_options(step, options)
    prompt_dir = loaded.case_dir / _case_path_value(loaded.config, "generated_prompts")
    prompt_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = output_stem(step_id, options.episode_id)
    if custom_instructions is not None:
        save_custom_prompt_instructions(loaded, step_id, options.episode_id, custom_instructions)
    prompt_path = prompt_dir / f"{stem}.{timestamp}.prompt.md"
    latest_path = prompt_dir / f"{stem}.latest.prompt.md"
    prompt_text = render_prompt(loaded, step, runtime_instruction_files, options)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    latest_path.write_text(prompt_text, encoding="utf-8")
    return prompt_path


def render_prompt(
    loaded: LoadedCase,
    step: dict[str, Any],
    runtime_instruction_files: list[str],
    options: PromptOptions | None = None,
) -> str:
    options = options or PromptOptions()
    case = loaded.config
    workflow = loaded.workflow
    step_id = str(step["step_id"])
    parts: list[str] = []
    parts.append("# Manual LLM prompt")
    parts.append("")
    parts.append("Copy this entire prompt into the LLM chat. Return only valid JSON.")
    parts.append("")
    parts.append("## Runtime metadata")
    parts.append("")
    parts.append(f"- case_id: `{loaded.case_id}`")
    parts.append(f"- task_type: `{case.get('task_type', workflow.get('task_type', ''))}`")
    parts.append(f"- step_id: `{step_id}`")
    parts.append(f"- step_title: `{step.get('title', '')}`")
    if options.episode_id:
        parts.append(f"- episode_id: `{options.episode_id}`")
    if options.episode_folder:
        parts.append(f"- episode_folder: `{options.episode_folder}`")
    parts.append("")
    parts.append("## Required output JSON schema")
    parts.append("")
    schema_path = PROJECT_ROOT / "schemas" / "llm_section_output.schema.json"
    parts.append(_fenced(read_textual_file(schema_path, PROMPT_TEXT_LIMIT), "json"))
    parts.append("")
    parts.append("## Case context")
    parts.append("")
    parts.append(render_case_context(case))
    parts.append("")
    parts.append("## Step objective")
    parts.append("")
    parts.append(str(step.get("objective", "")).strip())
    parts.append("")
    parts.append("## Custom instructions for this drafting unit (highest priority)")
    parts.append("")
    custom_instructions = read_custom_prompt_instructions(loaded, step_id, options.episode_id)
    if custom_instructions:
        parts.append(
            "Apply the following unit-specific instructions ahead of conflicting template, section, and "
            "general style instructions. They may not override factual accuracy, the required JSON schema, "
            "or the final-output validation guardrails."
        )
        parts.append("")
        parts.append(_fenced(custom_instructions, "text"))
    else:
        parts.append("[No custom instructions supplied for this unit.]")
    parts.append("")
    parts.append("## Instruction hierarchy")
    parts.append("")
    parts.extend(render_instruction_hierarchy(loaded, step, runtime_instruction_files))
    parts.append("")
    parts.append("## Evidence and controlling strategy available for this step")
    parts.append("")
    if _truthy_config(step.get("rfe_strategy_units", False)):
        from .rfe_strategy import render_strategy_unit_context

        parts.append(render_strategy_unit_context(loaded, options.episode_id))
    else:
        parts.append(render_evidence_context(loaded, step, options))
    parts.append("")
    included_drafts = _normalize_path_list(step.get("include_draft_steps", []))
    if included_drafts:
        parts.append("## Previously drafted supporting documents")
        parts.append("")
        parts.append(render_prior_draft_context(loaded, included_drafts))
        parts.append("")
    if _truthy_config(step.get("include_working_memo", False)):
        parts.append("## Current working memorandum context")
        parts.append("")
        parts.append(render_working_memo_context(loaded))
        parts.append("")
    parts.append("## Non-negotiable final-output guardrails")
    parts.append("")
    parts.append(render_final_output_guardrails(loaded, step, options))
    parts.append("")
    parts.append("## Required response")
    parts.append("")
    parts.append(
        "Return only one JSON object matching the schema. "
        "Set `case_id`, `task_type`, and `step_id` exactly as shown above. "
        + (f"Set `episode_id` exactly to `{options.episode_id}`. " if options.episode_id else "")
        + "If this step is only an intake/template-review step, put concise notes "
        "or acknowledgement into `draft_text` and use the structured arrays for "
        "questions, unsupported claims, and quality flags."
    )
    parts.append(
        "Before responding, verify that the object parses as strict JSON. Escape every double quote "
        "inside a string as `\\\"`, encode line breaks inside strings as `\\n`, do not use Markdown "
        "code fences, and do not leave trailing commas."
    )
    parts.append("")
    return "\n".join(parts)


def custom_prompt_instructions_path(loaded: LoadedCase, step_id: str, episode_id: str = "") -> Path:
    stem = output_stem(step_id, episode_id)
    return loaded.case_dir / "prompt_instructions" / f"{stem}.md"


def read_custom_prompt_instructions(loaded: LoadedCase, step_id: str, episode_id: str = "") -> str:
    path = custom_prompt_instructions_path(loaded, step_id, episode_id)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace").strip()


def save_custom_prompt_instructions(
    loaded: LoadedCase, step_id: str, episode_id: str, instructions: str
) -> Path:
    path = custom_prompt_instructions_path(loaded, step_id, episode_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(instructions.strip() + ("\n" if instructions.strip() else ""), encoding="utf-8")
    return path


def render_working_memo_context(loaded: LoadedCase) -> str:
    """Return the assembled memorandum as context for synthesis steps such as overview."""
    final_root = loaded.case_dir / _case_path_value(loaded.config, "final_memo")
    candidates = [final_root / "working_memo.md", final_root / "working_memo.docx"]
    for path in candidates:
        if path.exists():
            return (
                f"Source: `{path.relative_to(loaded.case_dir).as_posix()}`\n\n"
                + _fenced(read_textual_file(path, PROMPT_TEXT_LIMIT), "text")
            )
    return "[The working memorandum has not been built yet.]"


def render_prior_draft_context(loaded: LoadedCase, step_ids: list[str]) -> str:
    parts: list[str] = []
    for step_id in step_ids:
        try:
            prior_step = find_step(loaded.workflow, step_id)
        except SystemExit:
            parts.append(f"### {step_id}\n\n[Workflow step not found.]\n")
            continue
        destination = destination_for_step(prior_step, PromptOptions())
        if not destination:
            parts.append(f"### {step_id}\n\n[No fixed draft destination is configured.]\n")
            continue
        path = loaded.case_dir / destination
        if not path.exists():
            parts.append(f"### {step_id}\n\n[Draft has not been completed yet.]\n")
            continue
        parts.append(
            f"### {step_id}\n\nSource: `{path.relative_to(loaded.case_dir).as_posix()}`\n\n"
            + _fenced(read_textual_file(path, PROMPT_TEXT_LIMIT), "text")
            + "\n"
        )
    return "\n".join(parts).strip()


def render_final_output_guardrails(
    loaded: LoadedCase, step: dict[str, Any], options: PromptOptions
) -> str:
    step_id = str(step.get("step_id", ""))
    technical_step = step_id in {"opening_context_intake", "template_review"}
    standalone_document = str(step.get("output_kind", "")) == "standalone_support_document"
    citation = _citation_plan_for_step(loaded, step, options)
    lines = [
        (
            "The JSON `draft_text` field is the final, human-facing standalone supporting document only."
            if standalone_document
            else "The JSON `draft_text` field is final, human-facing petition text only. It will be inserted into Word verbatim."
        ),
        "Never put prompt analysis, evidence-processing commentary, OCR/parsing limitations, drafting advice, jokes, sarcasm, or notes to the legal team in `draft_text`.",
        "Put evidence gaps and internal cautions only in `unsupported_claims`, `questions_for_user`, `quality_flags`, or `revision_notes`.",
        "Draft the strongest accurate affirmative argument supported by the record. Do not write a negative sufficiency assessment in the petition body.",
        "Use concrete names, dates, figures, dimensions, transaction values, portfolio sizes, percentages, counts, organizations, media outlets, article titles, and URLs whenever the supplied evidence contains them.",
        "Use one consistent English name and abbreviation for every organization; define an alternate/source-language acronym once only if needed.",
        "Do not use the word `episode` in petition text. Use `criterion`, `section`, `submitted evidence`, or `record` as appropriate.",
        "In `used_documents`, provide a concise, descriptive English `document_title` for every cited document. Do not copy a raw filename or leave a Russian-only title.",
        "Every `used_documents[].document_id` must be copied exactly from the Technical document selection in this prompt (format `DOC####`). Never invent semantic IDs for an RFE quote, strategy, exhibit group, or explanatory material. If no indexed documents are listed, return `used_documents: []`.",
    ]
    if technical_step:
        lines.append("This is a technical intake/review step, so concise internal notes are allowed in `draft_text`.")
        return "\n".join(f"- {line}" for line in lines)
    exhibit_number = citation.get("exhibit_number", "")
    item_prefix = citation.get("item_prefix", "")
    if exhibit_number:
        lines.extend(
            [
                f"The primary exhibit for this section is Exhibit {exhibit_number}.",
                f"Number this unit's exhibit-list items with the prefix `{item_prefix}` (for example `{item_prefix}1.`), never with another criterion's prefix.",
                "Include the exhibit-list introduction and `Within the Exhibit, the following documents are attached:` followed by a complete numbered document list. If later units add documents to the same Exhibit, return the complete updated list for the material covered so far.",
                f"Use citations in this form: `(Please refer to Exhibit {exhibit_number}, page PAGE: {item_prefix}1 - Concise English document title, original and English translation.)` Adapt singular/plural and omit the translation phrase when no translation exists.",
                "Keep `PAGE` as the pagination placeholder until final PDF assembly. Do not use `XX`, raw filenames, document IDs, or technical paths in the petition body.",
            ]
        )
    return "\n".join(f"- {line}" for line in lines)


def render_case_context(case: dict[str, Any]) -> str:
    beneficiary = case.get("beneficiary", {})
    if not isinstance(beneficiary, dict):
        beneficiary = {}
    lines = [
        f"- beneficiary.full_name: {beneficiary.get('full_name', '')}",
        f"- beneficiary.preferred_reference: {beneficiary.get('preferred_reference', '')}",
        f"- field: {case.get('field', '')}",
        f"- specialization: {case.get('specialization', '')}",
        f"- procedural_context: {case.get('procedural_context', '')}",
        f"- drafting_objective: {case.get('drafting_objective', '')}",
        f"- claimed_criteria: {case.get('claimed_criteria', [])}",
        f"- enabled_steps: {case.get('enabled_steps', [])}",
        f"- disabled_steps: {case.get('disabled_steps', [])}",
    ]
    if str(case.get("task_type", "")) == "o1b_petition":
        petitioner = case.get("petitioner", {}) if isinstance(case.get("petitioner"), dict) else {}
        filing = case.get("filing", {}) if isinstance(case.get("filing"), dict) else {}
        us_work = case.get("us_work", {}) if isinstance(case.get("us_work"), dict) else {}
        lines.extend(
            [
                f"- o1b_track: {case.get('o1b_track', '')}",
                f"- petitioner.company_name: {petitioner.get('company_name', '')}",
                f"- petitioner.company_address: {petitioner.get('company_address', '')}",
                f"- petitioner.petitioner_type: {petitioner.get('petitioner_type', '')}",
                f"- petitioner.authorized_signatory: {petitioner.get('authorized_signatory', '')}",
                f"- filing.processing: {filing.get('processing', '')}",
                f"- filing.validity_start: {filing.get('validity_start', '')}",
                f"- filing.validity_end: {filing.get('validity_end', '')}",
                f"- us_work.position_or_role: {us_work.get('position_or_role', '')}",
                f"- us_work.compensation: {us_work.get('compensation', '')}",
                f"- us_work.work_location: {us_work.get('work_location', '')}",
                f"- us_work.duties_summary: {us_work.get('duties_summary', '')}",
            ]
        )
    rfe_metadata = case.get("rfe_metadata", {})
    if isinstance(rfe_metadata, dict):
        lines.extend(
            [
                f"- rfe.case_number: {rfe_metadata.get('case_number', '')}",
                f"- rfe.receipt_date: {rfe_metadata.get('receipt_date', '')}",
                f"- rfe.rfe_date: {rfe_metadata.get('rfe_date', '')}",
                f"- rfe.response_deadline: {rfe_metadata.get('response_deadline', '')}",
                f"- rfe.uscis_address: {rfe_metadata.get('uscis_address', '')}",
                f"- rfe.petition_type: {rfe_metadata.get('petition_type', '')}",
                f"- rfe.response_date: {rfe_metadata.get('rfe_response_date', '')}",
                f"- rfe.uscis_office_or_service_center: {rfe_metadata.get('uscis_office_or_service_center', '')}",
                f"- rfe.officer_name: {rfe_metadata.get('officer_name', '')}",
                f"- rfe.office_chief_name: {rfe_metadata.get('office_chief_name', '')}",
                f"- rfe.salutation: {rfe_metadata.get('salutation', '')}",
            ]
        )
    rfe_response = case.get("rfe_response", {})
    if isinstance(rfe_response, dict):
        lines.extend(
            [
                f"- rfe.plan_file: {rfe_response.get('plan_file', '')}",
                f"- rfe.attachment_label: {rfe_response.get('attachment_label', '')}",
                f"- rfe.initial_filing_label: {rfe_response.get('initial_filing_label', '')}",
            ]
        )
    return "\n".join(lines)


def render_instruction_hierarchy(
    loaded: LoadedCase, step: dict[str, Any], runtime_instruction_files: list[str]
) -> list[str]:
    sources = loaded.workflow.get("instruction_sources", {})
    if not isinstance(sources, dict):
        sources = {}
    sections: list[str] = []
    ordered_groups = [
        ("runtime", runtime_instruction_files),
        ("case_specific", [sources.get("case_specific", "")]),
        ("task_type", sources.get("task_type", [])),
        ("section_specific", [step.get("section_instructions", "")]),
        ("visa_or_rfe_specific", sources.get("visa_or_rfe_specific", [])),
        ("universal", sources.get("universal", [])),
    ]
    for label, paths in ordered_groups:
        normalized = _normalize_path_list(paths)
        if not normalized:
            continue
        sections.append(f"### {label}")
        sections.append("")
        for path_value in normalized:
            sections.append(render_source_file(loaded, path_value))
            sections.append("")
    return sections


def render_source_file(loaded: LoadedCase, path_value: str) -> str:
    path = _resolve_project_or_case_path(loaded.case_dir, path_value)
    if not path.exists():
        return f"#### {path_value}\n\n[Missing file: {path}]"
    text = read_textual_file(path, PROMPT_TEXT_LIMIT)
    return f"#### {path_value}\n\n{_fenced(text, _fence_language(path))}"


def render_evidence_context(
    loaded: LoadedCase, step: dict[str, Any], options: PromptOptions | None = None
) -> str:
    options = options or PromptOptions()
    if step.get("evidence_sources"):
        return render_configured_evidence_sources(loaded, step, options)
    roles = _normalize_path_list(step.get("evidence_folder_roles", []))
    if not roles:
        return "No evidence folder roles are configured for this step."
    role_map = folder_role_map(loaded.config)
    document_index = read_document_index(loaded)
    parts: list[str] = []
    for role in roles:
        folder_name = str(role_map.get(role, role))
        parts.append(f"### Evidence role: {role}")
        parts.append("")
        parts.append(f"Folder role: `{folder_name}`")
        parts.append("")
        files: list[Path] = []
        missing_folders: list[Path] = []
        for source_key in ["source_originals", "source_translations", "source_other"]:
            source_root = loaded.case_dir / _case_path_value(loaded.config, source_key)
            folder = source_root / folder_name
            evidence_folders = _episode_folders_for(folder, options, step)
            if evidence_folders:
                for evidence_folder in evidence_folders:
                    files.extend(
                        p
                        for p in sorted(evidence_folder.rglob("*"))
                        if p.is_file() and p.name != ".gitkeep"
                    )
            else:
                missing_folders.append(_episode_folder_for(folder, options))
        if not files:
            parts.append("[No files placed in originals/translations/other folders for this role yet.]")
            parts.append("")
            for folder in missing_folders:
                parts.append(f"- missing: `{folder}`")
            parts.append("")
            continue
        parts.append(render_evidence_files(loaded, files, document_index))
        parts.append("")
    return "\n".join(parts).strip()


def render_configured_evidence_sources(
    loaded: LoadedCase, step: dict[str, Any], options: PromptOptions
) -> str:
    sources = step.get("evidence_sources", [])
    if not isinstance(sources, list) or not sources:
        return "No configured evidence sources for this step."
    document_index = read_document_index(loaded)
    parts: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        label = str(source.get("label") or source.get("path_key") or "Evidence source")
        path_key = str(source.get("path_key", ""))
        folder_value = str(source.get("folder", "."))
        use_episode = _truthy_config(source.get("use_episode_folder", False))
        if not path_key:
            parts.append(f"### {label}")
            parts.append("")
            parts.append("[Missing path_key in workflow evidence_sources entry.]")
            parts.append("")
            continue
        try:
            source_root = loaded.case_dir / _case_path_value(loaded.config, path_key)
        except SystemExit as exc:
            parts.append(f"### {label}")
            parts.append("")
            parts.append(f"[Missing source path `{path_key}`: {exc}]")
            parts.append("")
            continue
        folder = source_root if folder_value in {"", "."} else source_root / folder_value
        evidence_folder = _episode_folder_for(folder, options) if use_episode else folder
        parts.append(f"### {label}")
        parts.append("")
        parts.append(f"- path_key: `{path_key}`")
        parts.append(f"- folder: `{_normalize_slashes(evidence_folder.relative_to(loaded.case_dir).as_posix()) if evidence_folder.exists() else evidence_folder}`")
        if use_episode and options.episode_id:
            parts.append(f"- episode_id: `{options.episode_id}`")
            if options.episode_folder:
                parts.append(f"- episode_folder: `{options.episode_folder}`")
        parts.append("")
        if not evidence_folder.exists():
            parts.append("[Folder does not exist yet.]")
            parts.append("")
            continue
        files = [p for p in sorted(evidence_folder.rglob("*")) if p.is_file() and p.name != ".gitkeep"]
        if not files:
            parts.append("[No files in this folder yet.]")
            parts.append("")
            continue
        parts.append(render_evidence_files(loaded, files, document_index))
        parts.append("")
    return "\n".join(parts).strip()


def render_evidence_files(
    loaded: LoadedCase, files: list[Path], document_index: dict[str, list[dict[str, str]]]
) -> str:
    parts: list[str] = []
    for file_path in files:
        if is_office_temporary_file(file_path):
            continue
        rel = file_path.relative_to(loaded.case_dir)
        sidecar_kind = prompt_sidecar_kind(file_path)
        if sidecar_kind:
            if sidecar_kind in {"info", "readme"}:
                label = "Folder-local instructions and explanatory notes"
                purpose = (
                    "apply these additional instructions and explanations only while analyzing "
                    "and drafting from documents in this exact folder"
                )
            else:
                label = "Auxiliary extract for non-machine-readable documents"
                purpose = (
                    "use only to understand partially or wholly non-machine-readable documents "
                    "located in this exact folder"
                )
            parts.extend(
                [
                    f"#### {label} for folder `{rel.parent.as_posix()}`",
                    f"- source_type: prompt-only folder sidecar ({file_path.name})",
                    "- indexing_policy: do not add to document/exhibit indexes, used_documents, citations, or final bundle",
                    f"- scope: {purpose}",
                    "- evidence_policy: this sidecar is not independent evidence; rely on and cite the underlying documents",
                    "",
                    _fenced(read_textual_file(file_path, EVIDENCE_TEXT_LIMIT), "text"),
                    "",
                ]
            )
            continue
        doc_rows = document_index.get(_normalize_slashes(rel.as_posix()), [])
        doc_row = doc_rows[0] if doc_rows else {}
        doc_id = doc_row.get("document_id", "")
        display_title = doc_row.get("display_title", "")
        extraction_status = doc_row.get("extraction_status", "")
        text_extraction_path = doc_row.get("text_extraction_path", "")
        translation_status = doc_row.get("translation_status", "")
        relationship_type = doc_row.get("relationship_type", "")
        parent_document_id = doc_row.get("parent_document_id", "")
        parts.append(f"#### {rel}")
        if doc_id or display_title:
            parts.append(f"- document_id: {doc_id}")
            parts.append(f"- display_title: {display_title}")
            parts.append(f"- translation_status: {translation_status or '[not set]'}")
            parts.append(f"- relationship_type: {relationship_type or '[not set]'}")
            if parent_document_id:
                parts.append(f"- parent_document_id: {parent_document_id}")
                parts.append("- bundle_order_hint: original first, then this translation")
            parts.append(f"- extraction_status: {extraction_status or '[not scanned]'}")
        else:
            parts.append("- document_id: [not indexed yet]")
        parts.append("")
        if text_extraction_path:
            extracted = loaded.case_dir / text_extraction_path
            parts.append(_fenced(read_textual_file(extracted, EVIDENCE_TEXT_LIMIT), "text"))
        elif file_path.suffix.lower() in TEXT_EXTENSIONS | DOCX_EXTENSIONS:
            parts.append(
                _fenced(read_textual_file(file_path, EVIDENCE_TEXT_LIMIT), _fence_language(file_path))
            )
        else:
            parts.append("[Binary or unsupported file type: listed for reference only.]")
        parts.append("")
    return "\n".join(parts).strip()


def read_document_index(loaded: LoadedCase) -> dict[str, list[dict[str, str]]]:
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    if not index_path.exists():
        return {}
    result: dict[str, list[dict[str, str]]] = {}
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = _normalize_slashes(row.get("file_path", ""))
            if key:
                result.setdefault(key, []).append(row)
    return result


def selected_documents_for_step(
    loaded: LoadedCase, step: dict[str, Any], options: PromptOptions | None = None
) -> list[dict[str, str]]:
    """Return the indexed documents that the matching prompt will actually receive."""
    options = options or PromptOptions()
    if _truthy_config(step.get("rfe_strategy_units", False)) and options.episode_id:
        from .rfe_strategy import selected_documents_for_unit

        return selected_documents_for_unit(loaded, options.episode_id)

    files: list[Path] = []
    sources = step.get("evidence_sources", [])
    if isinstance(sources, list) and sources:
        for source in sources:
            if not isinstance(source, dict):
                continue
            path_key = str(source.get("path_key", ""))
            if not path_key:
                continue
            try:
                source_root = loaded.case_dir / _case_path_value(loaded.config, path_key)
            except SystemExit:
                continue
            folder_value = str(source.get("folder", "."))
            folder = source_root if folder_value in {"", "."} else source_root / folder_value
            evidence_folder = (
                _episode_folder_for(folder, options)
                if _truthy_config(source.get("use_episode_folder", False))
                else folder
            )
            if evidence_folder.exists():
                files.extend(path for path in evidence_folder.rglob("*") if path.is_file())
    else:
        role_map = folder_role_map(loaded.config)
        for role in _normalize_path_list(step.get("evidence_folder_roles", [])):
            folder_name = str(role_map.get(role, role))
            for source_key in ("source_originals", "source_translations", "source_other"):
                try:
                    source_root = loaded.case_dir / _case_path_value(loaded.config, source_key)
                except SystemExit:
                    continue
                for evidence_folder in _episode_folders_for(source_root / folder_name, options, step):
                    files.extend(path for path in evidence_folder.rglob("*") if path.is_file())

    document_index = read_document_index(loaded)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in sorted(set(files)):
        if path.name == ".gitkeep" or is_office_temporary_file(path) or prompt_sidecar_kind(path):
            continue
        try:
            relative_path = path.relative_to(loaded.case_dir).as_posix()
        except ValueError:
            continue
        rows = document_index.get(_normalize_slashes(relative_path), [])
        row = rows[0] if rows else {}
        document_id = str(row.get("document_id", "")).strip()
        if not document_id or document_id in seen:
            continue
        selected.append(
            {
                "document_id": document_id,
                "title": str(row.get("display_title") or row.get("original_file_name") or path.stem),
                "file_path": relative_path,
            }
        )
        seen.add(document_id)
    return selected


def import_llm_output(
    case_id: str,
    step_id: str,
    output_file: str,
    *,
    episode_id: str | None = None,
    force: bool = False,
) -> Path:
    loaded = load_case(case_id)
    step = find_step(loaded.workflow, step_id)
    options = PromptOptions(episode_id=episode_id or "")
    validate_repeatable_options(step, options)
    source = Path(output_file)
    if not source.is_absolute():
        source = loaded.case_dir / output_file
    if not source.exists():
        raise SystemExit(f"LLM output file not found: {source}")
    try:
        parsed = parse_llm_json_object(source.read_text(encoding="utf-8-sig"))
        data = parsed.data
    except ValueError as exc:
        raise SystemExit(f"Invalid JSON output file: {source} ({exc})") from exc
    validate_llm_output(data, loaded, step_id, options)
    if step_id not in {"opening_context_intake", "template_review"}:
        _update_document_titles_from_llm(loaded, data)
    output_dir = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{output_stem(step_id, options.episode_id)}.json"
    if target.exists() and not force:
        raise SystemExit(f"Validated output already exists; use --force to replace: {target}")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def insert_section(
    case_id: str,
    step_id: str,
    *,
    episode_id: str | None = None,
    force: bool = False,
) -> Path:
    loaded = load_case(case_id)
    step = find_step(loaded.workflow, step_id)
    options = PromptOptions(episode_id=episode_id or "")
    validate_repeatable_options(step, options)
    destination = destination_for_step(step, options)
    if not destination:
        raise SystemExit(
            f"Step '{step_id}' has no fixed destination yet. Repeatable episode steps will be added next."
        )
    source = (
        loaded.case_dir
        / _case_path_value(loaded.config, "validated_outputs")
        / f"{output_stem(step_id, options.episode_id)}.json"
    )
    if not source.exists():
        raise SystemExit(f"Validated output not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid validated JSON file: {source} ({exc})") from exc
    validate_llm_output(data, loaded, step_id, options)
    target = loaded.case_dir / str(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        raise SystemExit(f"Draft section already exists; use --force to replace: {target}")
    target.write_text(str(data["draft_text"]).strip() + "\n", encoding="utf-8")
    # Keep the human-facing Word memorandum synchronized with validated draft sections when
    # a working memo template is available for this case.
    try:
        from .memo_builder import build_working_memo

        build_working_memo(case_id)
    except SystemExit:
        pass
    return target


def build_status_report(case_id: str) -> str:
    loaded = load_case(case_id)
    lines: list[str] = []
    lines.append(f"Case: {loaded.case_id}")
    lines.append(f"Task type: {loaded.config.get('task_type', '')}")
    lines.append("")
    lines.append("Documents")
    lines.append("---------")
    rows = _read_document_index_rows(loaded)
    ready_statuses = {"text_extracted", "manual_description_available"}
    ready = [row for row in rows if row.get("extraction_status") in ready_statuses]
    pending_manual = [
        row
        for row in rows
        if "Manual description placeholder:" in row.get("notes", "")
        and row.get("extraction_status") != "manual_description_available"
    ]
    translations = [row for row in rows if row.get("translation_status") == "translation"]
    linked_translations = [row for row in translations if row.get("parent_document_id")]
    unlinked_translations = [row for row in translations if not row.get("parent_document_id")]
    lines.append(f"Total indexed documents: {len(rows)}")
    lines.append(f"LLM-readable documents: {len(ready)}")
    lines.append(f"Pending manual descriptions: {len(pending_manual)}")
    lines.append(f"Translations linked to originals: {len(linked_translations)}/{len(translations)}")
    for row in pending_manual[:20]:
        lines.append(
            f"- {row.get('document_id')}: {row.get('display_title') or row.get('original_file_name')} "
            f"({row.get('file_path')})"
        )
    if len(pending_manual) > 20:
        lines.append(f"- ... and {len(pending_manual) - 20} more")
    if unlinked_translations:
        lines.append("Unlinked translations:")
        for row in unlinked_translations[:20]:
            lines.append(
                f"- {row.get('document_id')}: {row.get('display_title') or row.get('original_file_name')} "
                f"({row.get('file_path')})"
            )
        if len(unlinked_translations) > 20:
            lines.append(f"- ... and {len(unlinked_translations) - 20} more")
    lines.append("")
    lines.append("Exhibits")
    lines.append("--------")
    exhibit_rows = _read_exhibit_index_rows(loaded)
    lines.append(f"Total exhibits: {len(exhibit_rows)}")
    exhibits_missing_docs = [row for row in exhibit_rows if not row.get("document_ids", "").strip()]
    lines.append(f"Exhibits missing document_ids: {len(exhibits_missing_docs)}")
    lines.append("")
    lines.append("Fixed draft sections")
    lines.append("--------------------")
    steps = loaded.workflow.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    any_fixed = False
    for step in steps:
        if not isinstance(step, dict) or not step.get("destination"):
            continue
        any_fixed = True
        step_id = str(step.get("step_id"))
        destination = loaded.case_dir / str(step.get("destination"))
        validated = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs") / f"{step_id}.json"
        prompt_latest = loaded.case_dir / _case_path_value(loaded.config, "generated_prompts") / f"{step_id}.latest.prompt.md"
        if destination.exists():
            state = "draft_inserted"
        elif validated.exists():
            state = "validated_not_inserted"
        elif prompt_latest.exists():
            state = "prompt_ready"
        else:
            state = "not_started"
        lines.append(f"- {step_id}: {state}")
    if not any_fixed:
        lines.append("[No fixed-destination draft sections in workflow.]")
    lines.append("")
    lines.append("Repeatable outputs")
    lines.append("------------------")
    validated_dir = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs")
    repeatable_json = sorted(validated_dir.glob("*.*.json")) if validated_dir.exists() else []
    if repeatable_json:
        for path in repeatable_json[:30]:
            lines.append(f"- validated: {path.name}")
        if len(repeatable_json) > 30:
            lines.append(f"- ... and {len(repeatable_json) - 30} more")
    else:
        lines.append("[No repeatable validated outputs yet.]")
    return "\n".join(lines)


def run_next_report(case_id: str, *, build_prompt_file: bool = False) -> str:
    loaded = load_case(case_id)
    action = determine_next_action(loaded)
    lines = [
        f"Case: {loaded.case_id}",
        f"Next action: {action.action_type}",
    ]
    if action.step_id:
        lines.append(f"Step: {action.step_id}")
    if action.episode_id:
        lines.append(f"Episode ID: {action.episode_id}")
    if action.episode_folder:
        lines.append(f"Episode folder: {action.episode_folder}")
    if action.reason:
        lines.extend(["", action.reason])

    prompt_path: Path | None = None
    if build_prompt_file and action.action_type == "build_prompt":
        prompt_path = build_prompt(
            loaded.case_id,
            action.step_id,
            [],
            episode_id=action.episode_id or None,
            episode_folder=action.episode_folder or None,
        )
        lines.extend(["", f"Created prompt: {prompt_path}"])
    elif build_prompt_file:
        lines.extend(["", "--build-prompt was ignored because the next action is not prompt creation."])

    if prompt_path is None and action.prompt_path:
        lines.extend(["", f"Existing prompt: {action.prompt_path}"])
    if action.command:
        lines.extend(["", "Suggested command:", "", action.command])

    lines.extend(["", "Helpful status snapshot:", ""])
    lines.append(_compact_next_status(loaded))
    return "\n".join(lines)


def determine_next_action(loaded: LoadedCase) -> NextAction:
    config_issue = _first_case_config_placeholder(loaded.config)
    if config_issue:
        return NextAction(
            action_type="edit_case_config",
            command=f"notepad {loaded.case_dir / 'case_config.yaml'}",
            reason=f"case_config.yaml still contains placeholder value: {config_issue}",
        )

    steps = loaded.workflow.get("steps", [])
    if not isinstance(steps, list):
        return NextAction(action_type="blocked", reason="Workflow has no valid steps list.")

    enabled_steps = _enabled_steps(loaded.config)
    disabled_steps = set(_normalize_path_list(loaded.config.get("disabled_steps", [])))

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("step_id", ""))
        execution = str(step.get("execution", ""))
        if not step_id or step_id in disabled_steps:
            continue
        if execution.startswith("deterministic"):
            continue
        if not _step_enabled_for_case(loaded.config, step):
            continue
        if "repeatable" in execution:
            if enabled_steps and step_id not in enabled_steps:
                continue
            suggestion = _first_repeatable_gap(loaded, step)
            if suggestion:
                return suggestion
            continue

        destination = step.get("destination")
        if destination and (loaded.case_dir / str(destination)).exists():
            continue
        validated = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs") / f"{step_id}.json"
        if validated.exists():
            return NextAction(
                action_type="insert_section",
                step_id=step_id,
                command=f"python -m app.draft insert-section --case {loaded.case_id} --step {step_id}",
                reason="Validated LLM output exists, but the draft section has not been inserted yet.",
            )
        latest_prompt = loaded.case_dir / _case_path_value(loaded.config, "generated_prompts") / f"{step_id}.latest.prompt.md"
        if latest_prompt.exists():
            return NextAction(
                action_type="await_llm_output",
                step_id=step_id,
                prompt_path=latest_prompt,
                command=(
                    f"python -m app.draft import-output --case {loaded.case_id} --step {step_id} "
                    f"--file llm_outputs/{step_id}.json"
                ),
                reason="Prompt already exists. Copy it into the LLM, save JSON output, then import it.",
            )
        return NextAction(
            action_type="build_prompt",
            step_id=step_id,
            command=f"python -m app.draft build-prompt --case {loaded.case_id} --step {step_id}",
            reason="This is the next fixed LLM step without prompt/output/draft.",
        )

    return NextAction(
        action_type="review_or_bundle",
        command=(
            f"python -m app.draft status --case {loaded.case_id}\n"
            f"python -m app.bundle build --case {loaded.case_id} --dry-run"
        ),
        reason="No pending fixed LLM steps or enabled repeatable gaps were found.",
    )


def _step_enabled_for_case(config: dict[str, Any], step: dict[str, Any]) -> bool:
    roles = _normalize_path_list(step.get("evidence_folder_roles", []))
    role = roles[0] if len(roles) == 1 else ""
    criterion_roles = {
        "awards", "memberships", "media", "judging", "original_contribution",
        "scholarly_articles", "exhibitions", "leading_critical_role", "high_salary",
        "commercial_success", "lead_starring_productions", "published_recognition",
        "organization_role", "commercial_critical_success", "significant_recognition",
        "comparable_evidence",
    }
    if role == "comparable_evidence" and str(config.get("o1b_track", "")) == "mptv":
        return False
    claimed = set(_normalize_path_list(config.get("claimed_criteria", [])))
    return not (role in criterion_roles and claimed and role not in claimed)


def _first_repeatable_gap(loaded: LoadedCase, step: dict[str, Any]) -> NextAction | None:
    step_id = str(step.get("step_id", ""))
    candidates = _repeatable_episode_candidates(loaded, step)
    for episode_id, episode_folder in candidates:
        destination = loaded.case_dir / destination_for_step(
            step, PromptOptions(episode_id=episode_id, episode_folder=episode_folder)
        )
        if destination.exists():
            continue
        stem = output_stem(step_id, episode_id)
        validated = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs") / f"{stem}.json"
        if validated.exists():
            return NextAction(
                action_type="insert_section",
                step_id=step_id,
                episode_id=episode_id,
                episode_folder=episode_folder,
                command=(
                    f"python -m app.draft insert-section --case {loaded.case_id} "
                    f"--step {step_id} --episode-id {episode_id}"
                ),
                reason="Validated repeatable output exists, but the episode draft has not been inserted yet.",
            )
        latest_prompt = loaded.case_dir / _case_path_value(loaded.config, "generated_prompts") / f"{stem}.latest.prompt.md"
        if latest_prompt.exists():
            return NextAction(
                action_type="await_llm_output",
                step_id=step_id,
                episode_id=episode_id,
                episode_folder=episode_folder,
                prompt_path=latest_prompt,
                command=(
                    f"python -m app.draft import-output --case {loaded.case_id} --step {step_id} "
                    f"--episode-id {episode_id} --file llm_outputs/{stem}.json"
                ),
                reason="Repeatable prompt already exists. Copy it into the LLM, save JSON output, then import it.",
            )
        return NextAction(
            action_type="build_prompt",
            step_id=step_id,
            episode_id=episode_id,
            episode_folder=episode_folder,
            command=(
                f"python -m app.draft build-prompt --case {loaded.case_id} --step {step_id} "
                f"--episode-id {episode_id} --episode-folder \"{episode_folder}\""
            ),
            reason="This is the next enabled repeatable episode without prompt/output/draft.",
        )
    return None


def _repeatable_episode_candidates(loaded: LoadedCase, step: dict[str, Any]) -> list[tuple[str, str]]:
    if _truthy_config(step.get("rfe_strategy_units", False)):
        from .rfe_strategy import list_strategy_units

        return list_strategy_units(loaded)
    if step.get("evidence_sources"):
        return _repeatable_candidates_from_evidence_sources(loaded, step)
    scoped_terms = _episode_folder_terms(step)
    if scoped_terms:
        return _scoped_repeatable_episode_candidate(loaded, step, scoped_terms)
    roles = _normalize_path_list(step.get("evidence_folder_roles", []))
    role_map = folder_role_map(loaded.config)
    grouped_candidates: dict[str, tuple[str, str, int]] = {}
    for role in roles:
        folder_name = str(role_map.get(role, role))
        for priority, source_key in enumerate(["source_originals", "source_translations", "source_other"]):
            source_root = loaded.case_dir / _case_path_value(loaded.config, source_key)
            role_folder = source_root / folder_name
            if not role_folder.exists():
                continue
            subfolders = [
                path for path in sorted(role_folder.iterdir()) if path.is_dir() and _folder_has_files(path)
            ]
            if subfolders:
                for folder in subfolders:
                    display_name = folder.name
                    existing_key = _matching_episode_group_key(grouped_candidates, display_name)
                    group_key = existing_key or _episode_group_key(display_name)
                    episode_id = _episode_id_from_folder_name(display_name)
                    current = grouped_candidates.get(group_key)
                    if current is None or _prefer_episode_display_name(display_name, current[1], priority, current[2]):
                        grouped_candidates[group_key] = (episode_id, display_name, priority)
            elif _folder_has_files(role_folder):
                candidate = ("1", ".")
                grouped_candidates.setdefault(".", (candidate[0], candidate[1], priority))
    ordered = sorted(grouped_candidates.values(), key=lambda item: (item[2], item[1].casefold()))
    return [(episode_id, folder_name) for episode_id, folder_name, _priority in ordered]


def _scoped_repeatable_episode_candidate(
    loaded: LoadedCase, step: dict[str, Any], terms: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Collapse phase-specific folder aliases across originals/translations into one unit."""
    roles = _normalize_path_list(step.get("evidence_folder_roles", []))
    role_map = folder_role_map(loaded.config)
    matches: list[tuple[int, str]] = []
    for role in roles:
        folder_name = str(role_map.get(role, role))
        for priority, source_key in enumerate(["source_originals", "source_translations", "source_other"]):
            source_root = loaded.case_dir / _case_path_value(loaded.config, source_key)
            role_folder = source_root / folder_name
            if not role_folder.exists():
                continue
            for child in sorted(role_folder.iterdir()):
                if (
                    child.is_dir()
                    and _folder_has_files(child)
                    and _episode_folder_matches_terms(child.name, terms)
                ):
                    matches.append((priority, child.name))
    if not matches:
        return []
    matches.sort(key=lambda item: (item[0], _display_name_penalty(item[1]), -len(item[1])))
    display_name = matches[0][1]
    shared_id = str(step.get("shared_episode_id", "")).strip()
    episode_id = safe_path_component(shared_id) if shared_id else _episode_id_from_folder_name(display_name)
    return [(episode_id, display_name)]


def _episode_folder_terms(step: dict[str, Any]) -> tuple[str, ...]:
    terms = _normalize_path_list(step.get("episode_folder_terms", []))
    return tuple(term for term in terms if term)


def _episode_folder_matches_terms(name: str, terms: tuple[str, ...]) -> bool:
    normalized_name = _normalized_episode_name(name)
    if not normalized_name:
        return False
    for term in terms:
        normalized_term = _normalized_episode_name(term)
        if normalized_term and (
            normalized_term in normalized_name or normalized_name in normalized_term
        ):
            return True
    return False


def _repeatable_candidates_from_evidence_sources(
    loaded: LoadedCase, step: dict[str, Any]
) -> list[tuple[str, str]]:
    sources = step.get("evidence_sources", [])
    if not isinstance(sources, list):
        return []
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        if not isinstance(source, dict) or not _truthy_config(source.get("use_episode_folder", False)):
            continue
        path_key = str(source.get("path_key", ""))
        folder_value = str(source.get("folder", "."))
        if not path_key:
            continue
        try:
            source_root = loaded.case_dir / _case_path_value(loaded.config, path_key)
        except SystemExit:
            continue
        folder = source_root if folder_value in {"", "."} else source_root / folder_value
        if not folder.exists():
            continue
        subfolders = [path for path in sorted(folder.iterdir()) if path.is_dir() and _folder_has_files(path)]
        if subfolders:
            for child in subfolders:
                episode_id = _episode_id_from_folder_name(child.name)
                candidate = (episode_id, child.name)
                if candidate not in seen:
                    candidates.append(candidate)
                    seen.add(candidate)
        elif _folder_has_files(folder):
            candidate = ("1", ".")
            if candidate not in seen:
                candidates.append(candidate)
                seen.add(candidate)
    return candidates


def _episode_id_from_folder_name(name: str) -> str:
    stripped = name.strip()
    normalized = re.sub(r"\s+", " ", stripped)
    normalized = normalized.replace(" / ", " ")
    normalized = re.sub(r"^[._\-\s]+", "", normalized)
    return safe_path_component(normalized)


def _episode_group_key(name: str) -> str:
    normalized = _normalized_episode_name(name)
    return normalized or safe_path_component(name)


def _normalized_episode_name(name: str) -> str:
    value = _transliterate_cyrillic(name.lower())
    value = re.sub(r"[_/\\\-\.,()\[\]{}]+", " ", value)
    value = re.sub(
        r"\b(translation|translated|english|eng|en|perevod|angl|angliiskii|copy|kopiya|scan|skan|version|episode)\b",
        " ",
        value,
    )
    value = re.sub(r"\b\d{4}\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


_CALENDAR_TOKENS = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "yanvar", "fevral",
    "mart", "aprel", "mai", "iyun", "iyul", "avgust", "sentyabr", "oktyabr",
    "noyabr", "dekabr",
}


def _episode_acronym(name: str) -> str:
    tokens = [
        token
        for token in _normalized_episode_name(name).split()
        if token not in _CALENDAR_TOKENS and not token.isdigit()
    ]
    if len(tokens) < 2:
        return ""
    return "".join(token[0] for token in tokens if token)


def _names_match_by_acronym(left: str, right: str) -> bool:
    left_normalized = _normalized_episode_name(left).replace(" ", "")
    right_normalized = _normalized_episode_name(right).replace(" ", "")
    left_acronym = _episode_acronym(left)
    right_acronym = _episode_acronym(right)
    return bool(
        (2 <= len(left_normalized) <= 8 and left_normalized == right_acronym)
        or (2 <= len(right_normalized) <= 8 and right_normalized == left_acronym)
    )


def _matching_episode_group_key(
    grouped_candidates: dict[str, tuple[str, str, int]], display_name: str
) -> str:
    for key, (_episode_id, existing_name, _priority) in grouped_candidates.items():
        if _episode_folder_similarity(existing_name, display_name) >= 0.78:
            return key
    return ""


def _folder_has_files(path: Path) -> bool:
    return any(item.is_file() and item.name != ".gitkeep" for item in path.rglob("*"))


def _prefer_episode_display_name(new_name: str, old_name: str, new_priority: int, old_priority: int) -> bool:
    if new_priority != old_priority:
        return new_priority < old_priority
    new_penalty = _display_name_penalty(new_name)
    old_penalty = _display_name_penalty(old_name)
    if new_penalty != old_penalty:
        return new_penalty < old_penalty
    return len(new_name) > len(old_name)


def _display_name_penalty(name: str) -> tuple[int, int]:
    lowered = name.casefold()
    is_template_like = 1 if lowered in {"1 episode", "episode", "."} else 0
    has_eng_suffix = 1 if re.search(r"(^|[_\s-])eng($|[_\s-])", lowered) else 0
    return (is_template_like, has_eng_suffix)


def _episode_folder_similarity(left: str, right: str) -> float:
    left_normalized = _normalized_episode_name(left)
    right_normalized = _normalized_episode_name(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    if _names_match_by_acronym(left, right):
        return 0.99
    if min(len(left_normalized), len(right_normalized)) >= 3 and (
        left_normalized in right_normalized or right_normalized in left_normalized
    ):
        return 0.96
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens)
    containment = overlap / max(1, min(len(left_tokens), len(right_tokens)))
    union = overlap / max(1, len(left_tokens | right_tokens))
    sequence = _sequence_similarity(left_normalized, right_normalized)
    return min(1.0, max(sequence, (0.75 * containment) + (0.25 * union)))


def _citation_plan_for_step(
    loaded: LoadedCase, step: dict[str, Any], options: PromptOptions
) -> dict[str, str]:
    step_id = str(step.get("step_id", ""))
    configured_exhibit = str(step.get("exhibit_number", "")).strip()
    configured_prefix = str(step.get("item_prefix", "")).strip()
    if configured_exhibit:
        if "repeatable" in str(step.get("execution", "")) and not configured_prefix:
            candidates = _repeatable_episode_candidates(loaded, step)
            position = next(
                (
                    index
                    for index, (episode_id, _folder) in enumerate(candidates, start=1)
                    if episode_id == options.episode_id
                ),
                1,
            )
            configured_prefix = f"{configured_exhibit}.{position}."
        return {
            "exhibit_number": configured_exhibit,
            "item_prefix": configured_prefix or f"{configured_exhibit}.",
        }
    if step_id == "professional_biography":
        return {"exhibit_number": "0", "item_prefix": "0."}
    if step_id.startswith("recommendation_letters"):
        return {"exhibit_number": "0-1", "item_prefix": "0-1."}
    role_map = {
        "awards": "1",
        "memberships": "2",
        "media": "3",
        "judging": "4",
        "original_contribution": "5",
        "scholarly_articles": "6",
        "exhibitions": "7",
        "leading_critical_role": "8",
        "high_salary": "9",
        "commercial_success": "10",
        "employment_plan": "11",
    }
    roles = _normalize_path_list(step.get("evidence_folder_roles", []))
    role = roles[0] if len(roles) == 1 else ""
    exhibit_number = role_map.get(role, "")
    if not exhibit_number:
        return {}
    if "repeatable" not in str(step.get("execution", "")):
        return {"exhibit_number": exhibit_number, "item_prefix": f"{exhibit_number}."}
    candidates = _repeatable_episode_candidates(loaded, step)
    episode_position = next(
        (
            index
            for index, (episode_id, _folder) in enumerate(candidates, start=1)
            if episode_id == options.episode_id
        ),
        1,
    )
    return {
        "exhibit_number": exhibit_number,
        "item_prefix": f"{exhibit_number}.{episode_position}.",
    }


def _sequence_similarity(left: str, right: str) -> float:
    # Local import keeps the top-level import list lean for the usual CLI path.
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left, right).ratio()


def _first_case_config_placeholder(config: dict[str, Any]) -> str:
    for key in ["field", "specialization", "procedural_context", "drafting_objective"]:
        value = str(config.get(key, ""))
        if value.startswith("__") and value.endswith("__"):
            return key
    if str(config.get("task_type", "")) == "eb1a_rfe_response":
        metadata = config.get("rfe_metadata", {})
        if isinstance(metadata, dict):
            for key in ["case_number", "receipt_date", "rfe_date", "response_deadline", "uscis_address"]:
                value = str(metadata.get(key, ""))
                if value.startswith("__") and value.endswith("__"):
                    return f"rfe_metadata.{key}"
    if str(config.get("task_type", "")) == "o1b_petition":
        for dotted in [
            "petitioner.company_name",
            "petitioner.company_address",
            "petitioner.authorized_signatory",
            "filing.validity_start",
            "filing.validity_end",
            "filing.uscis_address",
            "us_work.position_or_role",
            "us_work.compensation",
            "us_work.work_location",
            "us_work.duties_summary",
        ]:
            value: Any = config
            for part in dotted.split("."):
                value = value.get(part, "") if isinstance(value, dict) else ""
            if str(value).startswith("__") and str(value).endswith("__"):
                return dotted
    beneficiary = config.get("beneficiary", {})
    if isinstance(beneficiary, dict):
        for key in ["full_name", "preferred_reference"]:
            value = str(beneficiary.get(key, ""))
            if value.startswith("__") and value.endswith("__"):
                return f"beneficiary.{key}"
    return ""


def _enabled_steps(config: dict[str, Any]) -> set[str]:
    raw = config.get("enabled_steps", [])
    values = set(_normalize_path_list(raw))
    return {value for value in values if value}


def _compact_next_status(loaded: LoadedCase) -> str:
    rows = _read_document_index_rows(loaded)
    pending_manual = [
        row
        for row in rows
        if "Manual description placeholder:" in row.get("notes", "")
        and row.get("extraction_status") != "manual_description_available"
    ]
    unlinked_translations = [
        row
        for row in rows
        if row.get("translation_status") == "translation" and not row.get("parent_document_id")
    ]
    return "\n".join(
        [
            f"- indexed documents: {len(rows)}",
            f"- pending manual descriptions: {len(pending_manual)}",
            f"- unlinked translations: {len(unlinked_translations)}",
            f"- exhibits: {len(_read_exhibit_index_rows(loaded))}",
        ]
    )


def _read_document_index_rows(loaded: LoadedCase) -> list[dict[str, str]]:
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    if not index_path.exists():
        return []
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_exhibit_index_rows(loaded: LoadedCase) -> list[dict[str, str]]:
    try:
        index_path = loaded.case_dir / _case_path_value(loaded.config, "exhibit_index")
    except SystemExit:
        return []
    if not index_path.exists():
        return []
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def validate_llm_output(
    data: Any, loaded: LoadedCase, step_id: str, options: PromptOptions | None = None
) -> None:
    options = options or PromptOptions()
    step = find_step(loaded.workflow, step_id)
    if not isinstance(data, dict):
        raise SystemExit("LLM output must be a JSON object.")
    required = [
        "case_id",
        "task_type",
        "step_id",
        "draft_text",
        "used_documents",
        "unsupported_claims",
        "questions_for_user",
        "quality_flags",
        "revision_notes",
    ]
    missing = [field for field in required if field not in data]
    if missing:
        raise SystemExit(f"LLM output is missing required field(s): {', '.join(missing)}")
    if data["case_id"] != loaded.case_id:
        raise SystemExit(f"case_id mismatch: expected {loaded.case_id}, got {data['case_id']}")
    if data["task_type"] != loaded.config.get("task_type"):
        raise SystemExit(
            f"task_type mismatch: expected {loaded.config.get('task_type')}, got {data['task_type']}"
        )
    if data["step_id"] != step_id:
        raise SystemExit(f"step_id mismatch: expected {step_id}, got {data['step_id']}")
    if options.episode_id and data.get("episode_id") != options.episode_id:
        raise SystemExit(
            f"episode_id mismatch: expected {options.episode_id}, got {data.get('episode_id')}"
        )
    if not isinstance(data["draft_text"], str) or not data["draft_text"].strip():
        raise SystemExit("draft_text must be a non-empty string.")
    draft_text = data["draft_text"].strip()
    technical_step = step_id in {"opening_context_intake", "template_review"}
    evidence_based = bool(step.get("evidence_folder_roles")) or bool(step.get("evidence_sources"))
    minimum_length = 20 if technical_step else 40
    if len(draft_text) < minimum_length:
        raise SystemExit(
            f"draft_text is too short for {step_id}: {len(draft_text)} characters; "
            f"expected at least {minimum_length}. Ask the LLM to return the complete requested output."
        )
    if draft_text.startswith("```") or draft_text.lower().startswith("here is the json"):
        raise SystemExit("draft_text appears to contain a wrapper instead of the requested section text.")
    if not technical_step:
        _validate_human_facing_draft_text(draft_text, loaded, step, options)
    for field in ["used_documents", "unsupported_claims", "questions_for_user", "quality_flags", "revision_notes"]:
        if not isinstance(data[field], list):
            raise SystemExit(f"{field} must be an array.")
    for index, item in enumerate(data["used_documents"], start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"used_documents item {index} must be an object.")
        for field in ["document_id", "document_title", "used_for"]:
            if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                raise SystemExit(f"used_documents item {index} missing string field: {field}")
        title = str(item.get("document_title", "")).strip()
        if not technical_step and re.search(r"[\u0400-\u04ff]", title):
            raise SystemExit(
                f"used_documents item {index} has a non-English document_title: {title!r}. "
                "Ask the LLM for a concise descriptive English title; do not reuse the Russian filename."
            )
        if len(title) > 180:
            raise SystemExit(
                f"used_documents item {index} document_title is too long ({len(title)} characters). "
                "Use a concise English exhibit title."
            )
    indexed_ids = {row.get("document_id", "") for row in _read_document_index_rows(loaded)}
    unknown_ids = sorted(
        {
            str(item.get("document_id", ""))
            for item in data["used_documents"]
            if str(item.get("document_id", "")) not in indexed_ids
        }
    )
    if unknown_ids:
        raise SystemExit(
            "used_documents contains document IDs that are not present in document_index.csv: "
            + ", ".join(unknown_ids)
        )
    selection_enforced = evidence_based or _truthy_config(step.get("rfe_strategy_units", False))
    if selection_enforced:
        allowed_ids = {
            row.get("document_id", "")
            for row in selected_documents_for_step(loaded, step, options)
            if row.get("document_id", "")
        }
        unselected_ids = sorted(
            {
                str(item.get("document_id", ""))
                for item in data["used_documents"]
                if str(item.get("document_id", "")) not in allowed_ids
            }
        )
        if unselected_ids:
            raise SystemExit(
                "used_documents contains IDs that were not in this prompt's Technical document selection: "
                + ", ".join(unselected_ids)
                + ". Auxiliary info/readme/extract files may guide drafting but can never be cited."
            )
    if not technical_step and evidence_based and not data["used_documents"]:
        raise SystemExit(
            f"{step_id} is an evidence-based drafting step, but used_documents is empty. "
            "Ask the LLM to identify the indexed evidence it relied on."
        )
def _validate_human_facing_draft_text(
    draft_text: str, loaded: LoadedCase, step: dict[str, Any], options: PromptOptions
) -> None:
    lowered = draft_text.casefold()
    forbidden_phrases = [
        "this episode",
        "within this episode",
        "submitted in this episode",
        "episode documents",
        "source prompt",
        "selected evidence reviewed",
        "evidence bundle reviewed",
        "current prompt",
        "machine-readable",
        "garbled",
        "the extracted text",
        "extractable evidence",
        "the llm",
        "the model",
        "does not yet establish",
        "does not prove",
        "cannot rely on",
        "should not be used",
        "contextual evidence only",
        "final petition should",
        "before this episode is used",
        "claimed specialization",
        "endlessly charming",
        "bureaucracy, regrettably",
        "deserve some restraint",
        "apparently even",
    ]
    found = sorted({phrase for phrase in forbidden_phrases if phrase in lowered})
    if re.search(r"\bepisode\b", lowered):
        found.append("episode")
    if re.search(r"source\s+(?:prompt|documents?|materials?).{0,80}\breviewed\s*:", lowered):
        found.append("source ... reviewed:")
    if re.search(r"\b(?:ocr|parsing)\s+(?:failure|limitation|issue|problem|needed|required)\b", lowered):
        found.append("OCR/parsing limitation language")
    if found:
        raise SystemExit(
            "draft_text contains internal workflow/AI language or prohibited petition phrasing: "
            + ", ".join(found)
            + ". Remove it from draft_text and place any internal concern in unsupported_claims, "
            "questions_for_user, quality_flags, or revision_notes."
        )

    if str(loaded.config.get("task_type", "")) == "o1b_petition":
        o1b_forbidden = [
            phrase
            for phrase in ["eb-1a", "form i-140", "permanent residence", "national interest"]
            if phrase in lowered
        ]
        if "214.1(c)(5)(1)" in lowered or "214.1(c)(5)(i)" in lowered:
            o1b_forbidden.append("stale O-1 consultation citation")
        if o1b_forbidden:
            raise SystemExit(
                "O-1B draft_text contains terminology or a citation from another petition framework: "
                + ", ".join(sorted(set(o1b_forbidden)))
                + ". Regenerate the section under the configured O-1B Arts/MPTV rules."
            )

    citation = _citation_plan_for_step(loaded, step, options)
    exhibit_number = citation.get("exhibit_number", "")
    item_prefix = citation.get("item_prefix", "")
    if exhibit_number and item_prefix.count(".") >= 2:
        expected_first = item_prefix.split(".", 1)[0]
        numbered_items = re.findall(r"(?m)^\s*(\d+)\.(\d+)\.(\d+)\.\s+", draft_text)
        wrong = sorted({".".join(item) for item in numbered_items if item[0] != expected_first})
        if wrong:
            raise SystemExit(
                f"draft_text uses exhibit-list numbering from the wrong criterion: {', '.join(wrong)}. "
                f"This step belongs to Exhibit {exhibit_number} and its list items must start with {item_prefix}"
            )


def _update_document_titles_from_llm(loaded: LoadedCase, data: dict[str, Any]) -> None:
    """Persist validated, human-readable English exhibit titles in document_index.csv."""
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    if not index_path.exists():
        return
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not fieldnames or "document_id" not in fieldnames or "display_title" not in fieldnames:
        return
    titles = {
        str(item.get("document_id", "")).strip(): str(item.get("document_title", "")).strip()
        for item in data.get("used_documents", [])
        if isinstance(item, dict)
    }
    changed = False
    for row in rows:
        document_id = row.get("document_id", "")
        title = titles.get(document_id, "")
        if not title or _truthy_config(row.get("manual_edit_lock", False)):
            continue
        if row.get("display_title", "") != title:
            row["display_title"] = title
            changed = True
    if not changed:
        return
    with index_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_repeatable_options(step: dict[str, Any], options: PromptOptions) -> None:
    is_repeatable = "repeatable" in str(step.get("execution", ""))
    if is_repeatable and not options.episode_id:
        raise SystemExit(
            f"Step '{step.get('step_id')}' is repeatable. Provide --episode-id, "
            "for example --episode-id 1."
        )


def output_stem(step_id: str, episode_id: str = "") -> str:
    if episode_id:
        return f"{step_id}.{safe_path_component(episode_id)}"
    return step_id


def destination_for_step(step: dict[str, Any], options: PromptOptions) -> str:
    destination = step.get("destination")
    if destination:
        return str(destination)
    pattern = step.get("destination_pattern")
    if not pattern:
        return ""
    safe_episode = safe_path_component(options.episode_id)
    return str(pattern).format(
        episode_id=safe_episode,
        component_id=safe_episode,
    )


def safe_path_component(value: str) -> str:
    value = value.strip()
    # Keep Unicode letters and digits: evidence folders are commonly named in
    # Russian and other non-Latin languages.  Separators and Windows-invalid
    # punctuation are still replaced, so the result remains one path segment.
    safe = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE)
    safe = safe.strip("._-")
    if not safe or safe in {".", ".."}:
        raise SystemExit(f"Invalid path component: {value!r}")
    return safe


def read_textual_file(path: Path, limit: int) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix in TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        elif suffix in DOCX_EXTENSIONS:
            text = extract_docx_text(path)
        else:
            text = f"[Unsupported source file type for prompt text extraction: {path.name}]"
    except Exception as exc:  # noqa: BLE001 - prompt should include extraction failures.
        text = f"[Could not read file: {path} ({exc})]"
    if len(text) > limit:
        return text[:limit] + f"\n\n[Truncated at {limit} characters.]"
    return text


def _episode_folder_for(role_folder: Path, options: PromptOptions) -> Path:
    if options.episode_folder:
        return role_folder / options.episode_folder
    if not options.episode_id:
        return role_folder
    if not role_folder.exists():
        return role_folder / options.episode_id

    episode_id = options.episode_id.strip().lower()
    candidates = []
    for child in sorted(role_folder.iterdir()):
        if not child.is_dir():
            continue
        name = child.name.strip().lower()
        if (
            name == episode_id
            or name.startswith(f"{episode_id} ")
            or name.startswith(f"{episode_id}.")
            or name.startswith(f"{episode_id}_")
            or name.startswith(f"{episode_id}-")
        ):
            candidates.append(child)
    if len(candidates) == 1:
        return candidates[0]
    return role_folder / options.episode_id


def _episode_folders_for(
    role_folder: Path, options: PromptOptions, step: dict[str, Any] | None = None
) -> list[Path]:
    if not role_folder.exists():
        return []
    scoped_terms = _episode_folder_terms(step or {})
    if scoped_terms:
        selected = [
            child
            for child in sorted(role_folder.iterdir())
            if child.is_dir()
            and _folder_has_files(child)
            and _episode_folder_matches_terms(child.name, scoped_terms)
        ]
        return _phase_folders_for(selected, step or {})
    if not options.episode_id and not options.episode_folder:
        selected = [role_folder] if _folder_has_files(role_folder) else []
        return _phase_folders_for(selected, step or {})

    exact = _episode_folder_for(role_folder, options)
    matched: list[Path] = []
    seen: set[Path] = set()
    if exact.exists() and exact.is_dir() and _folder_has_files(exact):
        matched.append(exact)
        seen.add(exact.resolve())

    target_key = _episode_group_key(options.episode_folder or options.episode_id)
    for child in sorted(role_folder.iterdir()):
        if not child.is_dir() or not _folder_has_files(child):
            continue
        if _episode_group_key(child.name) != target_key and _episode_folder_similarity(
            child.name, options.episode_folder or options.episode_id
        ) < 0.78:
            continue
        resolved = child.resolve()
        if resolved in seen:
            continue
        matched.append(child)
        seen.add(resolved)
    return _phase_folders_for(matched, step or {})


def _phase_folders_for(episode_folders: list[Path], step: dict[str, Any]) -> list[Path]:
    terms = tuple(_normalize_path_list(step.get("phase_subfolder_terms", [])))
    if not terms:
        return episode_folders
    matches: list[Path] = []
    seen: set[Path] = set()
    for episode_folder in episode_folders:
        for child in sorted(path for path in episode_folder.rglob("*") if path.is_dir()):
            if not _folder_has_files(child) or not _episode_folder_matches_terms(child.name, terms):
                continue
            resolved = child.resolve()
            if resolved not in seen:
                matches.append(child)
                seen.add(resolved)
    if matches or _truthy_config(step.get("phase_subfolder_required", False)):
        return matches
    return episode_folders


def _transliterate_cyrillic(value: str) -> str:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    return "".join(mapping.get(character, character) for character in value)


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        runs = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(unescape(text))
    return "\n\n".join(paragraphs)


def folder_role_map(config: dict[str, Any]) -> dict[str, Any]:
    task_type = str(config.get("task_type", ""))
    preferred_keys = (
        ["o1b_folder_roles", "folder_roles", "eb1a_folder_roles"]
        if task_type == "o1b_petition"
        else ["eb1a_folder_roles", "folder_roles", "o1b_folder_roles"]
    )
    for key in preferred_keys:
        value = config.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _case_path_value(config: dict[str, Any], key: str) -> Path:
    paths = config.get("paths", {})
    if not isinstance(paths, dict):
        raise SystemExit("case_config.yaml field 'paths' must be a mapping.")
    value = paths.get(key)
    if not value:
        raise SystemExit(f"case_config.yaml is missing paths.{key}")
    return Path(str(value))


def _resolve_project_or_case_path(case_dir: Path, path_value: str) -> Path:
    if not path_value:
        return case_dir / "__missing__"
    path = Path(path_value)
    if path.is_absolute():
        return path
    case_candidate = case_dir / path
    if case_candidate.exists():
        return case_candidate
    return PROJECT_ROOT / path


def _normalize_path_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _truthy_config(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _fenced(text: str, language: str = "") -> str:
    fence = "```"
    if "```" in text:
        fence = "````"
    return f"{fence}{language}\n{text.strip()}\n{fence}"


def _fence_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".csv":
        return "csv"
    if suffix in {".md", ".txt", ".docx"}:
        return "text"
    return ""


def _normalize_slashes(value: str) -> str:
    return re.sub(r"\\+", "/", value or "").strip()
