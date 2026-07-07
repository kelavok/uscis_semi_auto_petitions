from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .bundle_workflow import _register_pdf_font
from .file_rules import is_office_temporary_file
from .workflow import extract_docx_text, load_case


LAYOUT_ROOT = "document_layout"
SETTINGS_FILE = "settings.json"
INVENTORY_FILE = "inventory.json"
STRUCTURE_FILE = "structure.json"
MAPPINGS_FILE = "mappings.json"
COMPONENTS_DIR = "generated/separators"
CONVERTED_DIR = "generated/converted"
PREVIEW_PDF = "output/layout_preview.pdf"
FINAL_PDF = "output/layout_bundle.pdf"
SELECTION_FILE = "selection.json"

TEXT_FILE_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
IMAGE_FILE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
OFFICE_FILE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
}
PDF_FILE_EXTENSIONS = {".pdf"}
PAGE_BREAK = "__PAGE_BREAK__"
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@dataclass(frozen=True)
class LayoutParseSummary:
    settings: dict[str, str]
    original_files: int
    translation_files: int
    exhibits: int
    episodes: int
    documents: int


@dataclass(frozen=True)
class LayoutBuildSummary:
    pdf_path: Path
    exhibits: int
    episodes: int
    documents: int
    source_files: int


@dataclass(frozen=True)
class LayoutStatus:
    settings: dict[str, str]
    inventory: dict[str, list[dict[str, str]]]
    structure: dict[str, list[dict[str, Any]]]
    mappings: dict[str, dict[str, list[str]]]
    preview_pdf: Path
    final_pdf: Path
    exhibit_count: int
    episode_count: int
    document_count: int
    mapped_document_count: int
    fully_mapped_document_count: int
    stage1_complete: bool
    stage2_available: bool
    stage2_complete: bool
    stage3_available: bool
    has_preview: bool
    has_final: bool
    unmapped_documents: tuple[dict[str, str], ...]


def load_layout_status(case_id: str) -> LayoutStatus:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    settings = _load_settings(loaded.case_dir)
    inventory = _load_inventory(loaded.case_dir)
    structure = _load_structure(loaded.case_dir)
    mappings = _load_mappings(loaded.case_dir)
    preview_pdf = _layout_root(loaded.case_dir) / PREVIEW_PDF
    final_pdf = _layout_root(loaded.case_dir) / FINAL_PDF

    exhibits = structure.get("exhibits", [])
    exhibit_count = len(exhibits)
    episode_count = 0
    document_count = 0
    mapped_document_count = 0
    fully_mapped_document_count = 0
    unmapped_documents: list[dict[str, str]] = []
    for exhibit in exhibits:
        for episode in exhibit.get("episodes", []):
            if episode.get("kind") != "direct":
                episode_count += 1
            for document in episode.get("documents", []):
                document_count += 1
                mapping = mappings.get(document.get("id", ""), {})
                original_paths = _existing_paths(mapping.get("original_paths", []))
                translation_paths = _existing_paths(mapping.get("translation_paths", []))
                if original_paths or translation_paths:
                    mapped_document_count += 1
                if original_paths:
                    fully_mapped_document_count += 1
                else:
                    unmapped_documents.append(
                        {
                            "document_id": document.get("id", ""),
                            "document_number": document.get("number", ""),
                            "document_title": document.get("title", ""),
                        }
                    )

    list_document_path = Path(settings.get("list_document_path", "")) if settings.get("list_document_path") else None
    originals_dir = Path(settings.get("originals_dir", "")) if settings.get("originals_dir") else None
    stage1_complete = bool(
        exhibit_count
        and document_count
        and originals_dir
        and originals_dir.exists()
        and list_document_path
        and list_document_path.exists()
    )
    stage2_available = stage1_complete
    stage2_complete = stage1_complete and document_count > 0 and fully_mapped_document_count == document_count
    stage3_available = stage1_complete and any(
        _existing_paths(mapping.get("original_paths", [])) for mapping in mappings.values()
    )
    return LayoutStatus(
        settings=settings,
        inventory=inventory,
        structure=structure,
        mappings=mappings,
        preview_pdf=preview_pdf,
        final_pdf=final_pdf,
        exhibit_count=exhibit_count,
        episode_count=episode_count,
        document_count=document_count,
        mapped_document_count=mapped_document_count,
        fully_mapped_document_count=fully_mapped_document_count,
        stage1_complete=stage1_complete,
        stage2_available=stage2_available,
        stage2_complete=stage2_complete,
        stage3_available=stage3_available,
        has_preview=preview_pdf.exists(),
        has_final=final_pdf.exists(),
        unmapped_documents=tuple(unmapped_documents),
    )


