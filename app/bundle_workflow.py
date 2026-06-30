from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

from .evidence import INDEX_FIELDS
from .workflow import _case_path_value, _normalize_slashes, extract_docx_text, load_case


EXHIBIT_FIELDS = [
    "exhibit_id",
    "exhibit_number",
    "parent_exhibit_id",
    "display_title",
    "evidentiary_thesis",
    "task_type",
    "memo_section",
    "separator_title_type",
    "document_ids",
    "original_translation_order",
    "final_bundle_order",
    "user_approval_status",
    "manual_edit_lock",
    "notes",
]

TEXT_SOURCE_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
DOCX_SOURCE_EXTENSIONS = {".docx"}
IMAGE_SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
PDF_SOURCE_EXTENSIONS = {".pdf"}


@dataclass(frozen=True)
class ExhibitIndexSummary:
    exhibit_index_path: Path
    document_index_path: Path
    documents_seen: int
    documents_with_exhibit_number: int
    exhibits_created: int
    exhibits_updated: int
    locked_exhibits_skipped: int
    document_orders_written: int
    documents_without_exhibit_number: int


@dataclass(frozen=True)
class SeparatorSummary:
    separators_dir: Path
    exhibits_seen: int
    exhibit_pages_written: int
    document_pages_written: int
    missing_document_ids: int
    manifest_path: Path


@dataclass(frozen=True)
class SeparatorPdfSummary:
    source_dir: Path
    output_dir: Path
    markdown_files_seen: int
    pdf_pages_written: int
    manifest_path: Path


@dataclass(frozen=True)
class BundlePlanSummary:
    plan_csv_path: Path
    plan_md_path: Path
    total_items: int
    ready_items: int
    missing_items: int
    unsupported_items: int
    source_documents: int
    separator_pdfs: int


@dataclass(frozen=True)
class BundleBuildSummary:
    final_pdf_path: Path
    plan_csv_path: Path
    merged_items: int
    converted_items: int
    skipped_items: int


def build_exhibit_index(case_id: str) -> ExhibitIndexSummary:
    loaded = load_case(case_id)
    document_index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    exhibit_index_path = loaded.case_dir / _case_path_value(loaded.config, "exhibit_index")

    document_rows = _read_csv(document_index_path, INDEX_FIELDS)
    exhibit_rows = _read_csv(exhibit_index_path, EXHIBIT_FIELDS)
    exhibits_by_number = {
        row.get("exhibit_number", ""): row
        for row in exhibit_rows
        if row.get("exhibit_number")
    }

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in document_rows:
        exhibit_number = row.get("exhibit_number", "").strip()
        if exhibit_number:
            grouped.setdefault(exhibit_number, []).append(row)

    exhibits_created = 0
    exhibits_updated = 0
    locked_exhibits_skipped = 0
    document_orders_written = 0

    ordered_exhibit_numbers = sorted(grouped, key=_natural_sort_key)
    next_exhibit_id = _next_exhibit_number(exhibit_rows)
    global_document_order = 1

    for exhibit_order, exhibit_number in enumerate(ordered_exhibit_numbers, start=1):
        ordered_documents = order_documents_original_then_translation(grouped[exhibit_number])
        row = exhibits_by_number.get(exhibit_number)
        if row is None:
            row = _blank_exhibit_row()
            row["exhibit_id"] = f"EXH{next_exhibit_id:03d}"
            next_exhibit_id += 1
            row["exhibit_number"] = exhibit_number
            row["display_title"] = f"Exhibit {exhibit_number}"
            row["separator_title_type"] = "exhibit"
            row["user_approval_status"] = "pending"
            row["manual_edit_lock"] = "false"
            exhibit_rows.append(row)
            exhibits_by_number[exhibit_number] = row
            exhibits_created += 1
        elif _truthy(row.get("manual_edit_lock", "")):
            locked_exhibits_skipped += 1
            for document in ordered_documents:
                if not _truthy(document.get("manual_edit_lock", "")):
                    if not document.get("final_bundle_order"):
                        document["final_bundle_order"] = str(global_document_order)
                        document_orders_written += 1
                    global_document_order += 1
            continue
        else:
            exhibits_updated += 1

        row["task_type"] = row.get("task_type") or str(loaded.config.get("task_type", ""))
        row["memo_section"] = row.get("memo_section") or _common_value(ordered_documents, "memo_section_relevance")
        row["separator_title_type"] = row.get("separator_title_type") or "exhibit"
        row["document_ids"] = ";".join(document.get("document_id", "") for document in ordered_documents)
        row["original_translation_order"] = str(
            loaded.config.get("translation_order", "original_then_translation")
        )
        row["final_bundle_order"] = row.get("final_bundle_order") or str(exhibit_order)
        row["notes"] = _merge_note(row.get("notes", ""), "Generated/updated from document_index.csv.")

        for document in ordered_documents:
            if _truthy(document.get("manual_edit_lock", "")):
                global_document_order += 1
                continue
            if not document.get("final_bundle_order"):
                document["final_bundle_order"] = str(global_document_order)
                document_orders_written += 1
            global_document_order += 1

    _write_csv(document_index_path, document_rows, INDEX_FIELDS)
    _write_csv(exhibit_index_path, exhibit_rows, EXHIBIT_FIELDS)
    return ExhibitIndexSummary(
        exhibit_index_path=exhibit_index_path,
        document_index_path=document_index_path,
        documents_seen=len(document_rows),
        documents_with_exhibit_number=sum(1 for row in document_rows if row.get("exhibit_number", "").strip()),
        exhibits_created=exhibits_created,
        exhibits_updated=exhibits_updated,
        locked_exhibits_skipped=locked_exhibits_skipped,
        document_orders_written=document_orders_written,
        documents_without_exhibit_number=sum(
            1 for row in document_rows if not row.get("exhibit_number", "").strip()
        ),
    )


