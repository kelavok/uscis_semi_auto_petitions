from __future__ import annotations

import csv
import hashlib
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath

from .workflow import (
    LoadedCase,
    _case_path_value,
    _normalize_slashes,
    extract_docx_text,
    load_case,
)
from .file_rules import is_office_temporary_file, is_prompt_sidecar


INDEX_FIELDS = [
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
]

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic"}
MANUAL_DESCRIPTION_PLACEHOLDER = "[Write factual manual description here. Replace this line.]"
PDF_MAX_PAGES = 20
PDF_MAX_CHARACTERS = 200_000


@dataclass(frozen=True)
class ScanSummary:
    index_path: Path
    scanned_files: int
    added_rows: int
    updated_rows: int
    locked_rows_skipped: int
    extracted_texts: int
    non_text_files: int
    manual_description_files: int


@dataclass(frozen=True)
class LinkSummary:
    index_path: Path
    translations_seen: int
    linked_translations: int
    already_linked: int
    ambiguous_translations: int
    unmatched_translations: int
    locked_rows_skipped: int
    report_path: Path


@dataclass(frozen=True)
class TranslationMatchDecision:
    candidate: dict[str, str] | None
    method: str
    score: float
    alternatives: list[tuple[dict[str, str], float]]


@dataclass(frozen=True)
class ManualTranslationLinkSummary:
    index_path: Path
    translation_document_id: str
    original_document_id: str
    translation_file_path: str
    original_file_path: str
    previous_original_document_id: str
    displaced_translation_ids: tuple[str, ...]


def scan_documents(case_id: str) -> ScanSummary:
    loaded = load_case(case_id)
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    rows = _read_index(index_path)
    by_path = {_normalize_slashes(row.get("file_path", "")): row for row in rows if row.get("file_path")}
    next_number = _next_document_number(rows)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    scanned_files = 0
    added_rows = 0
    updated_rows = 0
    locked_rows_skipped = 0
    extracted_texts = 0
    non_text_files = 0
    manual_description_files = 0

    for file_path, source_kind in _iter_source_files(loaded):
        scanned_files += 1
        rel_path = _normalize_slashes(file_path.relative_to(loaded.case_dir).as_posix())
        existing = by_path.get(rel_path)
        if existing and _truthy(existing.get("manual_edit_lock", "")):
            locked_rows_skipped += 1
            continue

        if existing:
            row = existing
            doc_id = row.get("document_id") or f"DOC{next_number:04d}"
            if not row.get("document_id"):
                next_number += 1
            updated_rows += 1
        else:
            doc_id = f"DOC{next_number:04d}"
            next_number += 1
            row = _blank_row()
            row["document_id"] = doc_id
            row["display_title"] = file_path.stem
            row["user_approval_status"] = "pending"
            row["separator_title_type"] = "document"
            row["manual_edit_lock"] = "false"
            rows.append(row)
            by_path[rel_path] = row
            added_rows += 1

        fingerprint = _fingerprint(file_path)
        extraction = _reusable_extraction(loaded, row, doc_id, fingerprint) or _extract_text(
            file_path, loaded, doc_id
        )
        if extraction.status in {"text_extracted", "manual_description_available"}:
            extracted_texts += 1
        elif extraction.status in {"image_or_photo", "unsupported_binary", "pdf_no_extractable_text"}:
            non_text_files += 1
        if extraction.manual_description_path:
            manual_description_files += 1

        row["document_id"] = doc_id
        row["original_file_name"] = file_path.name
        row["file_path"] = rel_path
        row["document_type"] = _document_type(file_path)
        row["category"] = row.get("category") or _infer_category(loaded, file_path, source_kind)
        row["translation_status"] = row.get("translation_status") or source_kind
        row["extraction_status"] = extraction.status
        row["text_extraction_path"] = extraction.relative_text_path
        row["source_fingerprint"] = fingerprint
        row["last_scanned_at"] = now
        row["notes"] = _merge_notes(row.get("notes", ""), extraction.note)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    _write_index(index_path, rows)
    return ScanSummary(
        index_path=index_path,
        scanned_files=scanned_files,
        added_rows=added_rows,
        updated_rows=updated_rows,
        locked_rows_skipped=locked_rows_skipped,
        extracted_texts=extracted_texts,
        non_text_files=non_text_files,
        manual_description_files=manual_description_files,
    )