def refresh_layout_sources(
    case_id: str,
    *,
    originals_dir: str = "",
    translations_dir: str = "",
    list_document_path: str = "",
) -> LayoutParseSummary:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    settings = _load_settings(loaded.case_dir)
    if originals_dir.strip():
        settings["originals_dir"] = originals_dir.strip()
    if translations_dir.strip():
        settings["translations_dir"] = translations_dir.strip()
    if list_document_path.strip():
        settings["list_document_path"] = list_document_path.strip()
    if not settings.get("originals_dir"):
        raise ValueError("Choose the originals folder first.")
    if not settings.get("list_document_path"):
        raise ValueError("Choose the exhibit list document first.")

    originals_root = Path(settings["originals_dir"]).expanduser().resolve()
    translations_root = (
        Path(settings["translations_dir"]).expanduser().resolve()
        if settings.get("translations_dir")
        else None
    )
    list_path = Path(settings["list_document_path"]).expanduser().resolve()
    if not originals_root.exists() or not originals_root.is_dir():
        raise ValueError(f"Originals folder not found: {originals_root}")
    if translations_root and (not translations_root.exists() or not translations_root.is_dir()):
        raise ValueError(f"Translations folder not found: {translations_root}")
    if not list_path.exists() or not list_path.is_file():
        raise ValueError(f"Exhibit list document not found: {list_path}")

    settings["originals_dir"] = str(originals_root)
    settings["translations_dir"] = str(translations_root) if translations_root else ""
    settings["list_document_path"] = str(list_path)

    inventory = {
        "original_files": _scan_inventory_group(originals_root, "original"),
        "translation_files": _scan_inventory_group(translations_root, "translation") if translations_root else [],
    }
    structure = _parse_structure_from_document(list_path)
    structure = _renumber_structure(structure)
    previous_structure = _load_structure(loaded.case_dir)
    previous_mappings = _load_mappings(loaded.case_dir)
    preserved_mappings = _preserve_mappings(previous_structure, previous_mappings, structure)

    _write_json(_layout_root(loaded.case_dir) / SETTINGS_FILE, settings)
    _write_json(_layout_root(loaded.case_dir) / INVENTORY_FILE, inventory)
    _write_json(_layout_root(loaded.case_dir) / STRUCTURE_FILE, structure)
    _write_json(_layout_root(loaded.case_dir) / MAPPINGS_FILE, preserved_mappings)

    exhibits = structure.get("exhibits", [])
    return LayoutParseSummary(
        settings=settings,
        original_files=len(inventory["original_files"]),
        translation_files=len(inventory["translation_files"]),
        exhibits=len(exhibits),
        episodes=sum(
            1
            for exhibit in exhibits
            for episode in exhibit.get("episodes", [])
            if episode.get("kind") != "direct"
        ),
        documents=sum(
            len(episode.get("documents", []))
            for exhibit in exhibits
            for episode in exhibit.get("episodes", [])
        ),
    )


def update_layout_settings(case_id: str, **changes: str) -> dict[str, str]:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    settings = _load_settings(loaded.case_dir)
    for key, value in changes.items():
        if key in settings:
            settings[key] = value.strip()
    _write_json(_layout_root(loaded.case_dir) / SETTINGS_FILE, settings)
    return settings


def save_layout_structure(case_id: str, data: dict[str, str]) -> None:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    structure = _load_structure(loaded.case_dir)
    exhibits = structure.get("exhibits", [])
    seen_numbers: set[str] = set()
    next_fallback = 1
    for exhibit in exhibits:
        exhibit_id = exhibit.get("id", "")
        raw_number = data.get(f"exhibit_number_{exhibit_id}", "").strip()
        while str(next_fallback) in seen_numbers:
            next_fallback += 1
        candidate = raw_number or str(next_fallback)
        if candidate in seen_numbers:
            raise ValueError(f"Duplicate exhibit number: {candidate}")
        seen_numbers.add(candidate)
        exhibit["number"] = candidate
        exhibit["title"] = data.get(f"exhibit_title_{exhibit_id}", "").strip() or exhibit.get("title", "")
        for episode in exhibit.get("episodes", []):
            episode_id = episode.get("id", "")
            if episode.get("kind") != "direct":
                episode["title"] = (
                    data.get(f"episode_title_{episode_id}", "").strip() or episode.get("title", "")
                )
            for document in episode.get("documents", []):
                document_id = document.get("id", "")
                document["title"] = (
                    data.get(f"document_title_{document_id}", "").strip() or document.get("title", "")
                )
    _write_json(_layout_root(loaded.case_dir) / STRUCTURE_FILE, _renumber_structure(structure))


