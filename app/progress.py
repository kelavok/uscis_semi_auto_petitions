from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workflow import load_case


@dataclass(frozen=True)
class ProgressStep:
    key: str
    label: str
    detail: str
    complete: bool
    current: bool = False


@dataclass(frozen=True)
class CaseProgress:
    case_id: str
    beneficiary_name: str
    task_type: str
    stage_label: str
    completion_percent: int
    steps: list[ProgressStep]
    indexed_documents: int
    linked_translations: int
    total_translations: int


def build_case_progress(case_id: str) -> CaseProgress:
    loaded = load_case(case_id)
    config = loaded.config
    beneficiary = config.get("beneficiary", {}) if isinstance(config.get("beneficiary"), dict) else {}
    beneficiary_name = _clean_value(beneficiary.get("full_name")) or case_id
    task_type = str(config.get("task_type", ""))

    intake_values = [
        beneficiary.get("full_name"),
        beneficiary.get("preferred_reference"),
        config.get("field"),
        config.get("specialization"),
    ]
    intake_complete = all(_clean_value(value) for value in intake_values)
    if task_type == "eb1a_petition":
        intake_complete = intake_complete and bool(config.get("claimed_criteria"))
    elif task_type == "eb1a_rfe_response":
        manifest = loaded.case_dir / "case_strategy" / "strategy_manifest.json"
        intake_complete = manifest.exists() and manifest.stat().st_size > 0

    working_memo = loaded.case_dir / _configured_path(config, "final_memo", "final_memo") / "working_memo.docx"
    working_complete = working_memo.exists() and working_memo.stat().st_size > 0

    index_path = loaded.case_dir / _configured_path(config, "document_index", "indexes/document_index.csv")
    rows = _read_csv(index_path)
    indexed_documents = len(rows)
    scan_complete = indexed_documents > 0
    translations = [row for row in rows if row.get("translation_status") == "translation"]
    linked_translations = sum(bool(row.get("parent_document_id")) for row in translations)
    total_translations = len(translations)
    translation_complete = total_translations == 0 or linked_translations == total_translations

    draft_root = loaded.case_dir / _configured_path(config, "draft_sections", "draft_sections")
    draft_files = _meaningful_files(draft_root, {".md", ".txt"})
    final_overview = any("final_overview" in path.name for path in draft_files)
    if task_type == "eb1a_rfe_response":
        try:
            import json

            manifest_data = json.loads(
                (loaded.case_dir / "case_strategy/strategy_manifest.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            expected = len(manifest_data.get("units", []))
        except (OSError, ValueError, TypeError):
            expected = 0
        rfe_drafts = [path for path in draft_files if "draft_sections\\rfe\\sections" in str(path) or "/draft_sections/rfe/sections/" in path.as_posix()]
        drafting_complete = expected > 0 and len(rfe_drafts) >= expected
    else:
        drafting_complete = bool(draft_files) and final_overview

    exhibit_path = loaded.case_dir / _configured_path(config, "exhibit_index", "indexes/exhibit_index.csv")
    exhibit_rows = _read_csv(exhibit_path)
    exhibits_complete = bool(exhibit_rows)

    bundle_root = loaded.case_dir / _configured_path(config, "bundle_root", "bundle")
    final_root = bundle_root / "final"
    final_bundle = final_root / "evidence_bundle.pdf"
    bundle_pdfs = [final_bundle] if final_bundle.exists() and final_bundle.is_file() else []
    bundle_complete = bool(bundle_pdfs)

    raw_steps = [
        ("intake", "Case intake", "Basic case information and claimed criteria", intake_complete),
        ("working_memo", "Working memorandum", "First page, cover letter, and controlled section skeleton", working_complete),
        ("scan", "Document scan", f"{indexed_documents} indexed document(s)", scan_complete),
        (
            "translations",
            "Translation review",
            f"{linked_translations}/{total_translations} translation(s) linked" if total_translations else "No translations indexed",
            translation_complete,
        ),
        ("drafting", "LLM drafting", f"{len(draft_files)} drafted section file(s)", drafting_complete),
        ("exhibits", "Exhibit index and separators", f"{len(exhibit_rows)} exhibit row(s)", exhibits_complete),
        ("bundle", "Final PDF bundle", f"{len(bundle_pdfs)} PDF bundle file(s)", bundle_complete),
    ]
    current_assigned = False
    steps: list[ProgressStep] = []
    for key, label, detail, complete in raw_steps:
        current = not complete and not current_assigned
        if current:
            current_assigned = True
        steps.append(ProgressStep(key=key, label=label, detail=detail, complete=complete, current=current))
    completed_count = sum(step.complete for step in steps)
    completion_percent = round((completed_count / len(steps)) * 100)
    current_step = next((step for step in steps if step.current), None)
    stage_label = current_step.label if current_step else "Complete"
    return CaseProgress(
        case_id=case_id,
        beneficiary_name=beneficiary_name,
        task_type=task_type,
        stage_label=stage_label,
        completion_percent=completion_percent,
        steps=steps,
        indexed_documents=indexed_documents,
        linked_translations=linked_translations,
        total_translations=total_translations,
    )


def _configured_path(config: dict[str, Any], key: str, default: str) -> Path:
    paths = config.get("paths", {})
    if isinstance(paths, dict) and paths.get(key):
        return Path(str(paths[key]))
    return Path(default)


def _clean_value(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if not text or text.startswith("__") else text


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: value or "" for key, value in row.items() if key} for row in csv.DictReader(handle)]


def _meaningful_files(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in suffixes
    ]
