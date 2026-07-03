from __future__ import annotations

import json
import filecmp
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cli_support import PROJECT_ROOT, case_path
from .file_rules import is_office_temporary_file, is_prompt_sidecar
from .workflow import (
    EVIDENCE_TEXT_LIMIT,
    PROMPT_TEXT_LIMIT,
    LoadedCase,
    read_document_index,
    read_textual_file,
    safe_path_component,
)


STRATEGY_ROOT = "case_strategy"
MANIFEST_NAME = "strategy_manifest.json"
BOOTSTRAP_PROMPT_STEM = "rfe_strategy_bootstrap"

CRITERION_ALIASES: dict[str, tuple[str, ...]] = {
    "awards": ("awards", "prizes", "receipt of lesser nationally", "criterion (i)"),
    "memberships": ("membership in associations", "associations", "criterion (ii)"),
    "media": ("published material about", "published material", "criterion (iii)"),
    "judging": ("judge of the work of others", "judging", "criterion (iv)"),
    "original_contribution": ("original contributions", "original contribution", "criterion (v)"),
    "scholarly_articles": ("authorship of scholarly articles", "scholarly articles", "criterion (vi)"),
    "exhibitions": ("artistic exhibitions", "exhibitions", "criterion (vii)"),
    "leading_critical_role": ("leading or critical role", "critical role", "criterion (viii)"),
    "high_salary": ("high salary", "significantly high remuneration", "criterion (ix)"),
    "commercial_success": ("commercial successes", "commercial success", "criterion (x)"),
}

CRITERION_FOLDER_ORDERS = {
    "awards": 1,
    "memberships": 2,
    "media": 3,
    "judging": 4,
    "original_contribution": 5,
    "scholarly_articles": 6,
    "exhibitions": 7,
    "leading_critical_role": 8,
    "high_salary": 9,
    "commercial_success": 10,
}

NON_DRAFTING_SECTION_TYPES = {"cover_letter", "attachments"}


@dataclass(frozen=True)
class BootstrapSummary:
    prompt_path: Path
    strategy_copy: Path
    rfe_copy: Path


@dataclass(frozen=True)
class StrategyImportSummary:
    manifest_path: Path
    unit_count: int
    plan_path: Path


@dataclass(frozen=True)
class EvidenceImportSummary:
    copied_files: int
    skipped_files: int
    initial_sections: int
    report_path: Path


def build_strategy_bootstrap_prompt(case_id: str, strategy_path: str, rfe_path: str) -> BootstrapSummary:
    case_dir = case_path(case_id)
    strategy_source = _required_source_file(strategy_path, "Strategy")
    rfe_source = _required_source_file(rfe_path, "RFE")
    strategy_copy = _copy_source_file(strategy_source, case_dir / "source_documents/rfe/strategy")
    rfe_copy = _copy_source_file(rfe_source, case_dir / "source_documents/rfe/notice")

    raw_root = case_dir / STRATEGY_ROOT / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    strategy_text = _extract_text(strategy_copy)
    rfe_text = _extract_text(rfe_copy)
    (raw_root / "human_strategy.txt").write_text(strategy_text, encoding="utf-8")
    (raw_root / "rfe_notice.txt").write_text(rfe_text, encoding="utf-8")

    human_template_path = PROJECT_ROOT / "templates/RFE/EB1/rfe draft template.docx"
    yaml_template_path = PROJECT_ROOT / "templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.yaml"
    schema_path = PROJECT_ROOT / "schemas/rfe_strategy_output.schema.json"
    instruction_path = PROJECT_ROOT / "instructions/task_types/eb1a_rfe_response/strategy_bootstrap.md"
    prompt = "\n".join(
        [
            "# EXECUTE NOW: build the EB-1A RFE strategy JSON",
            "",
            "You are receiving a complete task, not a file for review. Perform the task now. Do not ask what the user wants, do not offer a menu of possible actions, and do not acknowledge the prompt. Return only the completed JSON object required below.",
            "",
            "## Runtime metadata",
            "",
            f"- case_id: `{case_id}`",
            "- task_type: `eb1a_rfe_response`",
            "- step_id: `rfe_strategy_bootstrap`",
            "",
            "## Required output schema",
            "",
            _fenced(schema_path.read_text(encoding="utf-8-sig"), "json"),
            "",
            "## Bootstrap instructions",
            "",
            instruction_path.read_text(encoding="utf-8-sig"),
            "",
            "## Human strategy (highest-priority case-specific source)",
            "",
            f"Source: `{strategy_copy.relative_to(case_dir).as_posix()}`",
            "",
            _fenced(strategy_text, "text"),
            "",
            "## Full RFE notice",
            "",
            f"Source: `{rfe_copy.relative_to(case_dir).as_posix()}`",
            "",
            _fenced(rfe_text, "text"),
            "",
            "## Human company Word template (visual and structural authority)",
            "",
            f"Source: `{human_template_path.relative_to(PROJECT_ROOT).as_posix()}`",
            "",
            _fenced(_extract_text(human_template_path), "text"),
            "",
            "## Company YAML template (drafting and assembly authority)",
            "",
            f"Source: `{yaml_template_path.relative_to(PROJECT_ROOT).as_posix()}`",
            "",
            _fenced(yaml_template_path.read_text(encoding="utf-8-sig", errors="replace"), "yaml"),
            "",
            "## Required response",
            "",
            "EXECUTE THE ANALYSIS AND GENERATE THE JSON NOW.",
            f"Return only one JSON object. Set `case_id` to `{case_id}` and `task_type` to `eb1a_rfe_response`. Do not ask a question and do not add introductory or closing prose. Validate strict JSON before sending: escape internal double quotes as `\\\"`, encode string line breaks as `\\n`, and remove all trailing commas.",
        ]
    )
    prompt_root = case_dir / "generated_prompts"
    prompt_root.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_root / f"{BOOTSTRAP_PROMPT_STEM}.latest.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    _remember_source_paths(case_dir, {"rfe_strategy_file": strategy_source, "rfe_notice_file": rfe_source})
    return BootstrapSummary(prompt_path=prompt_path, strategy_copy=strategy_copy, rfe_copy=rfe_copy)