def link_translations(case_id: str, *, auto_match: bool = True) -> LinkSummary:
    loaded = load_case(case_id)
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    rows = _read_index(index_path)
    originals = [row for row in rows if row.get("translation_status") == "original"]
    translations = [row for row in rows if row.get("translation_status") == "translation"]

    linked_translations = 0
    already_linked = 0
    ambiguous_translations = 0
    unmatched_translations = 0
    locked_rows_skipped = 0
    used_original_ids = {
        row.get("parent_document_id", "")
        for row in translations
        if row.get("parent_document_id", "")
    }
    report_rows: list[dict[str, str]] = []

    for translation in translations:
        if _truthy(translation.get("manual_edit_lock", "")):
            locked_rows_skipped += 1
            report_rows.append(_translation_report_row(translation, "locked", "", 0.0, []))
            continue
        if translation.get("parent_document_id"):
            already_linked += 1
            report_rows.append(
                _translation_report_row(
                    translation,
                    "already_linked",
                    "existing_parent_document_id",
                    1.0,
                    [],
                )
            )
            continue

        available_originals = [
            original for original in originals if original.get("document_id", "") not in used_original_ids
        ]
        decision = _translation_match_decision(translation, available_originals)
        if decision.candidate is not None and auto_match:
            original = decision.candidate
            translation["parent_document_id"] = original.get("document_id", "")
            translation["relationship_type"] = "translation"
            translation["translation_status"] = "translation"
            translation["notes"] = _merge_notes(
                translation.get("notes", ""),
                f"Linked as translation of {original.get('document_id', '')} by {decision.method} "
                f"(confidence {decision.score:.3f}). Bundle order: original_then_translation.",
            )
            if not _truthy(original.get("manual_edit_lock", "")):
                original["translation_status"] = original.get("translation_status") or "original"
                original["relationship_type"] = original.get("relationship_type") or "original"
                original["notes"] = _merge_notes(
                    original.get("notes", ""),
                    f"Has linked translation {translation.get('document_id', '')}. Bundle order: original_then_translation.",
                )
            linked_translations += 1
            used_original_ids.add(original.get("document_id", ""))
            report_rows.append(
                _translation_report_row(
                    translation,
                    "linked",
                    decision.method,
                    decision.score,
                    [(original, decision.score)],
                )
            )
        elif decision.candidate is not None:
            ambiguous_translations += 1
            review_alternatives = [(decision.candidate, decision.score)] + [
                item
                for item in decision.alternatives
                if item[0].get("document_id", "") != decision.candidate.get("document_id", "")
            ]
            report_rows.append(
                _translation_report_row(
                    translation,
                    "ambiguous",
                    decision.method,
                    decision.score,
                    review_alternatives,
                )
            )
        elif len(decision.alternatives) > 1 and decision.alternatives[0][1] >= 0.60:
            ambiguous_translations += 1
            translation["notes"] = _merge_notes(
                translation.get("notes", ""),
                "Translation link ambiguous. Set parent_document_id manually.",
            )
            report_rows.append(
                _translation_report_row(
                    translation,
                    "ambiguous",
                    decision.method,
                    decision.score,
                    decision.alternatives,
                )
            )
        else:
            unmatched_translations += 1
            translation["notes"] = _merge_notes(
                translation.get("notes", ""),
                "No matching original found. Set parent_document_id manually if applicable.",
            )
            report_rows.append(
                _translation_report_row(
                    translation,
                    "unmatched",
                    decision.method,
                    decision.score,
                    decision.alternatives,
                )
            )

    _write_index(index_path, rows)
    configured_paths = loaded.config.get("paths", {})
    reports_value = configured_paths.get("reports", "reports") if isinstance(configured_paths, dict) else "reports"
    report_path = loaded.case_dir / str(reports_value) / "translation_link_report.csv"
    _write_translation_report(report_path, report_rows)
    return LinkSummary(
        index_path=index_path,
        translations_seen=len(translations),
        linked_translations=linked_translations,
        already_linked=already_linked,
        ambiguous_translations=ambiguous_translations,
        unmatched_translations=unmatched_translations,
        locked_rows_skipped=locked_rows_skipped,
        report_path=report_path,
    )