def generate_separator_pages(case_id: str) -> SeparatorSummary:
    loaded = load_case(case_id)
    document_index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    exhibit_index_path = loaded.case_dir / _case_path_value(loaded.config, "exhibit_index")
    bundle_root = loaded.case_dir / _case_path_value(loaded.config, "bundle_root")
    separators_dir = bundle_root / "separators" / "generated"
    separators_dir.mkdir(parents=True, exist_ok=True)

    document_rows = _read_csv(document_index_path, INDEX_FIELDS)
    exhibit_rows = _read_csv(exhibit_index_path, EXHIBIT_FIELDS)
    documents_by_id = {
        row.get("document_id", ""): row
        for row in document_rows
        if row.get("document_id")
    }

    exhibit_pages_written = 0
    document_pages_written = 0
    missing_document_ids = 0
    manifest_lines = [
        "# Generated separator pages",
        "",
        "Do not edit these generated files directly; rerunning the command may overwrite them.",
        "",
    ]

    ordered_exhibits = sorted(exhibit_rows, key=_exhibit_sort_key)
    for exhibit_position, exhibit in enumerate(ordered_exhibits, start=1):
        exhibit_number = exhibit.get("exhibit_number", "").strip()
        if not exhibit_number:
            continue
        document_ids = [part.strip() for part in exhibit.get("document_ids", "").split(";") if part.strip()]
        exhibit_file = separators_dir / f"{exhibit_position:03d}_exhibit_{_safe_filename(exhibit_number)}.md"
        exhibit_file.write_text(
            _render_exhibit_separator(exhibit, document_ids, documents_by_id),
            encoding="utf-8",
        )
        exhibit_pages_written += 1
        manifest_lines.append(f"- {exhibit_file.relative_to(bundle_root).as_posix()}")

        for document_position, document_id in enumerate(document_ids, start=1):
            document = documents_by_id.get(document_id)
            if document is None:
                missing_document_ids += 1
                continue
            document_file = (
                separators_dir
                / f"{exhibit_position:03d}_{document_position:03d}_{_safe_filename(document_id)}.md"
            )
            document_file.write_text(
                _render_document_separator(exhibit, document),
                encoding="utf-8",
            )
            document_pages_written += 1
            manifest_lines.append(f"- {document_file.relative_to(bundle_root).as_posix()}")

    manifest_path = separators_dir / "manifest.md"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return SeparatorSummary(
        separators_dir=separators_dir,
        exhibits_seen=len(ordered_exhibits),
        exhibit_pages_written=exhibit_pages_written,
        document_pages_written=document_pages_written,
        missing_document_ids=missing_document_ids,
        manifest_path=manifest_path,
    )


