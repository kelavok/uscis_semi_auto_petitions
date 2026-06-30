from __future__ import annotations

import argparse

from .cli_support import (
    add_case_argument,
    configure_console,
    create_case_from_template,
    scaffold_only,
)
from .evidence import link_translations, scan_documents
from .memo_builder import apply_case_intake, build_working_memo
from .workflow import (
    build_prompt,
    build_status_report,
    import_llm_output,
    insert_section,
    run_next_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.draft",
        description="Controlled, step-by-step memorandum drafting workflow.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init_case = commands.add_parser("init-case", help="Create a case from the approved template")
    add_case_argument(init_case)
    init_case.add_argument("--task-type", required=True)

    build_prompt = commands.add_parser("build-prompt", help="Build one complete ManualProvider prompt")
    add_case_argument(build_prompt)
    build_prompt.add_argument("--step", required=True)
    build_prompt.add_argument("--episode-id", help="Repeatable episode/component id for criterion-style steps")
    build_prompt.add_argument(
        "--episode-folder",
        help="Folder under the evidence role folder to use for this episode, e.g. '1 episode'",
    )
    build_prompt.add_argument(
        "--instruction",
        action="append",
        default=[],
        help="Runtime instruction file; may be repeated (highest priority)",
    )

    scan = commands.add_parser("scan-documents", help="Scan source folders, update document index, and extract readable text")
    add_case_argument(scan)

    link = commands.add_parser("link-translations", help="Link translations to originals in document_index.csv")
    add_case_argument(link)

    status = commands.add_parser("status", help="Show case drafting/evidence status")
    add_case_argument(status)

    run_next = commands.add_parser("run-next", help="Suggest the next manual drafting action")
    add_case_argument(run_next)
    run_next.add_argument(
        "--build-prompt",
        action="store_true",
        help="Create the suggested prompt when the next action is prompt creation",
    )

    import_output = commands.add_parser("import-output", help="Validate and import one manual LLM output")
    add_case_argument(import_output)
    import_output.add_argument("--step", required=True)
    import_output.add_argument("--episode-id", help="Repeatable episode/component id for criterion-style steps")
    import_output.add_argument("--file", required=True)
    import_output.add_argument("--force", action="store_true", help="Replace existing validated output")

    insert_section = commands.add_parser("insert-section", help="Insert one validated section")
    add_case_argument(insert_section)
    insert_section.add_argument("--step", required=True)
    insert_section.add_argument("--episode-id", help="Repeatable episode/component id for criterion-style steps")
    insert_section.add_argument("--force", action="store_true", help="Replace existing draft section")

    intake = commands.add_parser("apply-intake", help="Apply basic case intake fields and optionally copy a source folder")
    add_case_argument(intake)
    intake.add_argument("--case-info-file", default="", help="YAML/TXT file with key: value case information")
    intake.add_argument("--source-folder", default="", help="Optional source folder to copy into the case workspace")
    intake.add_argument("--source-target-key", default="source_originals", help="Target paths key, e.g. source_originals")
    intake.add_argument("--beneficiary-full-name", default="")
    intake.add_argument("--preferred-reference", default="")
    intake.add_argument("--gender", choices=["male", "female", "neutral"], default="")
    intake.add_argument("--criteria", default="", help="Comma-separated EB1A criterion role IDs")
    intake.add_argument("--field", default="")
    intake.add_argument("--specialization", default="")
    intake.add_argument("--soc-code", default="")
    intake.add_argument("--case-number", default="")
    intake.add_argument("--receipt-date", default="")
    intake.add_argument("--rfe-date", default="")
    intake.add_argument("--response-deadline", default="")
    intake.add_argument("--uscis-address", default="")

    working_memo = commands.add_parser("build-working-memo", help="Create final_memo/working_memo.md and .docx")
    add_case_argument(working_memo)
    working_memo.add_argument("--template", default="", help="Machine template path; defaults by task type")

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)
    if args.command == "init-case":
        target = create_case_from_template(args.case_id, args.task_type)
        print(f"Created case workspace: {target}")
        print("Next: edit case_config.yaml and indexes before building prompts.")
        return 0
    if args.command == "build-prompt":
        target = build_prompt(
            args.case_id,
            args.step,
            args.instruction,
            episode_id=args.episode_id,
            episode_folder=args.episode_folder,
        )
        print(f"Created prompt: {target}")
        print("Copy the prompt into the LLM chat, then save the JSON response and run import-output.")
        return 0
    if args.command == "scan-documents":
        summary = scan_documents(args.case_id)
        print(f"Scanned files: {summary.scanned_files}")
        print(f"Added index rows: {summary.added_rows}")
        print(f"Updated index rows: {summary.updated_rows}")
        print(f"Locked rows skipped: {summary.locked_rows_skipped}")
        print(f"Extracted text files: {summary.extracted_texts}")
        print(f"Non-text / visual files: {summary.non_text_files}")
        print(f"Manual description files: {summary.manual_description_files}")
        print(f"Document index: {summary.index_path}")
        return 0
    if args.command == "link-translations":
        summary = link_translations(args.case_id)
        print(f"Translations seen: {summary.translations_seen}")
        print(f"Linked translations: {summary.linked_translations}")
        print(f"Already linked: {summary.already_linked}")
        print(f"Ambiguous translations: {summary.ambiguous_translations}")
        print(f"Unmatched translations: {summary.unmatched_translations}")
        print(f"Locked rows skipped: {summary.locked_rows_skipped}")
        print(f"Document index: {summary.index_path}")
        print(f"Translation review report: {summary.report_path}")
        print("Bundle order rule: original first, then translation.")
        return 0
    if args.command == "status":
        print(build_status_report(args.case_id))
        return 0
    if args.command == "run-next":
        print(run_next_report(args.case_id, build_prompt_file=args.build_prompt))
        return 0
    if args.command == "import-output":
        target = import_llm_output(
            args.case_id,
            args.step,
            args.file,
            episode_id=args.episode_id,
            force=args.force,
        )
        print(f"Validated output saved: {target}")
        return 0
    if args.command == "insert-section":
        target = insert_section(args.case_id, args.step, episode_id=args.episode_id, force=args.force)
        print(f"Draft section saved: {target}")
        return 0
    if args.command == "apply-intake":
        summary = apply_case_intake(
            args.case_id,
            {
                "beneficiary_full_name": args.beneficiary_full_name,
                "preferred_reference": args.preferred_reference,
                "gender": args.gender,
                "field": args.field,
                "specialization": args.specialization,
                "soc_code": args.soc_code,
                "case_number": args.case_number,
                "receipt_date": args.receipt_date,
                "rfe_date": args.rfe_date,
                "response_deadline": args.response_deadline,
                "uscis_address": args.uscis_address,
            },
            case_info_file=args.case_info_file,
            source_folder_path=args.source_folder,
            source_target_key=args.source_target_key,
            claimed_criteria=[item.strip() for item in args.criteria.split(",") if item.strip()]
            if args.criteria
            else None,
        )
        print(f"Updated fields: {summary.fields_updated}")
        print(f"Source files copied: {summary.source_files_copied}")
        print(f"Source files skipped: {summary.source_files_skipped}")
        print(f"Config: {summary.config_path}")
        return 0
    if args.command == "build-working-memo":
        summary = build_working_memo(args.case_id, template_path=args.template)
        print(f"Working memo markdown: {summary.markdown_path}")
        print(f"Working memo DOCX: {summary.docx_path}")
        print(f"Template parse report: {summary.template_report_path}")
        print(f"Sections written: {summary.sections_written}")
        print(f"Placeholders seen: {summary.placeholders_seen}")
        return 0

    details = {
        "task_type": getattr(args, "task_type", ""),
        "step": getattr(args, "step", ""),
        "file": getattr(args, "file", ""),
    }
    return scaffold_only(f"draft {args.command}", args.case_id, **details)


if __name__ == "__main__":
    raise SystemExit(main())