def manual_link_translation(
    case_id: str,
    translation_reference: str,
    original_reference: str,
    *,
    allow_shared_original: bool = False,
) -> ManualTranslationLinkSummary:
    loaded = load_case(case_id)
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    rows = _read_index(index_path)
    translation = _find_index_row(
        rows,
        translation_reference,
        loaded.case_dir,
        expected_status="translation",
    )
    original = _find_index_row(
        rows,
        original_reference,
        loaded.case_dir,
        expected_status="original",
    )
    translation_id = translation.get("document_id", "")
    original_id = original.get("document_id", "")
    existing_parent = translation.get("parent_document_id", "")
    previous_original_id = existing_parent if existing_parent and existing_parent != original_id else ""
    if previous_original_id:
        translation["notes"] = _merge_notes(
            translation.get("notes", ""),
            f"Manual link moved from {previous_original_id} to {original_id}.",
        )
        previous_original = next(
            (row for row in rows if row.get("document_id", "") == previous_original_id),
            None,
        )
        if previous_original is not None:
            previous_original["notes"] = _merge_notes(
                previous_original.get("notes", ""),
                f"Translation {translation_id} was manually reassigned to {original_id}.",
            )

    used_rows = [
        row
        for row in rows
        if row is not translation and row.get("parent_document_id", "") == original_id
    ]
    displaced_ids: list[str] = []
    if not allow_shared_original:
        for displaced in used_rows:
            displaced_id = displaced.get("document_id", "")
            displaced["parent_document_id"] = ""
            displaced["relationship_type"] = ""
            displaced["notes"] = _merge_notes(
                displaced.get("notes", ""),
                f"Link to {original_id} was displaced by manual reassignment to {translation_id}; manual review required.",
            )
            if displaced_id:
                displaced_ids.append(displaced_id)

    translation["parent_document_id"] = original_id
    translation["relationship_type"] = "translation"
    translation["translation_status"] = "translation"
    translation["notes"] = _merge_notes(
        translation.get("notes", ""),
        f"Manually confirmed as translation of {original_id}. Bundle order: original_then_translation.",
    )
    original["relationship_type"] = original.get("relationship_type") or "original"
    original["translation_status"] = original.get("translation_status") or "original"
    original["notes"] = _merge_notes(
        original.get("notes", ""),
        (
            f"Manually assigned translation {translation_id}; displaced {', '.join(displaced_ids)}. "
            "Bundle order: original_then_translation."
            if displaced_ids
            else f"Has manually confirmed translation {translation_id}. Bundle order: original_then_translation."
        ),
    )
    _write_index(index_path, rows)
    return ManualTranslationLinkSummary(
        index_path=index_path,
        translation_document_id=translation_id,
        original_document_id=original_id,
        translation_file_path=translation.get("file_path", ""),
        original_file_path=original.get("file_path", ""),
        previous_original_document_id=previous_original_id,
        displaced_translation_ids=tuple(displaced_ids),
    )


def unlink_translation(case_id: str, translation_reference: str) -> Path:
    loaded = load_case(case_id)
    index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    rows = _read_index(index_path)
    translation = _find_index_row(
        rows,
        translation_reference,
        loaded.case_dir,
        expected_status="translation",
    )
    previous_parent = translation.get("parent_document_id", "")
    translation["parent_document_id"] = ""
    translation["relationship_type"] = ""
    translation["notes"] = _merge_notes(
        translation.get("notes", ""),
        f"Manual link to {previous_parent or '[none]'} was removed.",
    )
    _write_index(index_path, rows)
    return index_path


def _find_index_row(
    rows: list[dict[str, str]],
    reference: str,
    case_dir: Path,
    *,
    expected_status: str,
) -> dict[str, str]:
    value = _strip_wrapping_quotes(reference.strip())
    if not value:
        raise ValueError(f"Missing {expected_status} document reference.")
    normalized_reference = _normalize_slashes(value).casefold()
    try:
        path = Path(value)
        if path.is_absolute():
            resolved = path.resolve()
            case_resolved = case_dir.resolve()
            if resolved != case_resolved and case_resolved not in resolved.parents:
                raise ValueError("Selected file is outside the case workspace.")
            normalized_reference = _normalize_slashes(resolved.relative_to(case_resolved).as_posix()).casefold()
    except OSError:
        pass
    matches = [
        row
        for row in rows
        if row.get("translation_status", "") == expected_status
        and (
            row.get("document_id", "").casefold() == normalized_reference
            or _normalize_slashes(row.get("file_path", "")).casefold() == normalized_reference
        )
    ]
    if not matches:
        raise ValueError(f"No indexed {expected_status} document found for: {reference}")
    if len(matches) > 1:
        raise ValueError(f"Reference is ambiguous: {reference}")
    return matches[0]


def _strip_wrapping_quotes(value: str) -> str:
    quote_pairs = {('"', '"'), ("'", "'"), ("“", "”"), ("«", "»")}
    while len(value) >= 2 and (value[0], value[-1]) in quote_pairs:
        value = value[1:-1].strip()
    return value


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    relative_text_path: str
    note: str
    manual_description_path: str = ""