def render_separator_pdfs(case_id: str) -> SeparatorPdfSummary:
    loaded = load_case(case_id)
    bundle_root = loaded.case_dir / _case_path_value(loaded.config, "bundle_root")
    source_dir = bundle_root / "separators" / "generated"
    output_dir = bundle_root / "separators" / "pdf"
    if not source_dir.exists():
        raise SystemExit(
            f"Separator markdown folder not found: {source_dir}. "
            "Run `python -m app.bundle separators --case CASE_ID` first."
        )

    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.enums import TA_CENTER  # type: ignore
        from reportlab.lib.pagesizes import LETTER  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing PDF dependency `reportlab`. Install with `pip install .[pdf]` "
            "or run this command with the bundled Codex Python runtime."
        ) from exc

    font_name = _register_pdf_font(pdfmetrics, TTFont)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_files = [
        path
        for path in sorted(source_dir.glob("*.md"))
        if path.name.lower() != "manifest.md"
    ]

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SeparatorTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            spaceAfter=0.25 * inch,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SeparatorHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#222222"),
            spaceBefore=0.12 * inch,
            spaceAfter=0.06 * inch,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SeparatorBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=14,
            spaceAfter=0.06 * inch,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SeparatorMeta",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#555555"),
            spaceAfter=0.05 * inch,
        )
    )

    pdf_count = 0
    manifest_lines = [
        "# Generated separator PDFs",
        "",
        "Generated from bundle/separators/generated/*.md.",
        "",
    ]
    for markdown_path in markdown_files:
        pdf_path = output_dir / (markdown_path.stem + ".pdf")
        story = _markdown_to_reportlab_story(markdown_path.read_text(encoding="utf-8-sig"), styles, Spacer)
        document = SimpleDocTemplate(
            str(pdf_path),
            pagesize=LETTER,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            title=markdown_path.stem,
        )
        document.build(story)
        pdf_count += 1
        manifest_lines.append(f"- {pdf_path.relative_to(bundle_root).as_posix()}")

    manifest_path = output_dir / "manifest.md"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return SeparatorPdfSummary(
        source_dir=source_dir,
        output_dir=output_dir,
        markdown_files_seen=len(markdown_files),
        pdf_pages_written=pdf_count,
        manifest_path=manifest_path,
    )


