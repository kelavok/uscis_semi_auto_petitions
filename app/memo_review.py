from __future__ import annotations

import difflib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from .bundle_workflow import (
    _match_memo_index_documents,
    _parse_memo_index_docx,
    sync_layout_indexes_from_memo,
)
from .workflow import _case_path_value, load_case


REVIEW_CANDIDATE = "review_candidate.docx"
REVIEW_ACCEPTED = "accepted_reviewed_memo.docx"
REVIEW_REPORT = "reviewed_memo_validation.json"
REVIEW_STATE = "reviewed_memo_state.json"


@dataclass(frozen=True)
class ReviewedMemoReport:
    candidate_path: str
    source_path: str
    checked_at: str
    index_parsed: bool
    exhibits_seen: int
    documents_seen: int
    documents_matched: int
    citations_seen: int
    unknown_index_items: tuple[str, ...]
    missing_indexed_documents: tuple[str, ...]
    unknown_citations: tuple[str, ...]
    structural_warnings: tuple[str, ...]
    accepted: bool = False

    @property
    def warnings(self) -> tuple[str, ...]:
        return (
            *self.structural_warnings,
            *self.unknown_index_items,
            *self.missing_indexed_documents,
            *self.unknown_citations,
        )


def validate_reviewed_memo(case_id: str, source_path: str) -> ReviewedMemoReport:
    loaded = load_case(case_id)
    source = _resolve_user_docx_path(source_path)
    if not source.exists() or not source.is_file():
        raise ValueError(f"Corrected memorandum was not found: {source}")
    if source.suffix.casefold() != ".docx":
        raise ValueError("The corrected memorandum must be a DOCX file.")

    final_root = loaded.case_dir / _case_path_value(loaded.config, "final_memo")
    final_root.mkdir(parents=True, exist_ok=True)
    candidate = final_root / REVIEW_CANDIDATE
    if source.resolve() != candidate.resolve():
        shutil.copy2(source, candidate)

    document_rows = _read_document_index(
        loaded.case_dir / _case_path_value(loaded.config, "document_index")
    )
    warnings: list[str] = []
    unknown_items: list[str] = []
    missing_documents: list[str] = []
    unknown_citations: list[str] = []
    exhibits_seen = documents_seen = documents_matched = citations_seen = 0
    parsed_ok = False
    parsed: dict[str, list[dict[str, str]]] = {"exhibits": [], "episodes": [], "documents": []}
    matches: list[dict[str, str]] = []

    try:
        parsed = _parse_memo_index_docx(candidate)
        parsed_ok = True
        exhibits_seen = len(parsed["exhibits"])
        documents_seen = len(parsed["documents"])
        matches, unknown_items = _match_memo_index_documents(parsed["documents"], document_rows)
        documents_matched = len(matches)
    except (Exception, SystemExit) as exc:  # soft validation by design
        warnings.append(str(exc))

    previously_indexed = {
        row.get("document_id", "")
        for row in document_rows
        if row.get("document_id", "") and row.get("exhibit_number", "").strip()
    }
    matched_ids = {item.get("document_id", "") for item in matches}
    rows_by_id = {row.get("document_id", ""): row for row in document_rows}
    for document_id in sorted(previously_indexed - matched_ids):
        row = rows_by_id.get(document_id, {})
        title = row.get("display_title", "") or row.get("original_file_name", "")
        missing_documents.append(f"Missing from corrected INDEX: {document_id} — {title}")

    if parsed_ok:
        citations = _extract_memo_citations(candidate)
        citations_seen = len(citations)
        known_by_number = {item.get("number", ""): item for item in parsed["documents"]}
        for citation in citations:
            known = known_by_number.get(citation["number"])
            if not known:
                unknown_citations.append(
                    f"Unrecognized citation {citation['number']}: {citation['title']}"
                )
                continue
            if citation["exhibit"] != known.get("exhibit_number", ""):
                unknown_citations.append(
                    f"Citation {citation['number']} names Exhibit {citation['exhibit']}, "
                    f"but the corrected INDEX places it in Exhibit {known.get('exhibit_number', '')}."
                )
                continue
            cited_title = _normalize_title(citation["title"])
            indexed_title = _normalize_title(known.get("display_title", "") or known.get("title", ""))
            similarity = difflib.SequenceMatcher(None, cited_title, indexed_title).ratio()
            if (
                cited_title
                and indexed_title
                and cited_title not in indexed_title
                and indexed_title not in cited_title
                and similarity < 0.55
            ):
                unknown_citations.append(
                    f"Citation {citation['number']} has an unrecognized document title: "
                    f"{citation['title']}"
                )

    report = ReviewedMemoReport(
        candidate_path=str(candidate),
        source_path=str(source),
        checked_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        index_parsed=parsed_ok,
        exhibits_seen=exhibits_seen,
        documents_seen=documents_seen,
        documents_matched=documents_matched,
        citations_seen=citations_seen,
        unknown_index_items=tuple(unknown_items),
        missing_indexed_documents=tuple(missing_documents),
        unknown_citations=tuple(unknown_citations),
        structural_warnings=tuple(warnings),
    )
    _write_report(final_root / REVIEW_REPORT, report)
    return report