def apply_strategy_output(case_id: str, output: dict[str, Any]) -> StrategyImportSummary:
    _validate_strategy_output(case_id, output)
    case_dir = case_path(case_id)
    strategy_root = case_dir / STRATEGY_ROOT
    strategy_root.mkdir(parents=True, exist_ok=True)
    raw_output = strategy_root / "llm_strategy_output.json"
    raw_output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    issues = {str(item["issue_id"]): item for item in output["rfe_issues"]}
    units: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for section in sorted(output["sections"], key=lambda item: int(item["order"])):
        if not section.get("required", True):
            continue
        episodes = section.get("episodes") or [
            {
                "episode_id": section["section_id"],
                "title": section["title"],
                "source_folder": section.get("source_folder", ""),
                "strategy": "",
                "rfe_issue_ids": section.get("rfe_issue_ids", []),
                "initial_filing_heading_hints": section.get("initial_filing_heading_hints", []),
            }
        ]
        for episode_index, episode in enumerate(episodes, start=1):
            raw_id = str(episode.get("episode_id") or section["section_id"])
            unit_id = safe_path_component(raw_id)
            if unit_id in used_ids:
                unit_id = safe_path_component(f"{section['section_id']}_{raw_id}_{episode_index}")
            used_ids.add(unit_id)
            issue_ids = list(dict.fromkeys([*section.get("rfe_issue_ids", []), *episode.get("rfe_issue_ids", [])]))
            unit = {
                "unit_id": unit_id,
                "order": len(units) + 1,
                "section_id": str(section["section_id"]),
                "section_order": int(section["order"]),
                "title": str(episode.get("title") or section["title"]),
                "section_title": str(section["title"]),
                "section_type": str(section["section_type"]),
                "criterion_role": str(section.get("criterion_role", "")),
                "source_folder": str(episode.get("source_folder") or section.get("source_folder", "")),
                "strategy": "\n\n".join(
                    part.strip()
                    for part in [str(section.get("strategy", "")), str(episode.get("strategy", ""))]
                    if part and part.strip()
                ),
                "rfe_issue_ids": issue_ids,
                "rfe_issues": [issues[item] for item in issue_ids if item in issues],
                "starter_text": str(section.get("starter_text", "")) if episode_index == 1 else "",
                "initial_filing_heading_hints": list(
                    dict.fromkeys(
                        [
                            *section.get("initial_filing_heading_hints", []),
                            *episode.get("initial_filing_heading_hints", []),
                        ]
                    )
                ),
                "planned_subheadings": list(episode.get("planned_subheadings", [])),
            }
            units.append(unit)

    manifest = {
        "schema_version": "1.0",
        "case_id": case_id,
        "task_type": "eb1a_rfe_response",
        "case_metadata": output["case_metadata"],
        "global_strategy": output["global_strategy"],
        "accepted_criteria": output.get("accepted_criteria", []),
        "challenged_criteria": output.get("challenged_criteria", []),
        "rfe_issues": output["rfe_issues"],
        "template_decisions": output["template_decisions"],
        "open_questions": output["open_questions"],
        "units": units,
    }
    manifest_path = strategy_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_unit_files(case_dir, manifest)
    _update_case_config(case_dir, manifest)
    plan_path = case_dir / "rfe_response_plan.md"
    plan_path.write_text(_render_plan(manifest), encoding="utf-8")
    return StrategyImportSummary(manifest_path=manifest_path, unit_count=len(units), plan_path=plan_path)