def build_bundle_plan(case_id: str) -> BundlePlanSummary:
    loaded = load_case(case_id)
    document_index_path = loaded.case_dir / _case_path_value(loaded.config, "document_index")
    exhibit_index_path = loaded.case_dir / _case_path_value(loaded.config, "exhibit_index")
    bundle_root = loaded.case_dir / _case_path_value(loaded.config, "bundle_root")
    plan_dir = bundle_root / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    document_rows = _read_csv(document_index_path, INDEX_FIELDS)
    exhibit_rows = _read_csv(exhibit_index_path, EXHIBIT_FIELDS)
    documents_by_id = {
        row.get("document_id", ""): row
        for row in document_rows
        if row.get("document_id")
    }

    items: list[dict[str, str]] = []
    sequence = 1
    ordered_exhibits = sorted(exhibit_rows, key=_exhibit_sort_key)
    for exhibit_position, exhibit in enumerate(ordered_exhibits, start=1):
        exhibit_number = exhibit.get("exhibit_number", "").strip()
        if not exhibit_number:
            continue
        exhibit_separator = (
            bundle_root
            / "separators"
            / "pdf"
            / f"{exhibit_position:03d}_exhibit_{_safe_filename(exhibit_number)}.pdf"
        )
        items.append(
            _plan_item(
                sequence,
                "exhibit_separator",
                exhibit_number,
                "",
                exhibit_separator,
                loaded.case_dir,
                _pdf_status(exhibit_separator),
                "Generated exhibit separator PDF.",
            )
        )
        sequence += 1

        document_ids = [part.strip() for part in exhibit.get("document_ids", "").split(";") if part.strip()]
        for document_position, document_id in enumerate(document_ids, start=1):
            document = documents_by_id.get(document_id)
            document_separator = (
                bundle_root
                / "separators"
                / "pdf"
                / f"{exhibit_position:03d}_{document_position:03d}_{_safe_filename(document_id)}.pdf"
            )
            items.append(
                _plan_item(
                    sequence,
                    "document_separator",
                    exhibit_number,
                    document_id,
                    document_separator,
                    loaded.case_dir,
                    _pdf_status(document_separator),
                    "Generated document separator PDF.",
                )
            )
            sequence += 1
            if not document:
                items.append(
                    _plan_item(
                        sequence,
                        "source_document",
                        exhibit_number,
                        document_id,
                        loaded.case_dir / "__missing_document_index_row__",
                        loaded.case_dir,
                        "missing",
                        "Document ID is listed in exhibit_index.csv but missing from document_index.csv.",
                    )
                )
                sequence += 1
                continue
            source_path = loaded.case_dir / document.get("file_path", "")
            status, note = _source_document_status(source_path)
            items.append(
                _plan_item(
                    sequence,
                    "source_document",
                    exhibit_number,
                    document_id,
                    source_path,
                    loaded.case_dir,
                    status,
                    note,
                )
            )
            sequence += 1

    plan_csv_path = plan_dir / "bundle_plan.csv"
    plan_md_path = plan_dir / "bundle_plan.md"
    _write_plan_csv(plan_csv_path, items)
    plan_md_path.write_text(_render_plan_markdown(items), encoding="utf-8")
    return BundlePlanSummary(
        plan_csv_path=plan_csv_path,
        plan_md_path=plan_md_path,
        total_items=len(items),
        ready_items=sum(1 for item in items if item["status"] in {"ready_pdf", "convertible_image", "convertible_text"}),
        missing_items=sum(1 for item in items if item["status"] == "missing"),
        unsupported_items=sum(1 for item in items if item["status"] == "unsupported"),
        source_documents=sum(1 for item in items if item["item_type"] == "source_document"),
        separator_pdfs=sum(1 for item in items if item["item_type"].endswith("_separator")),
    )


def build_evidence_bundle(case_id: str) -> BundleBuildSummary:
    loaded = load_case(case_id)
    plan_summary = build_bundle_plan(case_id)
    items = _read_plan_csv(plan_summary.plan_csv_path)
    blocking = [item for item in items if item["status"] in {"missing", "unsupported"}]
    if blocking:
        raise SystemExit(
            f"Bundle has {len(blocking)} missing/unsupported item(s). "
            f"Review plan: {plan_summary.plan_md_path}"
        )

    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
        from reportlab.lib.pagesizes import LETTER  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.lib.utils import ImageReader  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing PDF dependencies. Install with `pip install .[pdf]` "
            "or run this command with the bundled Codex Python runtime."
        ) from exc

    bundle_root = loaded.case_dir / _case_path_value(loaded.config, "bundle_root")
    converted_dir = bundle_root / "converted"
    final_dir = bundle_root / "final"
    converted_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_pdf_path = final_dir / "evidence_bundle.pdf"

    writer = PdfWriter()
    merged_items = 0
    converted_items = 0
    skipped_items = 0
    for item in items:
        source_path = loaded.case_dir / item["path"]
        pdf_path = source_path
        if item["status"] == "convertible_image":
            pdf_path = converted_dir / f"{int(item['sequence']):04d}_{_safe_filename(item['document_id'] or item['item_type'])}.pdf"
            _image_to_pdf(source_path, pdf_path, canvas, LETTER, inch, ImageReader)
            converted_items += 1
        elif item["status"] == "convertible_text":
            pdf_path = converted_dir / f"{int(item['sequence']):04d}_{_safe_filename(item['document_id'] or item['item_type'])}.pdf"
            _text_source_to_pdf(source_path, pdf_path)
            converted_items += 1
        elif item["status"] != "ready_pdf":
            skipped_items += 1
            continue

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
        merged_items += 1

    with final_pdf_path.open("wb") as handle:
        writer.write(handle)
    return BundleBuildSummary(
        final_pdf_path=final_pdf_path,
        plan_csv_path=plan_summary.plan_csv_path,
        merged_items=merged_items,
        converted_items=converted_items,
        skipped_items=skipped_items,
    )