def _reusable_extraction(
    loaded: LoadedCase,
    row: dict[str, str],
    doc_id: str,
    fingerprint: str,
) -> ExtractionResult | None:
    if row.get("source_fingerprint", "") != fingerprint:
        return None
    configured_path = row.get("text_extraction_path", "")
    if configured_path:
        existing = loaded.case_dir / configured_path
        if existing.exists() and existing.stat().st_size > 1:
            return ExtractionResult(
                status=row.get("extraction_status", "") or "text_extracted",
                relative_text_path=configured_path,
                note="Reused unchanged extracted text.",
            )
    # An interrupted scan can leave a valid deterministic extraction file
    # before document_index.csv is committed. Reuse it on the next run.
    deterministic = loaded.case_dir / _case_path_value(loaded.config, "extracted_text") / f"{doc_id}.txt"
    if deterministic.exists() and deterministic.stat().st_size > 1:
        return ExtractionResult(
            status="text_extracted",
            relative_text_path=_normalize_slashes(deterministic.relative_to(loaded.case_dir).as_posix()),
            note="Recovered extracted text from an interrupted earlier scan.",
        )
    return None


def _extract_text(file_path: Path, loaded: LoadedCase, doc_id: str) -> ExtractionResult:
    suffix = file_path.suffix.lower()
    text = ""
    status = ""
    note = ""

    if suffix in TEXT_EXTENSIONS:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        status = "text_extracted"
    elif suffix in DOCX_EXTENSIONS:
        try:
            text = extract_docx_text(file_path)
            status = "text_extracted" if text.strip() else "docx_no_extractable_text"
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            text = ""
            status = "docx_invalid_or_corrupt"
            note = (
                "The file has a .docx extension but is not a readable Word ZIP package. "
                f"Scanner continued without text extraction: {exc}"
            )
    elif suffix in PDF_EXTENSIONS:
        text, status, note = _extract_pdf_text(file_path)
    elif suffix in IMAGE_EXTENSIONS:
        status = "image_or_photo"
        note = "Image/photo file. Add manual description or readable translation if needed."
    else:
        status = "unsupported_binary"
        note = "Unsupported file type for text extraction. Listed for indexing/bundle only."

    if not text.strip():
        manual_description = _manual_description_for(loaded, doc_id, file_path)
        if manual_description.ready_text:
            return ExtractionResult(
                status="manual_description_available",
                relative_text_path=manual_description.relative_path,
                note=_merge_notes(note, "Using user-provided manual description for LLM context."),
                manual_description_path=manual_description.relative_path,
            )
        return ExtractionResult(
            status=status,
            relative_text_path="",
            note=_merge_notes(note, f"Manual description placeholder: {manual_description.relative_path}"),
            manual_description_path=manual_description.relative_path,
        )

    extracted_root = loaded.case_dir / _case_path_value(loaded.config, "extracted_text")
    extracted_root.mkdir(parents=True, exist_ok=True)
    text_path = extracted_root / f"{doc_id}.txt"
    text_path.write_text(text.strip() + "\n", encoding="utf-8")
    rel_text_path = _normalize_slashes(text_path.relative_to(loaded.case_dir).as_posix())
    return ExtractionResult(status=status, relative_text_path=rel_text_path, note=note)


@dataclass(frozen=True)
class ManualDescription:
    path: Path
    relative_path: str
    ready_text: str


def _manual_description_for(loaded: LoadedCase, doc_id: str, source_file: Path) -> ManualDescription:
    root = loaded.case_dir / _manual_descriptions_path(loaded)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{doc_id}.md"
    relative_path = _normalize_slashes(path.relative_to(loaded.case_dir).as_posix())
    if not path.exists():
        path.write_text(_manual_description_template(doc_id, source_file), encoding="utf-8")
        return ManualDescription(path=path, relative_path=relative_path, ready_text="")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if _manual_description_is_ready(text):
        return ManualDescription(path=path, relative_path=relative_path, ready_text=text.strip())
    return ManualDescription(path=path, relative_path=relative_path, ready_text="")


def _manual_descriptions_path(loaded: LoadedCase) -> Path:
    paths = loaded.config.get("paths", {})
    if isinstance(paths, dict) and paths.get("manual_descriptions"):
        return Path(str(paths["manual_descriptions"]))
    return Path("manual_descriptions")


def _manual_description_template(doc_id: str, source_file: Path) -> str:
    return (
        f"# Manual description for {doc_id}\n\n"
        f"Source file: `{source_file.name}`\n\n"
        "Use this file when the source document is a photo, scanned PDF, image-only PDF, "
        "or otherwise not machine-readable.\n\n"
        "Do not speculate. Describe only what you can verify from the document or from a "
        "known translation. If there is a readable translation, prefer indexing that "
        "translation as a separate document.\n\n"
        "## Description for LLM\n\n"
        f"{MANUAL_DESCRIPTION_PLACEHOLDER}\n\n"
        "## Suggested citation/display title\n\n"
        "[Optional]\n\n"
        "## Notes for index/exhibit handling\n\n"
        "[Optional]\n"
    )