def accept_reviewed_memo(case_id: str) -> ReviewedMemoReport:
    loaded = load_case(case_id)
    final_root = loaded.case_dir / _case_path_value(loaded.config, "final_memo")
    candidate = final_root / REVIEW_CANDIDATE
    if not candidate.exists():
        raise ValueError("Upload and validate a corrected memorandum first.")
    report = load_reviewed_memo_report(case_id)
    if report is None:
        raise ValueError("Validate the corrected memorandum before accepting it.")

    working = final_root / "working_memo.docx"
    if working.exists():
        backup_root = final_root / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            working,
            backup_root / f"working_memo_before_review_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.docx",
        )
    accepted_path = final_root / REVIEW_ACCEPTED
    shutil.copy2(candidate, accepted_path)
    shutil.copy2(candidate, working)

    if report.index_parsed:
        sync_layout_indexes_from_memo(
            case_id,
            memo_docx_path=str(working),
            allow_unmatched=True,
        )

    accepted = ReviewedMemoReport(**{**asdict(report), "accepted": True})
    _write_report(final_root / REVIEW_REPORT, accepted)
    (final_root / REVIEW_STATE).write_text(
        json.dumps(
            {
                "accepted": True,
                "accepted_path": str(accepted_path),
                "accepted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return accepted


def load_reviewed_memo_report(case_id: str) -> ReviewedMemoReport | None:
    loaded = load_case(case_id)
    path = _review_root(loaded) / REVIEW_REPORT
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return ReviewedMemoReport(
            candidate_path=str(data.get("candidate_path", "")),
            source_path=str(data.get("source_path", "")),
            checked_at=str(data.get("checked_at", "")),
            index_parsed=bool(data.get("index_parsed", False)),
            exhibits_seen=int(data.get("exhibits_seen", 0) or 0),
            documents_seen=int(data.get("documents_seen", 0) or 0),
            documents_matched=int(data.get("documents_matched", 0) or 0),
            citations_seen=int(data.get("citations_seen", 0) or 0),
            unknown_index_items=tuple(data.get("unknown_index_items", [])),
            missing_indexed_documents=tuple(data.get("missing_indexed_documents", [])),
            unknown_citations=tuple(data.get("unknown_citations", [])),
            structural_warnings=tuple(data.get("structural_warnings", [])),
            accepted=bool(data.get("accepted", False)),
        )
    except (OSError, ValueError, TypeError):
        return None


def accepted_reviewed_memo(case_id: str) -> Path | None:
    loaded = load_case(case_id)
    final_root = _review_root(loaded)
    state = final_root / REVIEW_STATE
    accepted = final_root / REVIEW_ACCEPTED
    if not state.exists() or not accepted.exists():
        return None
    try:
        data = json.loads(state.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return None
    return accepted if data.get("accepted") is True else None


def _resolve_user_docx_path(value: str) -> Path:
    cleaned = value.strip().strip('"').strip("'")
    if cleaned.casefold().startswith("file:"):
        parsed = urlparse(cleaned)
        cleaned = unquote(parsed.path)
        if parsed.netloc:
            cleaned = f"//{parsed.netloc}{cleaned}"
        if re.match(r"^/[A-Za-z]:/", cleaned):
            cleaned = cleaned[1:]
    if not cleaned:
        raise ValueError("Choose a corrected memorandum DOCX or paste its local path.")
    return Path(cleaned).expanduser().resolve()


def _read_document_index(path: Path) -> list[dict[str, str]]:
    import csv

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _extract_memo_citations(path: Path) -> list[dict[str, str]]:
    from docx import Document  # type: ignore

    text = "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)
    pattern = re.compile(
        r"Exhibit\s+(?P<exhibit>[^,;()]+),\s*page\s+PAGE:\s*"
        r"(?P<number>\d+(?:\.\d+){1,3})\s*-\s*(?P<title>[^;()]+)",
        flags=re.IGNORECASE,
    )
    return [
        {key: value.strip().rstrip(".") for key, value in match.groupdict().items()}
        for match in pattern.finditer(text)
    ]


def _write_report(path: Path, report: ReviewedMemoReport) -> None:
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize_title(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _review_root(loaded: object) -> Path:
    config = getattr(loaded, "config")
    case_dir = getattr(loaded, "case_dir")
    paths = config.get("paths", {}) if isinstance(config, dict) else {}
    relative = paths.get("final_memo", "final_memo") if isinstance(paths, dict) else "final_memo"
    return case_dir / str(relative)