def order_documents_original_then_translation(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_id = {row.get("document_id", ""): row for row in rows if row.get("document_id")}
    translations_by_parent: dict[str, list[dict[str, str]]] = {}
    originals: list[dict[str, str]] = []
    unpaired_translations: list[dict[str, str]] = []

    for row in rows:
        parent = row.get("parent_document_id", "").strip()
        is_translation = row.get("relationship_type") == "translation" or row.get("translation_status") == "translation"
        if is_translation and parent:
            translations_by_parent.setdefault(parent, []).append(row)
        elif is_translation:
            unpaired_translations.append(row)
        else:
            originals.append(row)

    ordered: list[dict[str, str]] = []
    for original in sorted(originals, key=_document_sort_key):
        ordered.append(original)
        linked = translations_by_parent.pop(original.get("document_id", ""), [])
        ordered.extend(sorted(linked, key=_document_sort_key))

    for parent_id in sorted(translations_by_parent, key=_natural_sort_key):
        parent = by_id.get(parent_id)
        if parent and parent not in ordered:
            ordered.append(parent)
        ordered.extend(sorted(translations_by_parent[parent_id], key=_document_sort_key))

    ordered.extend(sorted(unpaired_translations, key=_document_sort_key))
    return ordered


def _read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            normalized = {field: "" for field in fields}
            normalized.update({key: value or "" for key, value in row.items() if key})
            rows.append(normalized)
        return rows


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _blank_exhibit_row() -> dict[str, str]:
    return {field: "" for field in EXHIBIT_FIELDS}


def _document_sort_key(row: dict[str, str]) -> tuple[int, list[object], str]:
    order = row.get("final_bundle_order", "").strip()
    if order.isdigit():
        return (0, [int(order)], row.get("document_id", ""))
    return (1, _natural_sort_key(row.get("file_path", "") or row.get("document_id", "")), row.get("document_id", ""))


def _natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value or "")]


def _next_exhibit_number(rows: list[dict[str, str]]) -> int:
    numbers = []
    for row in rows:
        exhibit_id = row.get("exhibit_id", "")
        digits = "".join(char for char in exhibit_id if char.isdigit())
        if digits:
            numbers.append(int(digits))
    return max(numbers, default=0) + 1


def _common_value(rows: list[dict[str, str]], key: str) -> str:
    values = sorted({row.get(key, "").strip() for row in rows if row.get(key, "").strip()})
    if len(values) == 1:
        return values[0]
    return ""


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "locked"}


def _merge_note(existing: str, note: str) -> str:
    existing = (existing or "").strip()
    note = note.strip()
    if not note:
        return existing
    if not existing:
        return note
    if note in existing:
        return existing
    return existing + " | " + note