def add_mapping(case_id: str, document_id: str, kind: str, file_path: str) -> None:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    if kind not in {"original", "translation"}:
        raise ValueError(f"Unsupported mapping kind: {kind}")
    target = Path(file_path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise ValueError(f"File not found: {target}")
    mappings = _load_mappings(loaded.case_dir)
    entry = mappings.setdefault(document_id, {"original_paths": [], "translation_paths": []})
    key = "original_paths" if kind == "original" else "translation_paths"
    normalized = [str(Path(item).expanduser().resolve()) for item in entry.get(key, [])]
    if str(target) not in normalized:
        normalized.append(str(target))
    entry[key] = normalized
    _write_json(_layout_root(loaded.case_dir) / MAPPINGS_FILE, mappings)


def remove_mapping(case_id: str, document_id: str, kind: str, index: int) -> None:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    mappings = _load_mappings(loaded.case_dir)
    entry = mappings.setdefault(document_id, {"original_paths": [], "translation_paths": []})
    key = "original_paths" if kind == "original" else "translation_paths"
    items = list(entry.get(key, []))
    if 0 <= index < len(items):
        items.pop(index)
    entry[key] = items
    _write_json(_layout_root(loaded.case_dir) / MAPPINGS_FILE, mappings)


def save_layout_selection(case_id: str, selected_exhibits: list[str], selected_documents: list[str]) -> None:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    _write_json(
        _layout_root(loaded.case_dir) / SELECTION_FILE,
        {
            "selected_exhibits": selected_exhibits,
            "selected_documents": selected_documents,
        },
    )


def load_layout_selection(case_id: str) -> dict[str, list[str]]:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    path = _layout_root(loaded.case_dir) / SELECTION_FILE
    if not path.exists():
        return {"selected_exhibits": [], "selected_documents": []}
    return _read_json(path, {"selected_exhibits": [], "selected_documents": []})


def build_layout_preview(case_id: str) -> LayoutBuildSummary:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    status = load_layout_status(case_id)
    if not status.stage1_complete:
        raise ValueError("Stage 1 is incomplete. Parse the list and scan the folders first.")
    component_map = _render_separator_components(
        loaded.case_dir,
        _selected_structure(status.structure, None, None, include_unmapped=True),
    )
    preview_path = _layout_root(loaded.case_dir) / PREVIEW_PDF
    _merge_pdfs(component_map.values(), preview_path)
    return LayoutBuildSummary(
        pdf_path=preview_path,
        exhibits=status.exhibit_count,
        episodes=status.episode_count,
        documents=status.document_count,
        source_files=0,
    )


def build_layout_bundle(
    case_id: str,
    selected_exhibits: list[str],
    selected_documents: list[str],
) -> LayoutBuildSummary:
    loaded = load_case(case_id)
    _ensure_layout_case(loaded.config)
    status = load_layout_status(case_id)
    if not status.stage1_complete:
        raise ValueError("Stage 1 is incomplete. Parse the list and scan the folders first.")
    if not selected_exhibits and not selected_documents:
        raise ValueError("Select at least one exhibit or document to build.")
    filtered = _selected_structure(status.structure, selected_exhibits, selected_documents)
    selected_doc_ids = {
        document.get("id", "")
        for exhibit in filtered.get("exhibits", [])
        for episode in exhibit.get("episodes", [])
        for document in episode.get("documents", [])
    }
    for exhibit in filtered.get("exhibits", []):
        for episode in exhibit.get("episodes", []):
            for document in episode.get("documents", []):
                mapping = status.mappings.get(document.get("id", ""), {})
                original_paths = _existing_paths(mapping.get("original_paths", []))
                if not original_paths:
                    raise ValueError(
                        f"Document {document.get('number', document.get('id', ''))} is not linked to any original file."
                    )

    component_map = _render_separator_components(loaded.case_dir, filtered)
    merged_paths = [component_map["index"]]
    converted_root = _layout_root(loaded.case_dir) / CONVERTED_DIR
    converted_root.mkdir(parents=True, exist_ok=True)
    source_files = 0
    for exhibit in filtered.get("exhibits", []):
        merged_paths.append(component_map[f"exhibit:{exhibit.get('id', '')}"])
        for episode in exhibit.get("episodes", []):
            if episode.get("kind") != "direct":
                merged_paths.append(component_map[f"episode:{episode.get('id', '')}"])
            for document in episode.get("documents", []):
                merged_paths.append(component_map[f"document:{document.get('id', '')}"])
                mapping = status.mappings.get(document.get("id", ""), {})
                for kind in ("original_paths", "translation_paths"):
                    for offset, raw_path in enumerate(_existing_paths(mapping.get(kind, [])), start=1):
                        source_files += 1
                        merged_paths.append(
                            _prepare_pdf_source(
                                Path(raw_path),
                                converted_root / f"{source_files:04d}_{document.get('id', 'document')}_{kind}_{offset}.pdf",
                            )
                        )
    final_path = _layout_root(loaded.case_dir) / FINAL_PDF
    _merge_pdfs(merged_paths, final_path)
    return LayoutBuildSummary(
        pdf_path=final_path,
        exhibits=len(filtered.get("exhibits", [])),
        episodes=sum(
            1
            for exhibit in filtered.get("exhibits", [])
            for episode in exhibit.get("episodes", [])
            if episode.get("kind") != "direct"
        ),
        documents=len(selected_doc_ids),
        source_files=source_files,
    )


def _ensure_layout_case(config: dict[str, Any]) -> None:
    if str(config.get("task_type", "")) != "document_layout":
        raise ValueError("This action is only available for document layout cases.")


def _layout_root(case_dir: Path) -> Path:
    root = case_dir / LAYOUT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_settings(case_dir: Path) -> dict[str, str]:
    return _read_json(
        _layout_root(case_dir) / SETTINGS_FILE,
        {
            "originals_dir": "",
            "translations_dir": "",
            "list_document_path": "",
        },
    )


def _load_inventory(case_dir: Path) -> dict[str, list[dict[str, str]]]:
    return _read_json(_layout_root(case_dir) / INVENTORY_FILE, {"original_files": [], "translation_files": []})


def _load_structure(case_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return _read_json(_layout_root(case_dir) / STRUCTURE_FILE, {"exhibits": []})


def _load_mappings(case_dir: Path) -> dict[str, dict[str, list[str]]]:
    raw = _read_json(_layout_root(case_dir) / MAPPINGS_FILE, {})
    return {
        str(key): {
            "original_paths": [str(item) for item in value.get("original_paths", [])],
            "translation_paths": [str(item) for item in value.get("translation_paths", [])],
        }
        for key, value in raw.items()
        if isinstance(value, dict)
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scan_inventory_group(root: Path | None, group: str) -> list[dict[str, str]]:
    if root is None:
        return []
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_office_temporary_file(path):
            continue
        relative_path = path.relative_to(root).as_posix()
        files.append(
            {
                "id": f"{group}:{relative_path}",
                "path": str(path.resolve()),
                "relative_path": relative_path,
                "name": path.name,
                "stem": path.stem,
                "extension": path.suffix.lower(),
                "size": str(path.stat().st_size),
            }
        )
    return files


def _parse_structure_from_document(path: Path) -> dict[str, list[dict[str, Any]]]:
    lines = _read_structure_lines(path)
    exhibits = _parse_exhibit_blocks(lines)
    if not exhibits:
        raise ValueError("Could not parse any Exhibit blocks from the supplied list document.")
    return {"exhibits": exhibits}


def _read_structure_lines(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _read_docx_lines(path)
    if suffix == ".pdf":
        return _read_pdf_lines(path)
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def _read_docx_lines(path: Path) -> list[str]:
    try:
        from docx import Document  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing python-docx for DOCX exhibit list parsing.") from exc

    document = Document(str(path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)
        xml = paragraph._element.xml
        if 'w:type="page"' in xml or "w:type='page'" in xml:
            lines.append(PAGE_BREAK)
    return lines


def _read_pdf_lines(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing pypdf for PDF exhibit list parsing.") from exc

    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(text.splitlines())
        lines.append(PAGE_BREAK)
    return lines


def _parse_exhibit_blocks(lines: list[str]) -> list[dict[str, Any]]:
    exhibits: list[dict[str, Any]] = []
    current_heading = ""
    current_number = ""
    block_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^exhibit\s+([A-Za-z0-9-]+)\s*[:.\-]?\s*(.*)$", line, flags=re.IGNORECASE)
        if match:
            if current_heading:
                exhibits.append(_build_exhibit(current_number, current_heading, block_lines, len(exhibits) + 1))
            current_number = match.group(1).strip()
            current_heading = _clean_text(match.group(2).strip()) or f"Exhibit {current_number}"
            block_lines = []
            continue
        if current_heading:
            block_lines.append(line)
    if current_heading:
        exhibits.append(_build_exhibit(current_number, current_heading, block_lines, len(exhibits) + 1))
    return exhibits


def _build_exhibit(number: str, title: str, block_lines: list[str], exhibit_index: int) -> dict[str, Any]:
    direct_documents: list[str] = []
    episodes: list[dict[str, Any]] = []
    pending_title = ""
    in_parentheses = False
    buffered_documents: list[str] = []

    def commit_documents() -> None:
        nonlocal pending_title, buffered_documents, episodes, direct_documents
        documents = [_clean_text(item) for item in buffered_documents if _clean_text(item)]
        buffered_documents = []
        if not documents:
            return
        if pending_title:
            episodes.append(
                {
                    "id": f"episode_{exhibit_index:03d}_{len(episodes) + 1:03d}",
                    "kind": "episode",
                    "title": pending_title,
                    "number": "",
                    "documents": [
                        {
                            "id": f"doc_{exhibit_index:03d}_{len(episodes) + 1:03d}_{offset:03d}",
                            "title": document_title,
                            "number": "",
                        }
                        for offset, document_title in enumerate(documents, start=1)
                    ],
                }
            )
            pending_title = ""
        else:
            direct_documents.extend(documents)

    for raw_line in block_lines:
        line = raw_line.strip()
        if not line or line == PAGE_BREAK:
            continue
        if in_parentheses:
            if ")" in line:
                before, after = line.split(")", 1)
                if before.strip():
                    buffered_documents.append(before.strip())
                in_parentheses = False
                commit_documents()
                if after.strip():
                    pending_title = _clean_text(after)
            else:
                buffered_documents.append(line)
            continue
        if "(" in line:
            before, after = line.split("(", 1)
            if before.strip():
                pending_title = _clean_text(before)
            if ")" in after:
                inside, tail = after.split(")", 1)
                if inside.strip():
                    buffered_documents.extend(part for part in inside.splitlines() if part.strip())
                commit_documents()
                if tail.strip():
                    pending_title = _clean_text(tail)
            else:
                if after.strip():
                    buffered_documents.extend(part for part in after.splitlines() if part.strip())
                in_parentheses = True
            continue
        pending_title = _clean_text(line)

    if buffered_documents:
        commit_documents()

    if not episodes and not direct_documents:
        direct_documents = [_clean_text(line) for line in block_lines if _clean_text(line)]

    if direct_documents:
        episodes.insert(
            0,
            {
                "id": f"episode_{exhibit_index:03d}_direct",
                "kind": "direct",
                "title": "",
                "number": "",
                "documents": [
                    {
                        "id": f"doc_{exhibit_index:03d}_direct_{offset:03d}",
                        "title": document_title,
                        "number": "",
                    }
                    for offset, document_title in enumerate(direct_documents, start=1)
                ],
            },
        )

    return {
        "id": f"exhibit_{exhibit_index:03d}",
        "number": number or str(exhibit_index),
        "title": title,
        "episodes": episodes,
    }


def _clean_text(value: str) -> str:
    text = value.replace("\u00a0", " ").strip()
    text = re.sub(r"^\s*[-*•]+\s*", "", text)
    text = re.sub(r"^\s*(?:\d+(?:[.\-]\d+)+|\d+[.)])\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -")


def _renumber_structure(structure: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    exhibits = structure.get("exhibits", [])
    for exhibit_index, exhibit in enumerate(exhibits, start=1):
        if not str(exhibit.get("number", "")).strip():
            exhibit["number"] = str(exhibit_index)
        exhibit_number = str(exhibit.get("number", "")).strip()
        episode_counter = 1
        direct_counter = 1
        for episode in exhibit.get("episodes", []):
            documents = episode.get("documents", [])
            if episode.get("kind") == "direct":
                episode["number"] = ""
                for document in documents:
                    document["number"] = f"{exhibit_number}.{direct_counter}"
                    direct_counter += 1
            else:
                episode["number"] = f"{exhibit_number}.{episode_counter}"
                for document_index, document in enumerate(documents, start=1):
                    document["number"] = f"{episode['number']}.{document_index}"
                episode_counter += 1
    return structure


def _preserve_mappings(
    previous_structure: dict[str, list[dict[str, Any]]],
    previous_mappings: dict[str, dict[str, list[str]]],
    next_structure: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, list[str]]]:
    key_to_mapping: dict[str, dict[str, list[str]]] = {}
    for exhibit in previous_structure.get("exhibits", []):
        for episode in exhibit.get("episodes", []):
            for document in episode.get("documents", []):
                document_id = document.get("id", "")
                if not document_id:
                    continue
                semantic_key = _mapping_key(exhibit, episode, document)
                mapping = previous_mappings.get(document_id)
                if mapping:
                    key_to_mapping[semantic_key] = mapping
    preserved: dict[str, dict[str, list[str]]] = {}
    for exhibit in next_structure.get("exhibits", []):
        for episode in exhibit.get("episodes", []):
            for document in episode.get("documents", []):
                semantic_key = _mapping_key(exhibit, episode, document)
                mapping = key_to_mapping.get(semantic_key, {"original_paths": [], "translation_paths": []})
                preserved[document.get("id", "")] = {
                    "original_paths": _existing_paths(mapping.get("original_paths", [])),
                    "translation_paths": _existing_paths(mapping.get("translation_paths", [])),
                }
    return preserved


def _mapping_key(exhibit: dict[str, Any], episode: dict[str, Any], document: dict[str, Any]) -> str:
    return " | ".join(
        [
            _normalize_key(str(exhibit.get("title", ""))),
            _normalize_key(str(episode.get("title", ""))),
            _normalize_key(str(document.get("title", ""))),
        ]
    )


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _selected_structure(
    structure: dict[str, list[dict[str, Any]]],
    selected_exhibits: list[str] | None,
    selected_documents: list[str] | None,
    *,
    include_unmapped: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    exhibit_filter = set(selected_exhibits or [])
    document_filter = set(selected_documents or [])
    if not exhibit_filter and not document_filter:
        return json.loads(json.dumps(structure))

    filtered_exhibits: list[dict[str, Any]] = []
    for exhibit in structure.get("exhibits", []):
        include_exhibit = exhibit.get("number", "") in exhibit_filter
        next_exhibit = {key: value for key, value in exhibit.items() if key != "episodes"}
        next_episodes: list[dict[str, Any]] = []
        for episode in exhibit.get("episodes", []):
            next_episode = {key: value for key, value in episode.items() if key != "documents"}
            documents = []
            for document in episode.get("documents", []):
                document_id = document.get("id", "")
                if include_exhibit or document_id in document_filter or include_unmapped:
                    documents.append(dict(document))
            if documents:
                next_episode["documents"] = documents
                next_episodes.append(next_episode)
        if next_episodes:
            next_exhibit["episodes"] = next_episodes
            filtered_exhibits.append(next_exhibit)
    return {"exhibits": filtered_exhibits}


def _render_separator_components(case_dir: Path, structure: dict[str, list[dict[str, Any]]]) -> dict[str, Path]:
    components_root = _layout_root(case_dir) / COMPONENTS_DIR
    if components_root.exists():
        for old_file in components_root.glob("*.pdf"):
            old_file.unlink()
    components_root.mkdir(parents=True, exist_ok=True)
    components = _component_definitions(structure)
    paths: dict[str, Path] = {}
    for index, component in enumerate(components, start=1):
        target = components_root / f"{index:04d}_{component['kind']}_{component['id']}.pdf"
        _render_component_pdf(component, target)
        paths[_component_key(component)] = target
    return paths


def _component_definitions(structure: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    exhibits = structure.get("exhibits", [])
    components.append(
        {
            "id": "index",
            "kind": "index",
            "title": "List of Exhibits",
            "exhibits": exhibits,
        }
    )
    for exhibit in exhibits:
        components.append(
            {
                "id": exhibit.get("id", ""),
                "kind": "exhibit",
                "title": f"Exhibit {exhibit.get('number', '')} {exhibit.get('title', '')}".strip(),
                "subtitle": "Within this Exhibit, the following documents are attached:",
                "exhibit": exhibit,
            }
        )
        for episode in exhibit.get("episodes", []):
            if episode.get("kind") != "direct":
                components.append(
                    {
                        "id": episode.get("id", ""),
                        "kind": "episode",
                        "title": f"{episode.get('number', '')} {episode.get('title', '')}".strip(),
                        "parent_title": f"Exhibit {exhibit.get('number', '')} {exhibit.get('title', '')}".strip(),
                        "subtitle": "Within this section, the following documents are attached:",
                        "episode": episode,
                    }
                )
            for document in episode.get("documents", []):
                components.append(
                    {
                        "id": document.get("id", ""),
                        "kind": "document",
                        "title": f"{document.get('number', '')} {document.get('title', '')}".strip(),
                        "parent_title": _document_parent_title(exhibit, episode),
                    }
                )
    return components


def _component_key(component: dict[str, Any]) -> str:
    if component["kind"] == "index":
        return "index"
    return f"{component['kind']}:{component['id']}"


def _document_parent_title(exhibit: dict[str, Any], episode: dict[str, Any]) -> str:
    exhibit_title = f"Exhibit {exhibit.get('number', '')} {exhibit.get('title', '')}".strip()
    if episode.get("kind") == "direct":
        return exhibit_title
    return f"{exhibit_title} / {episode.get('number', '')} {episode.get('title', '')}".strip()


def _render_component_pdf(component: dict[str, Any], target: Path) -> None:
    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.platypus import Paragraph  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing reportlab for document layout rendering.") from exc

    font_name = _register_pdf_font(pdfmetrics, TTFont)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="LayoutMuted",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#5f6b7a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="LayoutList",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor("#5b6573"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="LayoutEpisode",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            leftIndent=24,
            textColor=colors.HexColor("#4a5565"),
        )
    )

    page_width, page_height = A4
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(target), pagesize=A4)
    margin_x = 70
    top_y = page_height - 80
    bottom_y = 90

    def write_wrapped(lines: list[tuple[str, str]], start_y: float) -> None:
        y = start_y
        for style_name, text in lines:
            paragraph = Paragraph(_escape_html(text), styles[style_name])
            available_height = y - bottom_y
            needed_width, needed_height = paragraph.wrap(page_width - 2 * margin_x, available_height)
            if needed_height > available_height:
                _draw_footer(pdf, font_name, margin_x, 58)
                pdf.showPage()
                y = top_y
                needed_width, needed_height = paragraph.wrap(page_width - 2 * margin_x, y - bottom_y)
            paragraph.drawOn(pdf, margin_x, y - needed_height)
            y -= needed_height + 8
        _draw_footer(pdf, font_name, margin_x, 58)

    if component["kind"] == "index":
        _draw_title(pdf, component["title"], font_name, page_width, top_y - 20)
        lines: list[tuple[str, str]] = []
        for exhibit in component.get("exhibits", []):
            lines.append(("LayoutList", f"Exhibit {exhibit.get('number', '')} {exhibit.get('title', '')}".strip()))
            for episode in exhibit.get("episodes", []):
                if episode.get("kind") != "direct":
                    lines.append(("LayoutEpisode", f"{episode.get('number', '')} {episode.get('title', '')}".strip()))
        write_wrapped(lines, top_y - 80)
    elif component["kind"] == "exhibit":
        _draw_title(pdf, component["title"], font_name, page_width, top_y)
        _draw_subtitle(pdf, component["subtitle"], font_name, page_width, top_y - 34)
        lines = []
        exhibit = component["exhibit"]
        for episode in exhibit.get("episodes", []):
            if episode.get("kind") != "direct":
                lines.append(("LayoutEpisode", f"{episode.get('number', '')} {episode.get('title', '')}".strip()))
            for document in episode.get("documents", []):
                lines.append(("LayoutList", f"{document.get('number', '')} {document.get('title', '')}".strip()))
        write_wrapped(lines, top_y - 95)
    elif component["kind"] == "episode":
        _draw_muted_header(pdf, component["parent_title"], font_name, margin_x, top_y + 10)
        _draw_title(pdf, component["title"], font_name, page_width, top_y - 10)
        _draw_subtitle(pdf, component["subtitle"], font_name, page_width, top_y - 44)
        lines = [
            ("LayoutList", f"{document.get('number', '')} {document.get('title', '')}".strip())
            for document in component["episode"].get("documents", [])
        ]
        write_wrapped(lines, top_y - 102)
    else:
        _draw_muted_header(pdf, component["parent_title"], font_name, margin_x, top_y + 25)
        _draw_title(pdf, component["title"], font_name, page_width, top_y - 10)
        _draw_footer(pdf, font_name, margin_x, 58)

    pdf.save()


def _draw_title(pdf: Any, title: str, font_name: str, page_width: float, y: float) -> None:
    pdf.setFont(font_name, 23)
    pdf.setFillColorRGB(0.16, 0.18, 0.2)
    pdf.drawCentredString(page_width / 2, y, title)


def _draw_subtitle(pdf: Any, subtitle: str, font_name: str, page_width: float, y: float) -> None:
    pdf.setFont(font_name, 11)
    pdf.setFillColorRGB(0.38, 0.42, 0.47)
    pdf.drawCentredString(page_width / 2, y, subtitle)
    width = pdf.stringWidth(subtitle, font_name, 11)
    pdf.line((page_width - width) / 2, y - 2, (page_width + width) / 2, y - 2)


def _draw_muted_header(pdf: Any, text: str, font_name: str, margin_x: float, y: float) -> None:
    pdf.setFont(font_name, 10)
    pdf.setFillColorRGB(0.47, 0.51, 0.56)
    pdf.drawString(margin_x, y, text)


def _draw_footer(pdf: Any, font_name: str, margin_x: float, y: float) -> None:
    footer = "Please see next page"
    pdf.setFont(font_name, 11)
    pdf.setFillColorRGB(0.38, 0.42, 0.47)
    pdf.drawString(margin_x, y, footer)
    pdf.line(margin_x, y - 2, margin_x + pdf.stringWidth(footer, font_name, 11), y - 2)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _merge_pdfs(paths: Iterable[Path], target: Path) -> None:
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing pypdf for PDF assembly.") from exc

    writer = PdfWriter()
    for path in paths:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        writer.write(handle)


def _prepare_pdf_source(source_path: Path, target_pdf: Path) -> Path:
    suffix = source_path.suffix.lower()
    if suffix in PDF_FILE_EXTENSIONS:
        return source_path
    if suffix in IMAGE_FILE_EXTENSIONS:
        _image_to_pdf(source_path, target_pdf)
        return target_pdf
    if suffix in TEXT_FILE_EXTENSIONS:
        _text_to_pdf(source_path.read_text(encoding="utf-8-sig", errors="replace"), source_path.name, target_pdf)
        return target_pdf
    if suffix == ".docx":
        if _try_office_to_pdf(source_path, target_pdf):
            return target_pdf
        _text_to_pdf(extract_docx_text(source_path), source_path.name, target_pdf)
        return target_pdf
    if suffix in OFFICE_FILE_EXTENSIONS:
        if _try_office_to_pdf(source_path, target_pdf):
            return target_pdf
        raise ValueError(f"Could not convert Office document to PDF: {source_path}")
    raise ValueError(f"Unsupported source file type for PDF assembly: {source_path.suffix or '[no extension]'}")


def _image_to_pdf(source_path: Path, target_pdf: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.lib.utils import ImageReader  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing reportlab for image conversion.") from exc

    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin = 0.5 * inch
    pdf = canvas.Canvas(str(target_pdf), pagesize=A4)
    image = ImageReader(str(source_path))
    width, height = image.getSize()
    scale = min((page_width - 2 * margin) / width, (page_height - 2 * margin) / height)
    draw_width = width * scale
    draw_height = height * scale
    pdf.drawImage(
        image,
        (page_width - draw_width) / 2,
        (page_height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
    )
    pdf.showPage()
    pdf.save()


def _text_to_pdf(text: str, title: str, target_pdf: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import inch  # type: ignore
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing reportlab for text conversion.") from exc

    font_name = _register_pdf_font(pdfmetrics, TTFont)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="LayoutSource",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=13,
        )
    )
    story: list[Any] = [Paragraph(_escape_html(title), styles["Title"]), Spacer(1, 0.15 * inch)]
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if stripped:
            story.append(Paragraph(_escape_html(stripped), styles["LayoutSource"]))
            story.append(Spacer(1, 0.05 * inch))
    if len(story) == 2:
        story.append(Paragraph("[empty file]", styles["LayoutSource"]))
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(target_pdf),
        pagesize=A4,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=title,
    )
    document.build(story)


def _try_office_to_pdf(source_path: Path, target_pdf: Path) -> bool:
    executable = _find_soffice()
    if executable is None:
        return False
    output_dir = target_pdf.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(source_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    produced = output_dir / f"{source_path.stem}.pdf"
    if result.returncode != 0 or not produced.exists():
        return False
    if produced.resolve() != target_pdf.resolve():
        if target_pdf.exists():
            target_pdf.unlink()
        produced.replace(target_pdf)
    return True


def _find_soffice() -> str | None:
    on_path = shutil.which("soffice")
    if on_path:
        return on_path
    candidates = [
        "C:/Program Files/LibreOffice/program/soffice.exe",
        "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def _existing_paths(paths: Iterable[str]) -> list[str]:
    return [str(Path(path).expanduser().resolve()) for path in paths if Path(path).expanduser().exists()]