def import_evidence_and_scan_inputs(
    case_id: str,
    initial_memo_path: str,
    new_documents_path: str,
) -> EvidenceImportSummary:
    case_dir = case_path(case_id)
    if not strategy_manifest_path(case_dir).exists():
        raise ValueError("Accept the RFE strategy JSON before importing evidence.")
    memo_source = _required_source(initial_memo_path, "Initial filing memorandum")
    new_source = _required_source(new_documents_path, "New RFE documents")

    copied = skipped = 0
    c, s = _copy_any(memo_source, case_dir / "source_documents/initial_filing/memorandum")
    copied += c
    skipped += s
    c, s = _copy_bilingual_tree(new_source, case_dir / "source_documents/rfe_response/new_documents")
    copied += c
    skipped += s
    _remember_source_paths(
        case_dir,
        {
            "initial_filing_memo": memo_source,
            "rfe_new_documents": new_source,
        },
    )
    sections, report_path = partition_initial_filing(case_id)
    return EvidenceImportSummary(copied, skipped, sections, report_path)


def partition_initial_filing(case_id: str) -> tuple[int, Path]:
    case_dir = case_path(case_id)
    memo_root = case_dir / "source_documents/initial_filing/memorandum"
    files = [path for path in sorted(memo_root.rglob("*")) if path.is_file() and path.name != ".gitkeep"]
    if not files:
        raise ValueError("No initial filing memorandum was imported.")
    text = "\n\n".join(_extract_text(path) for path in files)
    output_root = case_dir / STRATEGY_ROOT / "initial_filing_sections"
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "_full_initial_filing.txt").write_text(text, encoding="utf-8")
    manifest = load_strategy_manifest(case_dir)
    hints: dict[str, list[str]] = {role: list(aliases) for role, aliases in CRITERION_ALIASES.items()}
    for unit in manifest.get("units", []):
        role = str(unit.get("criterion_role", ""))
        if role:
            hints.setdefault(role, []).extend(str(item) for item in unit.get("initial_filing_heading_hints", []))
    sections = _split_by_criterion(text, hints)
    report_lines = ["# Initial filing partition report", "", f"- source files: {len(files)}", f"- extracted characters: {len(text)}", ""]
    for role in sorted(set(manifest.get("challenged_criteria", [])) | {str(unit.get("criterion_role", "")) for unit in manifest.get("units", []) if unit.get("criterion_role")}):
        section_text = sections.get(role, "")
        if section_text:
            (output_root / f"{safe_path_component(role)}.txt").write_text(section_text, encoding="utf-8")
            report_lines.append(f"- {role}: {len(section_text)} characters")
        else:
            report_lines.append(f"- {role}: heading not found; full memorandum remains available for manual review")
    report_path = case_dir / "reports/initial_filing_partition_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return sum(bool(value) for value in sections.values()), report_path


def strategy_manifest_path(case_dir: Path) -> Path:
    return case_dir / STRATEGY_ROOT / MANIFEST_NAME


def load_strategy_manifest(case_dir: Path) -> dict[str, Any]:
    path = strategy_manifest_path(case_dir)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def list_strategy_units(loaded: LoadedCase) -> list[tuple[str, str]]:
    return [
        (str(unit["unit_id"]), str(unit.get("source_folder", "")))
        for unit in effective_strategy_units(loaded.case_dir, loaded.config)
        if str(unit.get("section_type", "")) not in NON_DRAFTING_SECTION_TYPES
    ]