def _render_exhibit_separator(
    exhibit: dict[str, str],
    document_ids: list[str],
    documents_by_id: dict[str, dict[str, str]],
) -> str:
    exhibit_number = exhibit.get("exhibit_number", "")
    title = exhibit.get("display_title", "") or f"Exhibit {exhibit_number}"
    lines = [
        "---",
        "separator_type: exhibit",
        f"exhibit_number: {exhibit_number}",
        f"exhibit_id: {exhibit.get('exhibit_id', '')}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    thesis = exhibit.get("evidentiary_thesis", "").strip()
    if thesis:
        lines.extend(["## Evidentiary thesis", "", thesis, ""])
    lines.extend(["## Documents included", ""])
    if document_ids:
        for index, document_id in enumerate(document_ids, start=1):
            document = documents_by_id.get(document_id, {})
            doc_title = _document_title(document) if document else "[missing document in document_index.csv]"
            relationship = _relationship_label(document)
            lines.append(f"{index}. {document_id} - {doc_title}{relationship}")
    else:
        lines.append("[No document_ids listed for this exhibit.]")
    lines.append("")
    lines.append("Generated from exhibit_index.csv and document_index.csv.")
    return "\n".join(lines) + "\n"


def _render_document_separator(exhibit: dict[str, str], document: dict[str, str]) -> str:
    title = _document_title(document)
    lines = [
        "---",
        "separator_type: document",
        f"exhibit_number: {document.get('exhibit_number', exhibit.get('exhibit_number', ''))}",
        f"document_id: {document.get('document_id', '')}",
        "---",
        "",
        f"# {title}",
        "",
        f"**Exhibit:** {document.get('exhibit_number', exhibit.get('exhibit_number', ''))}",
        "",
        f"**Document ID:** {document.get('document_id', '')}",
        "",
        f"**Document type:** {document.get('document_type', '')}",
        "",
        f"**Source file:** `{document.get('file_path', '')}`",
        "",
        f"**Translation status:** {document.get('translation_status', '') or 'not set'}",
        "",
    ]
    if document.get("relationship_type"):
        lines.extend([f"**Relationship type:** {document.get('relationship_type', '')}", ""])
    if document.get("parent_document_id"):
        lines.extend(
            [
                f"**Relationship:** translation of {document.get('parent_document_id', '')}",
                "",
                f"**Original document ID:** {document.get('parent_document_id', '')}",
                "",
                "**Bundle order:** original first, then this translation.",
                "",
            ]
        )
    if document.get("short_description"):
        lines.extend(["## Description", "", document.get("short_description", ""), ""])
    if document.get("person_or_organization"):
        lines.extend(["## Person / organization", "", document.get("person_or_organization", ""), ""])
    if document.get("document_date"):
        lines.extend(["## Date", "", document.get("document_date", ""), ""])
    notes = document.get("notes", "").strip()
    if notes:
        lines.extend(["## Notes", "", notes, ""])
    lines.append("Generated from document_index.csv.")
    return "\n".join(lines) + "\n"


def _document_title(document: dict[str, str]) -> str:
    return (
        document.get("display_title", "").strip()
        or document.get("original_file_name", "").strip()
        or document.get("document_id", "").strip()
        or "[untitled document]"
    )


def _relationship_label(document: dict[str, str]) -> str:
    if not document:
        return ""
    if document.get("relationship_type") == "translation" or document.get("translation_status") == "translation":
        parent = document.get("parent_document_id", "").strip()
        return f" (translation of {parent})" if parent else " (translation)"
    if document.get("translation_status") == "original":
        return " (original)"
    return ""


def _exhibit_sort_key(row: dict[str, str]) -> tuple[int, list[object], str]:
    order = row.get("final_bundle_order", "").strip()
    if order.isdigit():
        return (0, [int(order)], row.get("exhibit_number", ""))
    return (1, _natural_sort_key(row.get("exhibit_number", "")), row.get("exhibit_id", ""))


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    safe = safe.strip("._-")
    return safe or "untitled"


def _plan_item(
    sequence: int,
    item_type: str,
    exhibit_number: str,
    document_id: str,
    path: Path,
    case_dir: Path,
    status: str,
    notes: str,
) -> dict[str, str]:
    try:
        relative_path = _normalize_slashes(path.relative_to(case_dir).as_posix())
    except ValueError:
        relative_path = _normalize_slashes(str(path))
    return {
        "sequence": str(sequence),
        "item_type": item_type,
        "exhibit_number": exhibit_number,
        "document_id": document_id,
        "path": relative_path,
        "status": status,
        "notes": notes,
    }


def _pdf_status(path: Path) -> str:
    return "ready_pdf" if path.exists() else "missing"


def _source_document_status(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "missing", "Source file missing."
    suffix = path.suffix.lower()
    if suffix in PDF_SOURCE_EXTENSIONS:
        return "ready_pdf", "Source PDF."
    if suffix in IMAGE_SOURCE_EXTENSIONS:
        return "convertible_image", "Image will be converted to PDF."
    if suffix in TEXT_SOURCE_EXTENSIONS | DOCX_SOURCE_EXTENSIONS:
        return "convertible_text", "Text/DOCX source will be rendered to PDF."
    return "unsupported", f"Unsupported source type for PDF bundle: {suffix or '[no extension]'}"


PLAN_FIELDS = ["sequence", "item_type", "exhibit_number", "document_id", "path", "status", "notes"]


def _write_plan_csv(path: Path, items: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_FIELDS)
        writer.writeheader()
        writer.writerows(items)


def _read_plan_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _render_plan_markdown(items: list[dict[str, str]]) -> str:
    lines = [
        "# Evidence bundle plan",
        "",
        "| # | Type | Exhibit | Document | Status | Path | Notes |",
        "|---:|---|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["sequence"],
                    item["item_type"],
                    item["exhibit_number"],
                    item["document_id"],
                    item["status"],
                    "`" + item["path"] + "`",
                    item["notes"].replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _image_to_pdf(
    image_path: Path,
    pdf_path: Path,
    canvas: object,
    pagesize: tuple[float, float],
    inch: float,
    ImageReader: object,
) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = pagesize
    margin = 0.6 * inch
    c = canvas.Canvas(str(pdf_path), pagesize=pagesize)  # type: ignore[attr-defined]
    image = ImageReader(str(image_path))  # type: ignore[operator]
    image_width, image_height = image.getSize()
    max_width = page_width - 2 * margin
    max_height = page_height - 2 * margin
    scale = min(max_width / image_width, max_height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    x = (page_width - draw_width) / 2
    y = (page_height - draw_height) / 2
    c.drawImage(image, x, y, width=draw_width, height=draw_height, preserveAspectRatio=True)
    c.showPage()
    c.save()


def _text_source_to_pdf(source_path: Path, pdf_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing reportlab for text conversion.") from exc

    text = extract_docx_text(source_path) if source_path.suffix.lower() in DOCX_SOURCE_EXTENSIONS else source_path.read_text(encoding="utf-8-sig", errors="replace")
    font_name = _register_pdf_font(pdfmetrics, TTFont)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SourceText",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=13,
        )
    )
    story: list[object] = [Paragraph(escape(source_path.name), styles["Title"]), Spacer(1, 0.2 * inch)]
    for paragraph in text.splitlines():
        if paragraph.strip():
            story.append(Paragraph(escape(paragraph.strip()), styles["SourceText"]))
            story.append(Spacer(1, 0.05 * inch))
    if len(story) == 2:
        story.append(Paragraph("[empty text source]", styles["SourceText"]))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=source_path.name,
    )
    document.build(story)


def _register_pdf_font(pdfmetrics: object, TTFont: object) -> str:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            font_name = font_path.stem.replace(" ", "")
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))  # type: ignore[attr-defined]
                return font_name
            except Exception:
                continue
    return "Helvetica"