def _manual_description_is_ready(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if MANUAL_DESCRIPTION_PLACEHOLDER in stripped:
        return False
    meaningful_lines = [
        line.strip()
        for line in stripped.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("[Optional]")
        and not line.strip().startswith("Source file:")
        and not line.strip().startswith("Use this file")
        and not line.strip().startswith("Do not speculate")
    ]
    return bool(meaningful_lines)


def _extract_pdf_text(file_path: Path) -> tuple[str, str, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError:
        PdfReader = None  # type: ignore

    if PdfReader is not None:
        try:
            logging.getLogger("pypdf").setLevel(logging.ERROR)
            reader = PdfReader(str(file_path))
            pages = []
            total_characters = 0
            for page_number, page in enumerate(reader.pages):
                if page_number >= PDF_MAX_PAGES or total_characters >= PDF_MAX_CHARACTERS:
                    break
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    pages.append(page_text)
                    total_characters += len(page_text)
            text = "\n\n".join(page for page in pages if page)
            if text.strip():
                truncated = len(reader.pages) > PDF_MAX_PAGES or len(text) >= PDF_MAX_CHARACTERS
                note = f"PDF extraction limited to first {PDF_MAX_PAGES} pages / {PDF_MAX_CHARACTERS} characters." if truncated else ""
                return text[:PDF_MAX_CHARACTERS], "text_extracted", note
            return "", "pdf_no_extractable_text", "PDF appears scanned or image-only; OCR/manual description needed."
        except Exception as exc:  # noqa: BLE001
            pypdf_error = exc
    else:
        pypdf_error = None

    try:
        import pdfplumber  # type: ignore
    except ModuleNotFoundError:
        return (
            "",
            "pdf_text_dependency_missing",
            "Install pdfplumber or pypdf to extract text from readable PDFs.",
        )

    try:
        with pdfplumber.open(file_path) as pdf:
            pages = [(page.extract_text() or "").strip() for page in pdf.pages[:PDF_MAX_PAGES]]
        text = "\n\n".join(page for page in pages if page)
        if text.strip():
            truncated = len(pdf.pages) > PDF_MAX_PAGES or len(text) >= PDF_MAX_CHARACTERS
            note = f"PDF extraction limited to first {PDF_MAX_PAGES} pages / {PDF_MAX_CHARACTERS} characters." if truncated else ""
            return text[:PDF_MAX_CHARACTERS], "text_extracted", note
        return "", "pdf_no_extractable_text", "PDF appears scanned or image-only; OCR/manual description needed."
    except Exception as exc:  # noqa: BLE001
        note = f"pypdf failed: {pypdf_error}; " if pypdf_error else ""
        return "", "pdf_extraction_error", note + f"pdfplumber failed: {exc}"


def _iter_source_files(loaded: LoadedCase) -> list[tuple[Path, str]]:
    configured = _configured_source_paths(loaded)
    files: list[tuple[Path, str]] = []
    for key, source_kind in configured:
        root = loaded.case_dir / _case_path_value(loaded.config, key)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and path.name != ".gitkeep"
                and not is_prompt_sidecar(path)
                and not is_office_temporary_file(path)
            ):
                files.append((path, source_kind))
    return files


def _configured_source_paths(loaded: LoadedCase) -> list[tuple[str, str]]:
    if str(loaded.config.get("task_type", "")) == "eb1a_rfe_response":
        rfe_paths = [
            ("source_rfe_new_originals", "original"),
            ("source_rfe_new_translations", "translation"),
            ("source_initial_filing_memo", "initial_filing_memo"),
            ("source_rfe_notice", "rfe_notice"),
            ("source_rfe_strategy", "rfe_strategy"),
        ]
        paths = loaded.config.get("paths", {})
        if isinstance(paths, dict):
            return [(key, kind) for key, kind in rfe_paths if key in paths]
    defaults = [
        ("source_originals", "original"),
        ("source_translations", "translation"),
        ("source_other", "other"),
    ]
    paths = loaded.config.get("paths", {})
    if not isinstance(paths, dict):
        return defaults
    configured: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, source_kind in defaults:
        if key in paths:
            configured.append((key, source_kind))
            seen.add(key)
    for key in sorted(str(path_key) for path_key in paths if str(path_key).startswith("source_")):
        if key in seen:
            continue
        configured.append((key, key.removeprefix("source_")))
        seen.add(key)
    return configured


def _read_index(index_path: Path) -> list[dict[str, str]]:
    if not index_path.exists():
        return []
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalized = _blank_row()
            normalized.update({key: value or "" for key, value in row.items() if key})
            rows.append(normalized)
        return rows


def _write_index(index_path: Path, rows: list[dict[str, str]]) -> None:
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in INDEX_FIELDS})


