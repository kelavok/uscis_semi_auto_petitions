from __future__ import annotations

import argparse

from .bundle_workflow import (
    build_evidence_bundle,
    build_bundle_plan,
    build_exhibit_index,
    build_final_filing_pdf,
    generate_separator_pages,
    refresh_layout_indexes,
    render_separator_pdfs,
    sync_layout_indexes_from_memo,
)
from .cli_support import add_case_argument, configure_console


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.bundle",
        description="Deterministic evidence bundle assembly (no LLM calls).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Validate indexes and assemble one evidence bundle")
    add_case_argument(build)
    build.add_argument("--dry-run", action="store_true", help="Validate and report without creating a PDF")

    final_filing = commands.add_parser(
        "final-filing",
        help="Resolve memo PAGE placeholders and merge the memo with the evidence bundle",
    )
    add_case_argument(final_filing)
    final_filing.add_argument(
        "--memo",
        default="",
        help="Optional DOCX memo path; defaults to final_memo/working_memo.docx",
    )

    build_index = commands.add_parser("build-index", help="Build exhibit_index.csv from document_index.csv")
    add_case_argument(build_index)

    refresh_indexes = commands.add_parser(
        "refresh-indexes",
        help="Rescan sources and derive Exhibit assignments from validated LLM outputs",
    )
    add_case_argument(refresh_indexes)

    sync_from_memo = commands.add_parser(
        "sync-indexes-from-memo",
        help="Replace Exhibit/document ordering from the working memo INDEX section",
    )
    add_case_argument(sync_from_memo)
    sync_from_memo.add_argument(
        "--memo",
        default="",
        help="Optional DOCX memo path; defaults to final_memo/working_memo.docx",
    )

    separators = commands.add_parser("separators", help="Generate markdown separator pages from indexes")
    add_case_argument(separators)

    separator_pdfs = commands.add_parser("separator-pdfs", help="Render generated markdown separator pages to PDF")
    add_case_argument(separator_pdfs)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)
    if args.command == "build":
        if args.dry_run:
            summary = build_bundle_plan(args.case_id)
            print(f"Total plan items: {summary.total_items}")
            print(f"Ready items: {summary.ready_items}")
            print(f"Missing items: {summary.missing_items}")
            print(f"Unsupported items: {summary.unsupported_items}")
            print(f"Separator PDFs: {summary.separator_pdfs}")
            print(f"Source documents: {summary.source_documents}")
            print(f"Plan CSV: {summary.plan_csv_path}")
            print(f"Plan report: {summary.plan_md_path}")
            return 0
        summary = build_evidence_bundle(args.case_id)
        print(f"Final PDF: {summary.final_pdf_path}")
        print(f"Plan CSV: {summary.plan_csv_path}")
        print(f"Merged items: {summary.merged_items}")
        print(f"Converted items: {summary.converted_items}")
        print(f"Skipped items: {summary.skipped_items}")
        return 0
    if args.command == "final-filing":
        summary = build_final_filing_pdf(args.case_id, memo_docx_path=args.memo)
        print(f"Final filing PDF: {summary.final_pdf_path}")
        print(f"Numbered memo DOCX: {summary.numbered_memo_docx_path}")
        print(f"Numbered memo PDF: {summary.numbered_memo_pdf_path}")
        print(f"Evidence bundle PDF: {summary.evidence_bundle_pdf_path}")
        print(f"Report: {summary.report_path}")
        print(f"Memo pages: {summary.memo_pages}")
        print(f"Bundle pages: {summary.bundle_pages}")
        print(f"Final pages: {summary.final_pages}")
        print(
            f"PAGE placeholders: {summary.placeholders_resolved}/"
            f"{summary.placeholders_seen} resolved"
        )
        print(f"Unresolved placeholders: {summary.placeholders_unresolved}")
        return 0
    if args.command == "build-index":
        summary = build_exhibit_index(args.case_id)
        print(f"Documents seen: {summary.documents_seen}")
        print(f"Documents with exhibit_number: {summary.documents_with_exhibit_number}")
        print(f"Documents without exhibit_number: {summary.documents_without_exhibit_number}")
        print(f"Exhibits created: {summary.exhibits_created}")
        print(f"Exhibits updated: {summary.exhibits_updated}")
        print(f"Locked exhibits skipped: {summary.locked_exhibits_skipped}")
        print(f"Document bundle orders written: {summary.document_orders_written}")
        print(f"Document index: {summary.document_index_path}")
        print(f"Exhibit index: {summary.exhibit_index_path}")
        print("Bundle order rule: original first, then translation.")
        return 0
    if args.command == "refresh-indexes":
        summary = refresh_layout_indexes(args.case_id)
        print(f"Source files scanned: {summary.scanned_files}")
        print(f"Auxiliary index rows removed: {summary.auxiliary_rows_removed}")
        print(f"Replacement PDFs rebound: {summary.replacement_documents_rebound}")
        print(
            f"Used documents assigned: {summary.status.assigned_used_documents}/"
            f"{summary.status.unique_used_documents}"
        )
        print(f"Exhibits: {summary.status.exhibit_count}")
        print(f"Stale document IDs: {', '.join(summary.status.stale_document_ids) or '[none]'}")
        print(f"Assignment conflicts: {len(summary.status.assignment_conflicts)}")
        print(f"Unsupported documents: {len(summary.status.unsupported_documents)}")
        return 0
    if args.command == "sync-indexes-from-memo":
        summary = sync_layout_indexes_from_memo(args.case_id, memo_docx_path=args.memo)
        print(f"Memo: {summary.memo_docx_path}")
        print(f"Exhibits: {summary.exhibits_seen}")
        print(f"Episodes: {summary.episodes_seen}")
        print(f"Documents matched: {summary.documents_matched}/{summary.documents_seen}")
        print(f"Document index: {summary.document_index_path}")
        print(f"Exhibit index: {summary.exhibit_index_path}")
        if summary.unmatched_titles:
            print("Unmatched:")
            for title in summary.unmatched_titles:
                print(f"- {title}")
        return 0
    if args.command == "separators":
        summary = generate_separator_pages(args.case_id)
        print(f"Exhibits seen: {summary.exhibits_seen}")
        print(f"Exhibit separator pages written: {summary.exhibit_pages_written}")
        print(f"Document separator pages written: {summary.document_pages_written}")
        print(f"Missing document IDs: {summary.missing_document_ids}")
        print(f"Separators dir: {summary.separators_dir}")
        print(f"Manifest: {summary.manifest_path}")
        return 0
    if args.command == "separator-pdfs":
        summary = render_separator_pdfs(args.case_id)
        print(f"Markdown separator files seen: {summary.markdown_files_seen}")
        print(f"PDF separator pages written: {summary.pdf_pages_written}")
        print(f"Source dir: {summary.source_dir}")
        print(f"Output dir: {summary.output_dir}")
        print(f"Manifest: {summary.manifest_path}")
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