def _markdown_to_reportlab_story(text: str, styles: object, Spacer: object) -> list[object]:
    story: list[object] = []
    in_front_matter = False
    front_matter_done = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "---" and not front_matter_done:
            in_front_matter = not in_front_matter
            if not in_front_matter:
                front_matter_done = True
            continue
        if in_front_matter or not line:
            continue
        story.extend(_markdown_line_to_flowables(line, styles, Spacer))
    if not story:
        from reportlab.platypus import Paragraph  # type: ignore

        story.append(Paragraph("[blank separator]", styles["SeparatorBody"]))  # type: ignore[index]
    return story


def _markdown_line_to_flowables(line: str, styles: object, Spacer: object) -> list[object]:
    from reportlab.platypus import Paragraph  # type: ignore

    if line.startswith("# "):
        return [Paragraph(_inline_markdown_to_html(line[2:]), styles["SeparatorTitle"])]  # type: ignore[index]
    if line.startswith("## "):
        return [Paragraph(_inline_markdown_to_html(line[3:]), styles["SeparatorHeading"])]  # type: ignore[index]
    if re.match(r"^\d+\.\s+", line):
        return [Paragraph(_inline_markdown_to_html(line), styles["SeparatorBody"])]  # type: ignore[index]
    if line.startswith("- "):
        return [Paragraph("• " + _inline_markdown_to_html(line[2:]), styles["SeparatorBody"])]  # type: ignore[index]
    if line.startswith("**"):
        return [Paragraph(_inline_markdown_to_html(line), styles["SeparatorMeta"])]  # type: ignore[index]
    return [Paragraph(_inline_markdown_to_html(line), styles["SeparatorBody"])]  # type: ignore[index]


def _inline_markdown_to_html(value: str) -> str:
    escaped = escape(value)
    escaped = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    return escaped