def _blank_row() -> dict[str, str]:
    return {field: "" for field in INDEX_FIELDS}


def _next_document_number(rows: list[dict[str, str]]) -> int:
    numbers = []
    for row in rows:
        doc_id = row.get("document_id", "")
        digits = "".join(char for char in doc_id if char.isdigit())
        if digits:
            numbers.append(int(digits))
    return max(numbers, default=0) + 1


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "locked"}


def _document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in DOCX_EXTENSIONS:
        return "docx"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return suffix.lstrip(".") or "unknown"


def _infer_category(loaded: LoadedCase, file_path: Path, source_kind: str) -> str:
    relative_parts: tuple[str, ...] = ()
    matches: list[tuple[int, tuple[str, ...]]] = []
    paths = loaded.config.get("paths", {})
    if isinstance(paths, dict):
        for path_value in paths.values():
            source_root = loaded.case_dir / Path(str(path_value))
            try:
                candidate_parts = file_path.relative_to(source_root).parts
            except ValueError:
                continue
            matches.append((len(source_root.parts), candidate_parts))
    if matches:
        relative_parts = max(matches, key=lambda item: item[0])[1]
    if not relative_parts:
        return source_kind
    top_folder = relative_parts[0]
    for roles_key in ("o1b_folder_roles", "eb1a_folder_roles", "rfe_folder_roles"):
        roles = loaded.config.get(roles_key, {})
        if isinstance(roles, dict):
            for role, folder in roles.items():
                if str(folder) == top_folder:
                    return str(role)
    return top_folder


def _source_key_for_kind(loaded: LoadedCase, source_kind: str) -> str:
    known = {
        "original": "source_originals",
        "translation": "source_translations",
        "other": "source_other",
    }
    if source_kind in known:
        return known[source_kind]
    paths = loaded.config.get("paths", {})
    if not isinstance(paths, dict):
        return ""
    candidate = "source_" + source_kind
    return candidate if candidate in paths else ""


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _merge_notes(existing: str, new: str) -> str:
    existing = (existing or "").strip()
    new = (new or "").strip()
    if not new:
        return existing
    if not existing:
        return new
    if new in existing:
        return existing
    return existing + " | " + new