def get_strategy_unit(
    case_dir: Path, unit_id: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    units = (
        effective_strategy_units(case_dir, config)
        if config is not None
        else load_strategy_manifest(case_dir).get("units", [])
    )
    for unit in units:
        if str(unit.get("unit_id")) == unit_id:
            return unit
    return {}


def effective_strategy_units(case_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconcile LLM strategy with the folders that actually contain RFE evidence.

    Before evidence is imported the bootstrap units remain useful for building the
    first Word skeleton. Once evidence exists, criterion episodes are derived from
    non-empty folders; the LLM manifest supplies strategy and RFE issues only.
    """
    manifest = load_strategy_manifest(case_dir)
    raw_units = [dict(unit) for unit in manifest.get("units", []) if isinstance(unit, dict)]
    roots = _new_evidence_roots(case_dir, config)
    if not any(_folder_has_meaningful_files(root) for root in roots if root.exists()):
        return raw_units

    criterion_templates: dict[str, list[dict[str, Any]]] = {}
    for unit in raw_units:
        role = str(unit.get("criterion_role", ""))
        if role:
            criterion_templates.setdefault(role, []).append(unit)

    generated: dict[str, list[dict[str, Any]]] = {}
    for role, templates in criterion_templates.items():
        generated[role] = _folder_driven_units(case_dir, config, role, templates)

    result: list[dict[str, Any]] = []
    emitted_roles: set[str] = set()
    for unit in raw_units:
        role = str(unit.get("criterion_role", ""))
        if not role:
            result.append(unit)
        elif role not in emitted_roles:
            result.extend(generated.get(role, []))
            emitted_roles.add(role)
    return result


def _folder_driven_units(
    case_dir: Path,
    config: dict[str, Any],
    role: str,
    templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    roots = _new_evidence_roots(case_dir, config)
    criterion_names = _criterion_folder_names(roots, config, role)
    if not criterion_names:
        return []
    criterion_name = criterion_names[0]
    episode_names: dict[str, str] = {}
    for root in roots:
        criterion_dir = root / criterion_name
        if not criterion_dir.exists():
            continue
        for child in sorted(criterion_dir.iterdir()):
            if child.is_dir() and _folder_has_meaningful_files(child):
                episode_names.setdefault(child.name.casefold(), child.name)
    if not episode_names:
        return []

    all_names = sorted(episode_names.values(), key=_natural_name_key)
    numbered = [name for name in all_names if re.match(r"^\s*\d+\s*[.)_-]?\s*\S", name)]
    # Unnumbered folders alongside numbered episodes are criterion-wide support
    # (for example a salary comparison or US-media comparison), not episodes.
    primary_names = numbered or all_names
    shared_names = [name for name in all_names if name not in primary_names]
    if role == "high_salary":
        primary_names = [criterion_name]
        shared_names = []

    units: list[dict[str, Any]] = []
    for episode_name in primary_names:
        source_folder = criterion_name if episode_name == criterion_name else f"{criterion_name}/{episode_name}"
        matched = _matching_strategy_templates(episode_name, templates)
        base = _merge_strategy_templates(templates, matched)
        title = _clean_episode_title(episode_name) if episode_name != criterion_name else str(base.get("section_title") or base.get("title") or role.replace("_", " ").title())
        shared_folders = [f"{criterion_name}/{name}" for name in shared_names]
        base.update(
            {
                "unit_id": safe_path_component(f"{role}_{_clean_episode_title(episode_name)}"),
                "title": title,
                "source_folder": source_folder,
                "shared_source_folders": shared_folders,
                "folder_driven": True,
            }
        )
        if role == "leading_critical_role":
            for phase, phase_title in (
                ("role", "Leading or Critical Role"),
                ("reputation", "Distinguished Reputation"),
            ):
                phased = dict(base)
                phased["unit_id"] = safe_path_component(f"{base['unit_id']}_{phase}")
                phased["title"] = f"{title} — {phase_title}"
                phased["phase"] = phase
                phased["strategy"] = (
                    str(base.get("strategy", "")).strip()
                    + f"\n\nThis unit is limited to the {phase_title.lower()} part of the criterion."
                ).strip()
                units.append(phased)
        else:
            units.append(base)
    for order, unit in enumerate(units, start=1):
        unit["order"] = order
    return units


def _new_evidence_roots(case_dir: Path, config: dict[str, Any]) -> list[Path]:
    paths = config.get("paths", {}) if isinstance(config.get("paths"), dict) else {}
    return [
        case_dir / str(paths.get("source_rfe_new_originals", "source_documents/rfe_response/new_documents/originals")),
        case_dir / str(paths.get("source_rfe_new_translations", "source_documents/rfe_response/new_documents/translations")),
    ]


def _criterion_folder_names(roots: list[Path], config: dict[str, Any], role: str) -> list[str]:
    names = [child.name for root in roots if root.exists() for child in root.iterdir() if child.is_dir()]
    role_map = config.get("eb1a_folder_roles", {}) if isinstance(config.get("eb1a_folder_roles"), dict) else {}
    configured = str(role_map.get(role, ""))
    exact = next((name for name in names if name == configured), "")
    if exact:
        return [exact]
    ordinal = CRITERION_FOLDER_ORDERS.get(role)
    if ordinal is not None:
        pattern = re.compile(rf"^\s*{ordinal}\s*[.)_-]")
        match = next((name for name in names if pattern.match(name)), "")
        if match:
            return [match]
    return []


def _folder_has_meaningful_files(path: Path) -> bool:
    return path.exists() and any(
        item.is_file()
        and item.name != ".gitkeep"
        and not is_office_temporary_file(item)
        for item in path.rglob("*")
    )


def _clean_episode_title(name: str) -> str:
    cleaned = re.sub(r"^\s*\d+\s*[.)_-]?\s*", "", name).strip()
    return cleaned or name.strip()


def _natural_name_key(name: str) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", name)
    )


def _strategy_words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", value.casefold()))


def _matching_strategy_templates(name: str, templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = _strategy_words(name)
    ranked = []
    for template in templates:
        haystack = " ".join(
            str(template.get(key, "")) for key in ("title", "source_folder", "unit_id")
        )
        score = len(words & _strategy_words(haystack))
        ranked.append((score, template))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [template for score, template in ranked if score > 0]


def _merge_strategy_templates(
    templates: list[dict[str, Any]], matched: list[dict[str, Any]]
) -> dict[str, Any]:
    selected = matched or [templates[0]]
    merged = dict(selected[0])
    if matched:
        strategy_values = [str(item.get("strategy", "")).strip() for item in matched]
    else:
        strategy_values = [
            str(issue.get("response_strategy", "")).strip()
            for item in templates
            for issue in item.get("rfe_issues", []) or []
            if isinstance(issue, dict)
        ]
    merged["strategy"] = "\n\n".join(dict.fromkeys(value for value in strategy_values if value))
    for key in ("rfe_issue_ids", "rfe_issues", "initial_filing_heading_hints"):
        values: list[Any] = []
        seen: set[str] = set()
        for item in templates:
            for value in item.get(key, []) or []:
                marker = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)
                if marker not in seen:
                    values.append(value)
                    seen.add(marker)
        merged[key] = values
    merged["planned_subheadings"] = (
        list(
            dict.fromkeys(
                str(value)
                for item in selected
                for value in item.get("planned_subheadings", []) or []
                if str(value).strip()
            )
        )
        if matched
        else []
    )
    merged["starter_text"] = str(selected[0].get("starter_text", ""))
    return merged


def render_strategy_unit_context(loaded: LoadedCase, unit_id: str) -> str:
    manifest = load_strategy_manifest(loaded.case_dir)
    unit = get_strategy_unit(loaded.case_dir, unit_id, loaded.config)
    if not unit:
        return f"[Strategy unit not found: {unit_id}]"
    parts = [
        "### Controlling global RFE strategy",
        "",
        _fenced(str(manifest.get("global_strategy", "")), "text"),
        "",
        "### Strategy for this drafting unit",
        "",
        f"- unit_id: `{unit_id}`",
        f"- section_type: `{unit.get('section_type', '')}`",
        f"- criterion_role: `{unit.get('criterion_role', '') or '[not criterion-specific]'}`",
        f"- source_folder: `{unit.get('source_folder', '') or '[not evidence-folder-specific]'}`",
        "",
        _fenced(str(unit.get("strategy", "")), "text"),
        "",
        "### RFE issues assigned to this unit",
        "",
    ]
    for issue in unit.get("rfe_issues", []):
        parts.extend(
            [
                f"#### {issue.get('issue_id', '')}: {issue.get('topic', '')}",
                f"- status: {issue.get('status', '')}",
                f"- defect: {issue.get('defect', '')}",
                f"- response_strategy: {issue.get('response_strategy', '')}",
                "",
                _fenced(str(issue.get("exact_rfe_quote", "")), "text"),
                "",
            ]
        )
    criterion = str(unit.get("criterion_role", ""))
    partition = loaded.case_dir / STRATEGY_ROOT / "initial_filing_sections" / f"{safe_path_component(criterion)}.txt" if criterion else None
    if partition and partition.exists():
        parts.extend(["### Relevant initial filing memorandum section", "", _fenced(partition.read_text(encoding="utf-8-sig")[:PROMPT_TEXT_LIMIT], "text"), ""])
    elif criterion:
        parts.extend(["### Relevant initial filing memorandum section", "", "[No criterion-specific partition was found. Review the partition report before final drafting.]", ""])

    source_folder = str(unit.get("source_folder", "")).strip("/\\")
    files: list[Path] = []
    roots = [
        ("New evidence originals", loaded.case_dir / "source_documents/rfe_response/new_documents/originals"),
        ("New evidence translations", loaded.case_dir / "source_documents/rfe_response/new_documents/translations"),
    ]
    index = read_document_index(loaded)
    from .workflow import render_evidence_files

    selected_by_label: list[tuple[str, list[Path]]] = []
    for label, root in roots:
        folders = [source_folder, *unit.get("shared_source_folders", [])]
        scoped: list[Path] = []
        for folder in dict.fromkeys(str(value).strip("/\\") for value in folders if str(value).strip("/\\")):
            selected = root / folder
            if selected.exists():
                scoped.extend(
                    path for path in sorted(selected.rglob("*"))
                    if path.is_file() and path.name != ".gitkeep" and not is_office_temporary_file(path)
                )
        scoped = _filter_phase_files(scoped, source_folder, str(unit.get("phase", "")))
        selected_by_label.append((label, list(dict.fromkeys(scoped))))

    parts.extend(["### Technical document selection for this unit", ""])
    parts.append(
        "Use only the exact `DOC####` identifiers below in `used_documents`. "
        "Never invent an ID for an RFE quotation, strategy statement, exhibit group, or explanatory concept."
    )
    technical_rows = _technical_document_rows(loaded, [path for _label, scoped in selected_by_label for path in scoped], index)
    if technical_rows:
        parts.extend(["", *[f"- `{row['document_id']}` — {row['title']} (`{row['file_path']}`)" for row in technical_rows]])
    else:
        parts.extend(["", "[No indexed evidence documents are assigned; `used_documents` must be an empty array.]"])
    parts.append("")

    for label, scoped in selected_by_label:
        parts.extend([f"### {label}", ""])
        if scoped:
            files.extend(scoped)
            parts.extend([render_evidence_files(loaded, scoped, index), ""])
        else:
            parts.extend([f"[No files found for mapped folder `{source_folder or '[none]'}`.]", ""])
    return "\n".join(parts).strip()


def selected_documents_for_unit(loaded: LoadedCase, unit_id: str) -> list[dict[str, str]]:
    unit = get_strategy_unit(loaded.case_dir, unit_id, loaded.config)
    if not unit:
        return []
    roots = _new_evidence_roots(loaded.case_dir, loaded.config)
    folders = [unit.get("source_folder", ""), *unit.get("shared_source_folders", [])]
    files: list[Path] = []
    for root in roots:
        for folder in dict.fromkeys(str(value).strip("/\\") for value in folders if str(value).strip("/\\")):
            selected = root / folder
            if selected.exists():
                files.extend(
                    path for path in selected.rglob("*")
                    if path.is_file() and path.name != ".gitkeep" and not is_office_temporary_file(path)
                )
    files = _filter_phase_files(files, str(unit.get("source_folder", "")), str(unit.get("phase", "")))
    return _technical_document_rows(loaded, files, read_document_index(loaded))


def _filter_phase_files(files: list[Path], source_folder: str, phase: str) -> list[Path]:
    if phase not in {"role", "reputation"}:
        return files
    terms = ("role", "роль") if phase == "role" else ("reputation", "репутац")
    source_parts = tuple(part.casefold() for part in Path(source_folder).parts)
    matched: list[Path] = []
    for path in files:
        parts = tuple(part.casefold() for part in path.parts)
        tail = parts
        for index in range(max(0, len(parts) - len(source_parts) + 1)):
            if parts[index : index + len(source_parts)] == source_parts:
                tail = parts[index + len(source_parts) :]
                break
        if any(term in "/".join(tail) for term in terms):
            matched.append(path)
    return matched or files


def _technical_document_rows(
    loaded: LoadedCase, files: list[Path], index: dict[str, list[dict[str, str]]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in sorted(set(files)):
        if is_prompt_sidecar(path):
            continue
        rel = path.relative_to(loaded.case_dir).as_posix()
        matches = index.get(rel, [])
        row = matches[0] if matches else {}
        document_id = str(row.get("document_id", ""))
        if not document_id or document_id in seen:
            continue
        rows.append(
            {
                "document_id": document_id,
                "title": str(row.get("display_title") or row.get("original_file_name") or path.stem),
                "file_path": rel,
            }
        )
        seen.add(document_id)
    return rows


def _validate_strategy_output(case_id: str, output: dict[str, Any]) -> None:
    if not isinstance(output, dict):
        raise ValueError("Strategy output must be one JSON object.")
    if output.get("case_id") != case_id:
        raise ValueError(f"case_id must be {case_id!r}.")
    if output.get("task_type") != "eb1a_rfe_response":
        raise ValueError("task_type must be 'eb1a_rfe_response'.")
    for key in ["case_metadata", "global_strategy", "rfe_issues", "sections", "template_decisions", "open_questions"]:
        if key not in output:
            raise ValueError(f"Missing required strategy field: {key}")
    metadata = output["case_metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("case_metadata must be an object.")
    for key in [
        "beneficiary_full_name", "preferred_reference", "field", "specialization",
        "case_number", "receipt_date", "rfe_date", "response_deadline", "uscis_address",
        "salutation",
    ]:
        if not str(metadata.get(key, "")).strip():
            raise ValueError(f"case_metadata.{key} is required.")
    for key in [
        "rfe_response_date", "uscis_office_or_service_center", "officer_name",
        "office_chief_name", "submitter_name", "submitter_title",
    ]:
        if key not in metadata:
            raise ValueError(f"case_metadata.{key} must be present (use an empty string if unknown).")
    if not isinstance(output["rfe_issues"], list):
        raise ValueError("rfe_issues must be an array.")
    issue_ids: set[str] = set()
    for issue in output["rfe_issues"]:
        if not isinstance(issue, dict):
            raise ValueError("Each rfe_issues item must be an object.")
        for key in ["issue_id", "topic", "issue_type", "status", "exact_rfe_quote", "defect", "response_strategy"]:
            if not str(issue.get(key, "")).strip():
                raise ValueError(f"Every RFE issue requires {key}.")
        issue_id = str(issue["issue_id"])
        if issue_id in issue_ids:
            raise ValueError(f"Duplicate RFE issue ID: {issue_id}")
        issue_ids.add(issue_id)
    if not isinstance(output["sections"], list) or not output["sections"]:
        raise ValueError("sections must contain at least one section.")
    section_ids: set[str] = set()
    orders: set[int] = set()
    for section in output["sections"]:
        if not isinstance(section, dict):
            raise ValueError("Each sections item must be an object.")
        section_id = str(section.get("section_id", "")).strip()
        if not section_id or section_id in section_ids:
            raise ValueError(f"Section IDs must be non-empty and unique: {section_id!r}")
        section_ids.add(section_id)
        try:
            order = int(section.get("order"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid section order for {section_id}.") from exc
        if order in orders:
            raise ValueError(f"Duplicate section order: {order}")
        orders.add(order)
        unknown = set(section.get("rfe_issue_ids", [])) - issue_ids
        if unknown:
            raise ValueError(f"Section {section_id} references unknown RFE issues: {sorted(unknown)}")
        episodes = section.get("episodes", [])
        if not isinstance(episodes, list):
            raise ValueError(f"Section {section_id}.episodes must be an array.")
        episode_ids: set[str] = set()
        for episode in episodes:
            if not isinstance(episode, dict):
                raise ValueError(f"Section {section_id} has a non-object episode.")
            episode_id = str(episode.get("episode_id", "")).strip()
            if not episode_id or episode_id in episode_ids:
                raise ValueError(
                    f"Section {section_id} episode IDs must be non-empty and unique: {episode_id!r}"
                )
            episode_ids.add(episode_id)
            episode_unknown = set(episode.get("rfe_issue_ids", [])) - issue_ids
            if episode_unknown:
                raise ValueError(
                    f"Episode {episode_id} references unknown RFE issues: {sorted(episode_unknown)}"
                )
    if not isinstance(output["template_decisions"], dict):
        raise ValueError("template_decisions must be an object.")
    if not isinstance(output["open_questions"], list):
        raise ValueError("open_questions must be an array.")


def _write_unit_files(case_dir: Path, manifest: dict[str, Any]) -> None:
    units_root = case_dir / STRATEGY_ROOT / "units"
    if units_root.exists():
        shutil.rmtree(units_root)
    for unit in manifest["units"]:
        root = units_root / str(unit["unit_id"])
        root.mkdir(parents=True, exist_ok=True)
        (root / "metadata.json").write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "strategy.md").write_text(
            f"# {unit['title']}\n\n{unit.get('strategy', '')}\n", encoding="utf-8"
        )
        quotes = "\n\n".join(
            f"## {item.get('issue_id', '')}: {item.get('topic', '')}\n\n{item.get('exact_rfe_quote', '')}"
            for item in unit.get("rfe_issues", [])
        )
        (root / "rfe_issues.md").write_text(quotes + ("\n" if quotes else ""), encoding="utf-8")


def _update_case_config(case_dir: Path, manifest: dict[str, Any]) -> None:
    from .memo_builder import _write_yaml_file
    from .workflow import load_yaml_file

    config_path = case_dir / "case_config.yaml"
    config = load_yaml_file(config_path)
    meta = manifest["case_metadata"]
    beneficiary = config.setdefault("beneficiary", {})
    beneficiary["full_name"] = meta["beneficiary_full_name"]
    beneficiary["preferred_reference"] = meta["preferred_reference"]
    config["field"] = meta["field"]
    config["specialization"] = meta["specialization"]
    config["procedural_context"] = "EB-1A Request for Evidence response"
    config["drafting_objective"] = "Prepare a strategy-controlled EB-1A RFE response"
    rfe_metadata = config.setdefault("rfe_metadata", {})
    for key in [
        "case_number", "receipt_date", "rfe_date", "response_deadline", "uscis_address",
        "petition_type", "rfe_response_date", "uscis_office_or_service_center",
        "officer_name", "office_chief_name", "salutation", "submitter_name", "submitter_title",
    ]:
        if meta.get(key):
            rfe_metadata[key] = meta[key]
    paths = config.setdefault("paths", {})
    paths.update(
        {
            "source_rfe_notice": "source_documents/rfe/notice",
            "source_rfe_strategy": "source_documents/rfe/strategy",
            "source_initial_filing_memo": "source_documents/initial_filing/memorandum",
            "source_rfe_new_originals": "source_documents/rfe_response/new_documents/originals",
            "source_rfe_new_translations": "source_documents/rfe_response/new_documents/translations",
            "rfe_strategy_root": STRATEGY_ROOT,
        }
    )
    config["claimed_criteria"] = list(
        dict.fromkeys(
            [
                *manifest.get("accepted_criteria", []),
                *manifest.get("challenged_criteria", []),
                *[unit.get("criterion_role", "") for unit in manifest["units"] if unit.get("criterion_role")],
            ]
        )
    )
    response = config.setdefault("rfe_response", {})
    response["strategy_manifest"] = f"{STRATEGY_ROOT}/{MANIFEST_NAME}"
    response["template_file"] = "templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.yaml"
    response["human_template_file"] = "templates/RFE/EB1/rfe draft template.docx"
    response["attachment_label"] = manifest.get("template_decisions", {}).get("attachment_label", "Attachment")
    config["rfe_enabled_issues"] = [unit["unit_id"] for unit in manifest["units"]]
    _write_yaml_file(config_path, config)


def _render_plan(manifest: dict[str, Any]) -> str:
    lines = ["# RFE response plan", "", "Generated from the accepted strategy bootstrap JSON.", "", "## Structure rationale", "", str(manifest.get("template_decisions", {}).get("structure_rationale", "")), "", "## Drafting units", ""]
    for unit in manifest["units"]:
        lines.extend(
            [
                f"{unit['order']}. **{unit['title']}** (`{unit['unit_id']}`)",
                f"   - type: `{unit['section_type']}`",
                f"   - criterion: `{unit.get('criterion_role') or 'n/a'}`",
                f"   - evidence folder: `{unit.get('source_folder') or 'n/a'}`",
                f"   - RFE issues: {', '.join(unit.get('rfe_issue_ids', [])) or 'none'}",
            ]
        )
    lines.extend(["", "## Open questions", ""])
    lines.extend(f"- {item}" for item in manifest.get("open_questions", []))
    return "\n".join(lines).rstrip() + "\n"


def _split_by_criterion(text: str, hints: dict[str, list[str]]) -> dict[str, str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\r?\n", text) if part.strip()]
    starts: list[tuple[int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        normalized = re.sub(r"\s+", " ", paragraph).casefold()
        heading_like = len(normalized) <= 320 or normalized.startswith(("criterion", "documentation", "evidence of"))
        if not heading_like:
            continue
        matches = [role for role, aliases in hints.items() if any(alias.casefold() in normalized for alias in aliases if alias)]
        if len(matches) == 1 and (not starts or starts[-1][1] != matches[0]):
            starts.append((index, matches[0]))
    result: dict[str, str] = {}
    for position, (start, role) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(paragraphs)
        block = "\n\n".join(paragraphs[start:end]).strip()
        if len(block) > len(result.get(role, "")):
            result[role] = block
    return result


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            return "\n\n".join((page.extract_text() or "").strip() for page in PdfReader(str(path)).pages).strip()
        except Exception:
            try:
                import pdfplumber  # type: ignore

                with pdfplumber.open(path) as pdf:
                    return "\n\n".join((page.extract_text() or "").strip() for page in pdf.pages).strip()
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Could not extract PDF text from {path}: {exc}") from exc
    text = read_textual_file(path, 500_000)
    if text.startswith("[Unsupported source file type"):
        raise ValueError(f"Unsupported text source: {path}")
    return text


def _required_source_file(value: str, label: str) -> Path:
    path = _required_source(value, label)
    if not path.is_file():
        raise ValueError(f"{label} must point to one file: {path}")
    return path


def _required_source(value: str, label: str) -> Path:
    cleaned = str(value).strip().strip('"').strip("'")
    if not cleaned:
        raise ValueError(f"{label} path is required.")
    path = Path(cleaned).expanduser()
    if not path.exists():
        raise ValueError(f"{label} path does not exist: {path}")
    return path.resolve()


def _copy_source_file(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def _copy_any(source: Path, destination: Path) -> tuple[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        target = destination / source.name
        if target.exists() and filecmp.cmp(source, target, shallow=False):
            return 0, 1
        shutil.copy2(source, target)
        return 1, 0
    copied = skipped = 0
    for item in sorted(source.rglob("*")):
        if not item.is_file() or is_office_temporary_file(item):
            continue
        target = destination / item.relative_to(source)
        if target.exists() and filecmp.cmp(item, target, shallow=False):
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied += 1
    return copied, skipped


def _copy_bilingual_tree(source: Path, destination: Path) -> tuple[int, int]:
    originals = source / "originals"
    translations = source / "translations"
    if originals.is_dir() or translations.is_dir():
        copied = skipped = 0
        for name, child in (("originals", originals), ("translations", translations)):
            if child.is_dir():
                c, s = _copy_any(child, destination / name)
                copied += c
                skipped += s
        return copied, skipped
    return _copy_any(source, destination / "originals")


def _remember_source_paths(case_dir: Path, updates: dict[str, Path]) -> None:
    from .memo_builder import _write_yaml_file
    from .workflow import load_yaml_file

    config_path = case_dir / "case_config.yaml"
    config = load_yaml_file(config_path)
    imports = config.setdefault("source_imports", {})
    imports.pop("initial_filing_documents", None)
    for key, value in updates.items():
        imports[key] = str(value)
    paths = config.get("paths", {})
    if isinstance(paths, dict):
        paths.pop("source_initial_filing_originals", None)
        paths.pop("source_initial_filing_translations", None)
    _write_yaml_file(config_path, config)


def _fenced(text: str, language: str = "") -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{language}\n{text}\n{fence}"