def _translation_match_decision(
    translation: dict[str, str], originals: list[dict[str, str]]
) -> TranslationMatchDecision:
    translation_under_source = _path_under_source(translation.get("file_path", ""), "source_documents/translations")
    if not translation_under_source:
        return TranslationMatchDecision(None, "invalid_translation_path", 0.0, [])

    category = translation.get("category", "")
    scoped = [original for original in originals if not category or original.get("category", "") == category]
    if not scoped:
        return TranslationMatchDecision(None, "no_originals_in_category", 0.0, [])

    exact_path = "source_documents/originals/" + translation_under_source
    exact_matches = [
        original
        for original in scoped
        if _normalize_slashes(original.get("file_path", "")) == exact_path
    ]
    if len(exact_matches) == 1:
        return TranslationMatchDecision(exact_matches[0], "exact_relative_path", 1.0, [(exact_matches[0], 1.0)])

    translation_parent = str(PurePosixPath(translation_under_source).parent)
    translation_stem = _normalized_match_stem(PurePosixPath(translation_under_source).stem)
    same_parent_matches = []
    for original in scoped:
        original_under_source = _path_under_source(
            original.get("file_path", ""), "source_documents/originals"
        )
        if not original_under_source:
            continue
        original_parent = str(PurePosixPath(original_under_source).parent)
        if original_parent != translation_parent:
            continue
        original_stem = _normalized_match_stem(PurePosixPath(original_under_source).stem)
        if original_stem == translation_stem:
            same_parent_matches.append(original)
    if len(same_parent_matches) == 1:
        return TranslationMatchDecision(
            same_parent_matches[0], "same_folder_normalized_name", 0.995, [(same_parent_matches[0], 0.995)]
        )

    category_name_matches = []
    for original in scoped:
        original_under_source = _path_under_source(original.get("file_path", ""), "source_documents/originals")
        if original_under_source and _normalized_match_stem(PurePosixPath(original_under_source).stem) == translation_stem:
            category_name_matches.append(original)
    if len(category_name_matches) == 1:
        return TranslationMatchDecision(
            category_name_matches[0],
            "unique_normalized_name_in_category",
            0.98,
            [(category_name_matches[0], 0.98)],
        )

    episode_scope, episode_score, episode_method = _episode_scoped_originals(
        translation_under_source, scoped
    )
    candidates = episode_scope or scoped
    ranked: list[tuple[dict[str, str], float]] = []
    for original in candidates:
        original_under_source = _path_under_source(original.get("file_path", ""), "source_documents/originals")
        if not original_under_source:
            continue
        file_score = _match_similarity(
            PurePosixPath(translation_under_source).stem,
            PurePosixPath(original_under_source).stem,
        )
        directory_score = _directory_similarity(translation_under_source, original_under_source)
        combined = (0.74 * file_score) + (0.20 * episode_score) + (0.06 * directory_score)
        ranked.append((original, round(combined, 4)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    alternatives = ranked[:3]
    if not alternatives:
        return TranslationMatchDecision(None, episode_method or "no_candidates", 0.0, [])

    top_original, top_score = alternatives[0]
    runner_up = alternatives[1][1] if len(alternatives) > 1 else 0.0
    margin = top_score - runner_up
    top_path = _path_under_source(top_original.get("file_path", ""), "source_documents/originals")
    top_file_score = _match_similarity(
        PurePosixPath(translation_under_source).stem,
        PurePosixPath(top_path).stem,
    )
    identifying_overlap = _identifying_token_overlap(
        PurePosixPath(translation_under_source).stem,
        PurePosixPath(top_path).stem,
    )
    generic_ambiguity = _is_generic_ambiguous_name(
        PurePosixPath(translation_under_source).stem,
        candidates,
    )
    confident = (
        (top_file_score >= 0.92 and top_score >= 0.80 and margin >= 0.06)
        or (episode_score >= 0.82 and top_file_score >= 0.72 and top_score >= 0.75 and margin >= 0.10)
        or (top_file_score >= 0.84 and top_score >= 0.82 and margin >= 0.12)
        or (episode_score >= 0.82 and identifying_overlap >= 2 and top_score >= 0.60 and margin >= 0.08)
    ) and not generic_ambiguity
    method = f"{episode_method}+fuzzy_name" if episode_method else "fuzzy_name_in_category"
    if confident:
        return TranslationMatchDecision(top_original, method, top_score, alternatives)
    return TranslationMatchDecision(None, method, top_score, alternatives)


def _episode_scoped_originals(
    translation_under_source: str, originals: list[dict[str, str]]
) -> tuple[list[dict[str, str]], float, str]:
    translation_parts = PurePosixPath(translation_under_source).parts
    if len(translation_parts) < 3:
        return originals, 1.0, "category_root"
    translation_episode = translation_parts[1]
    episode_rows: dict[str, list[dict[str, str]]] = {}
    for original in originals:
        original_under_source = _path_under_source(original.get("file_path", ""), "source_documents/originals")
        parts = PurePosixPath(original_under_source).parts
        if len(parts) >= 3:
            episode_rows.setdefault(parts[1], []).append(original)
    if not episode_rows:
        return originals, 0.0, "no_episode_scope"
    ranked_episodes = sorted(
        ((episode, _match_similarity(translation_episode, episode, allow_acronym=True)) for episode in episode_rows),
        key=lambda item: item[1],
        reverse=True,
    )
    best_episode, best_score = ranked_episodes[0]
    runner_up = ranked_episodes[1][1] if len(ranked_episodes) > 1 else 0.0
    if best_score >= 0.78 or (best_score >= 0.58 and best_score - runner_up >= 0.12):
        return episode_rows[best_episode], best_score, "matched_episode"
    return originals, best_score, "uncertain_episode"


def _directory_similarity(translation_path: str, original_path: str) -> float:
    translation_parts = PurePosixPath(translation_path).parts[2:-1]
    original_parts = PurePosixPath(original_path).parts[2:-1]
    if not translation_parts or not original_parts:
        return 0.0
    return max(
        _match_similarity(translation_part, original_part, allow_acronym=True)
        for translation_part in translation_parts
        for original_part in original_parts
    )


def _match_similarity(left: str, right: str, *, allow_acronym: bool = False) -> float:
    left_normalized = _normalized_match_stem(left)
    right_normalized = _normalized_match_stem(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    if min(len(left_normalized), len(right_normalized)) >= 3 and (
        left_normalized in right_normalized or right_normalized in left_normalized
    ):
        shorter = left_normalized if len(left_normalized) <= len(right_normalized) else right_normalized
        generic_short = set(shorter.split()) <= {
            "vote", "article", "profile", "rules", "gratitude", "invitation", "reference", "journal"
        }
        if not generic_short:
            return 0.96
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens)
    containment = overlap / max(1, min(len(left_tokens), len(right_tokens)))
    union = overlap / max(1, len(left_tokens | right_tokens))
    sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    acronym_left = _acronym(left_normalized)
    acronym_right = _acronym(right_normalized)
    acronym_score = 0.94 if allow_acronym and acronym_left and acronym_left == acronym_right else 0.0
    return min(1.0, max(sequence, (0.75 * containment) + (0.25 * union), acronym_score))


def _acronym(value: str) -> str:
    stop = {"i", "v", "na", "po", "o", "ob", "the", "of", "and", "for", "2024", "2025", "2026"}
    words = [word for word in value.split() if len(word) > 1 and word not in stop and not word.isdigit()]
    return "".join(word[0] for word in words) if len(words) >= 2 else ""


def _is_generic_ambiguous_name(stem: str, candidates: list[dict[str, str]]) -> bool:
    generic = {
        "vote",
        "article",
        "profile",
        "rules",
        "gratitude",
        "invitation",
        "reference",
        "journal",
        "certificate",
        "ustav",
        "programma",
    }
    tokens = set(_normalized_match_stem(stem).split())
    generic_tokens = tokens & generic
    identifying_tokens = {token for token in tokens - generic if not token.isdigit()}
    if not generic_tokens or identifying_tokens:
        return False
    matches = 0
    for candidate in candidates:
        candidate_tokens = set(_normalized_match_stem(Path(candidate.get("file_path", "")).stem).split())
        if generic_tokens & candidate_tokens:
            matches += 1
    return matches > 1


def _identifying_token_overlap(left: str, right: str) -> int:
    generic = {
        "vote", "article", "profile", "rules", "gratitude", "invitation", "reference", "journal",
        "kim", "aleksei", "alexey", "gmail", "award", "awards", "premii", "nominatsiya", "sayte",
        "dokument", "dokumenty", "kompanii", "company", "dogovor", "forma", "podtverzhdeniya",
        "o", "ob", "po", "v", "na", "i", "the", "of", "and", "for",
    }
    left_tokens = {
        token for token in _normalized_match_stem(left).split() if token not in generic and not token.isdigit()
    }
    right_tokens = {
        token for token in _normalized_match_stem(right).split() if token not in generic and not token.isdigit()
    }
    return len(left_tokens & right_tokens)


def _translation_report_row(
    translation: dict[str, str],
    status: str,
    method: str,
    score: float,
    alternatives: list[tuple[dict[str, str], float]],
) -> dict[str, str]:
    return {
        "translation_document_id": translation.get("document_id", ""),
        "translation_file_path": translation.get("file_path", ""),
        "category": translation.get("category", ""),
        "status": status,
        "parent_document_id": translation.get("parent_document_id", ""),
        "match_method": method,
        "confidence": f"{score:.3f}" if score else "",
        "suggested_originals": " | ".join(
            f"{original.get('document_id', '')} ({candidate_score:.3f}) {original.get('file_path', '')}"
            for original, candidate_score in alternatives[:3]
        ),
    }


def _write_translation_report(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "translation_document_id",
        "translation_file_path",
        "category",
        "status",
        "parent_document_id",
        "match_method",
        "confidence",
        "suggested_originals",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _path_under_source(file_path: str, source_prefix: str) -> str:
    normalized = _normalize_slashes(file_path)
    prefix = source_prefix.rstrip("/") + "/"
    if not normalized.startswith(prefix):
        return ""
    return normalized[len(prefix) :]


def _normalized_match_stem(stem: str) -> str:
    value = _transliterate_cyrillic(stem.lower())
    value = re.sub(r"[_\-.,()\[\]{}]+", " ", value)
    value = re.sub(
        r"\b(translation|translated|english|eng|en|perevod|angl|angliiskii|removed|copy|kopiya|scan|skan|version)\b",
        " ",
        value,
    )
    synonym_tokens = {
        "golosovanie": "vote",
        "golosovalka": "vote",
        "zhyuri": "jury",
        "biografiya": "profile",
        "polozhenie": "rules",
        "blagodarnost": "gratitude",
        "blagodaronost": "gratitude",
        "priglashenie": "invitation",
        "statya": "article",
        "intervyu": "article",
        "publikatsiya": "article",
        "rekomendatsiya": "recommendation",
        "rekpismo": "recommendation",
        "pismo": "letter",
        "spravka": "reference",
        "zhurnal": "journal",
        "izdanie": "journal",
    }
    value = " ".join(synonym_tokens.get(token, token) for token in value.split())
    value = re.sub(r"\b(recommendation|letter)\b", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _transliterate_cyrillic(value: str) -> str:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    return "".join(mapping.get(character, character) for character in value)
