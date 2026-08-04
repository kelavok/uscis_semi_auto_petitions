from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .bundle_workflow import (
    bundle_catalog,
    build_bundle_plan,
    build_evidence_bundle,
    build_exhibit_index,
    generate_separator_pages,
    inspect_bundle_preparation,
    inspect_layout_index_status,
    load_bundle_selection,
    prepare_selected_bundle,
    refresh_layout_indexes,
    render_separator_pdfs,
)
from .cli_support import CASE_ROOT, configure_console, create_case_from_template, validate_case_id
from .document_layout import (
    add_mapping as add_document_layout_mapping,
    build_original_directory_catalog,
    build_layout_bundle,
    build_layout_preview,
    list_installed_fonts,
    load_layout_selection,
    load_layout_status,
    refresh_layout_sources,
    remove_mapping as remove_document_layout_mapping,
    save_folder_scopes,
    save_layout_selection,
    save_layout_structure,
    set_mapping_paths,
    update_layout_settings,
)
from .evidence import (
    link_translations,
    manual_link_translation,
    scan_documents,
    unlink_translation,
)
from .memo_builder import (
    apply_case_intake,
    build_working_memo,
    parse_machine_template,
    refresh_case_sources,
)
from .json_input import parse_llm_json_object
from .progress import CaseProgress, build_case_progress
from .rfe_strategy import (
    apply_strategy_output,
    build_strategy_bootstrap_prompt,
    import_evidence_and_scan_inputs,
    load_strategy_manifest,
)
from .stages import LLMStage, LLMUnit, build_llm_stage
from .template_variants import EB1A_TEMPLATE_VARIANTS, eb1a_machine_template_file, eb1a_template_variant
from .workflow import (
    _case_path_value,
    build_prompt,
    build_status_report,
    destination_for_step,
    find_step,
    folder_role_map,
    import_llm_output,
    insert_section,
    load_case,
    output_stem,
    PromptOptions,
    read_custom_prompt_instructions,
    run_next_report,
    validate_llm_output,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.web",
        description="Local browser UI for the manual petitions workflow.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), PetitionsHandler)
    print(f"Petitions web UI: http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


class PetitionsHandler(BaseHTTPRequestHandler):
    server_version = "PetitionsWeb/0.1"

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/favicon.ico":
                self._send_bytes(
                    Path(__file__).resolve().parents[1] / "free-icon-robot-3398643.png",
                    "image/png",
                )
                return
            if parsed.path == "/":
                self._send_html(render_home(parsed.query))
                return
            if parsed.path == "/case":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_case_page(case_id, params))
                return
            if parsed.path == "/intake":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_intake_page(case_id, params))
                return
            if parsed.path == "/llm":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_llm_page(case_id, params))
                return
            if parsed.path == "/layout":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_layout_page(case_id, params))
                return
            if parsed.path == "/document-layout":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_document_layout_page(case_id, params))
                return
            if parsed.path == "/translations":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                self._send_html(render_translation_review_page(case_id, params))
                return
            if parsed.path == "/open-source-folder":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                source_key = _single(params, "source_key")
                location = _single(params, "location") or "case"
                opened = _open_source_folder(case_id, source_key, location)
                self._redirect(f"/intake?case={quote(case_id)}&message={quote(f'Opened folder: {opened}')}")
                return
            if parsed.path == "/file":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                rel_path = _single(params, "path")
                self._send_text(read_case_file(case_id, rel_path))
                return
            if parsed.path == "/layout-artifact":
                params = parse_qs(parsed.query)
                case_id = _single(params, "case")
                kind = _single(params, "kind")
                status = load_layout_status(case_id)
                if kind == "preview":
                    self._send_bytes(status.preview_pdf, "application/pdf")
                    return
                if kind == "final":
                    self._send_bytes(status.final_pdf, "application/pdf")
                    return
                self.send_error(404)
                return
            self.send_error(404)
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            self._send_html(render_error(exc), status=500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            data = {key: values[-1] for key, values in parse_qs(raw, keep_blank_values=True).items()}
            action = data.get("action", "")
            case_id = data.get("case", "")
            message = handle_action(action, case_id, data)
            destination_case = case_id or data.get("new_case", "")
            if action in {"manual_link_translation", "unlink_translation", "open_case_file"}:
                review_doc = data.get("review_doc", "")
                destination = f"/translations?case={quote(destination_case)}&message={quote(message)}"
                if review_doc and action == "open_case_file":
                    destination += f"&doc={quote(review_doc)}"
                self._redirect(destination)
            else:
                route = _action_route(action)
                destination = f"{route}?case={quote(destination_case)}&message={quote(message)}"
                if action in {"build_prompt", "refresh_unit_documents"} and data.get("step"):
                    step_id = data.get("step", "")
                    episode_id = data.get("episode_id", "")
                    destination += f"&step={quote(step_id)}"
                    if episode_id:
                        destination += f"&episode={quote(episode_id)}"
                    if action == "build_prompt":
                        destination += f"&prompt={quote(output_stem(step_id, episode_id) + '.latest.prompt.md')}"
                elif action == "run_next":
                    prompts = latest_prompts(destination_case)
                    if prompts:
                        destination += f"&prompt={quote(prompts[0].name)}"
                if data.get("redo_step"):
                    destination += f"&redo={quote(data.get('redo_step', ''))}"
                    if data.get("redo_episode"):
                        destination += f"&episode={quote(data.get('redo_episode', ''))}"
                self._redirect(destination)
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            case_id = ""
            action = ""
            try:
                case_id = data.get("case", "")  # type: ignore[possibly-undefined]
                action = data.get("action", "")  # type: ignore[possibly-undefined]
            except Exception:
                pass
            if case_id:
                if action in {"manual_link_translation", "unlink_translation", "open_case_file"}:
                    review_doc = data.get("review_doc", "") or data.get("translation_document_id", "")
                    destination = f"/translations?case={quote(case_id)}&error={quote(str(exc))}"
                    if review_doc:
                        destination += f"&doc={quote(review_doc)}"
                    self._redirect(destination)
                else:
                    route = _action_route(action)
                    self._redirect(f"{route}?case={quote(case_id)}&error={quote(str(exc))}")
            else:
                self._send_html(render_error(exc), status=500)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _send_html(self, html: str, *, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()


def handle_action(action: str, case_id: str, data: dict[str, str]) -> str:
    if action == "init_case":
        new_case = data.get("new_case", "").strip()
        task_type = data.get("task_type", "eb1a_petition").strip() or "eb1a_petition"
        create_case_from_template(new_case, task_type)
        return f"Created case {new_case}."

    validate_case_id(case_id)
    if action == "layout_pick_originals_dir":
        selected = _pick_directory(_safe_layout_setting(case_id, "originals_dir"))
        if not selected:
            return "Originals folder selection was canceled."
        update_layout_settings(case_id, originals_dir=selected)
        return "Selected originals folder."
    if action == "layout_pick_translations_dir":
        selected = _pick_directory(_safe_layout_setting(case_id, "translations_dir"))
        if not selected:
            return "Translations folder selection was canceled."
        update_layout_settings(case_id, translations_dir=selected)
        return "Selected translations folder."
    if action == "layout_pick_list_document":
        selected = _pick_file(_safe_layout_setting(case_id, "list_document_path"))
        if not selected:
            return "Exhibit list file selection was canceled."
        update_layout_settings(case_id, list_document_path=selected)
        return "Selected exhibit list document."
    if action == "layout_parse_sources":
        summary = refresh_layout_sources(
            case_id,
            originals_dir=data.get("originals_dir", ""),
            translations_dir=data.get("translations_dir", ""),
            list_document_path=data.get("list_document_path", ""),
            font_family=data.get("font_family", ""),
        )
        return (
            f"Scanned {summary.original_files} original file(s) and {summary.translation_files} translation file(s); "
            f"parsed {summary.exhibits} exhibit(s), {summary.episodes} episode(s), and {summary.documents} document(s)."
        )
    if action == "layout_save_structure":
        save_layout_structure(case_id, data)
        return "Saved exhibit titles, episode titles, and document titles."
    if action == "layout_save_folder_scopes":
        save_folder_scopes(case_id, data)
        return "Saved exhibit and episode folder selections."
    if action == "layout_save_document_originals":
        selected_files = [
            value
            for key, value in data.items()
            if key.startswith("original_choice_") and value.strip()
        ]
        set_mapping_paths(case_id, data.get("document_id", ""), "original", selected_files)
        return f"Saved {len(selected_files)} original file(s) for the selected document."
    if action == "layout_add_mapping":
        kind = data.get("mapping_kind", "").strip()
        initial_dir = _safe_layout_setting(case_id, "translations_dir" if kind == "translation" else "originals_dir")
        selected = _pick_file(initial_dir)
        if not selected:
            return "File selection was canceled."
        add_document_layout_mapping(case_id, data.get("document_id", ""), kind, selected)
        return "Attached file to the selected document."
    if action == "layout_remove_mapping":
        remove_document_layout_mapping(
            case_id,
            data.get("document_id", ""),
            data.get("mapping_kind", ""),
            int(data.get("mapping_index", "0") or "0"),
        )
        return "Removed the selected file mapping."
    if action == "layout_preview":
        summary = build_layout_preview(case_id)
        return f"Built separator preview PDF: {summary.pdf_path}."
    if action == "layout_build":
        selected_exhibits = [
            key.removeprefix("select_layout_exhibit_")
            for key, value in data.items()
            if key.startswith("select_layout_exhibit_") and value == "on"
        ]
        selected_documents = [
            key.removeprefix("select_layout_document_")
            for key, value in data.items()
            if key.startswith("select_layout_document_") and value == "on"
        ]
        save_layout_selection(case_id, selected_exhibits, selected_documents)
        summary = build_layout_bundle(case_id, selected_exhibits, selected_documents)
        return (
            f"Built layout bundle PDF: {summary.pdf_path}. "
            f"Included {summary.exhibits} exhibit(s), {summary.documents} document(s), and {summary.source_files} mapped file(s)."
        )
    if action == "scan_documents":
        summary = scan_documents(case_id)
        return (
            f"Scanned {summary.scanned_files} file(s); added {summary.added_rows}, "
            f"updated {summary.updated_rows}, removed {summary.removed_rows} auxiliary row(s)."
        )
    if action == "refresh_intake_sources":
        loaded = load_case(case_id)
        if str(loaded.config.get("task_type", "")) == "eb1a_rfe_response":
            imports = loaded.config.get("source_imports", {})
            if not isinstance(imports, dict):
                imports = {}
            imported = import_evidence_and_scan_inputs(
                case_id,
                str(imports.get("initial_filing_memo", "")),
                str(imports.get("rfe_new_documents", "")),
            )
            refreshed_files = imported.copied_files
        else:
            refreshed_files = refresh_case_sources(case_id).source_files_copied
        scanned = scan_documents(case_id)
        linked = link_translations(case_id)
        return (
            f"Refreshed intake sources ({refreshed_files} new or changed file(s)); "
            f"reindexed {scanned.scanned_files} document(s) and linked "
            f"{linked.linked_translations} translation(s). The memorandum was not changed."
        )
    if action == "refresh_unit_documents":
        scanned = scan_documents(case_id)
        linked = link_translations(case_id)
        return (
            f"Refreshed document list: {scanned.scanned_files} scanned, "
            f"{scanned.added_rows} added, {scanned.updated_rows} updated, "
            f"{scanned.removed_rows} auxiliary row(s) removed, "
            f"{linked.linked_translations} translation(s) linked."
        )
    if action == "build_rfe_strategy_prompt":
        summary = build_strategy_bootstrap_prompt(
            case_id,
            data.get("strategy_path", ""),
            data.get("rfe_path", ""),
        )
        return f"Created strategy bootstrap prompt {summary.prompt_path.name}."
    if action == "import_rfe_strategy_output":
        output_text = data.get("strategy_output_json", "").strip()
        if not output_text:
            raise ValueError("Paste the strategy bootstrap JSON first.")
        try:
            parsed_strategy = parse_llm_json_object(output_text)
            output = parsed_strategy.data
        except ValueError as exc:
            raise ValueError(f"Invalid strategy JSON: {exc}") from exc
        summary = apply_strategy_output(case_id, output)
        memo = build_working_memo(case_id)
        repair = (
            f" Automatic JSON repair applied: {'; '.join(parsed_strategy.repair_notes)}."
            if parsed_strategy.repaired
            else ""
        )
        return (
            f"Accepted strategy manifest with {summary.unit_count} drafting unit(s); "
            f"built {memo.docx_path.name}.{repair}"
        )
    if action == "import_rfe_evidence":
        imported = import_evidence_and_scan_inputs(
            case_id,
            data.get("initial_memo_path", ""),
            data.get("new_documents_path", ""),
        )
        scanned = scan_documents(case_id)
        linked = link_translations(case_id)
        memo = build_working_memo(case_id)
        return (
            f"Imported {imported.copied_files} file(s), scanned {scanned.scanned_files}, "
            f"partitioned {imported.initial_sections} initial-filing section(s), and linked "
            f"{linked.linked_translations} translation(s); rebuilt {memo.docx_path.name} from actual evidence folders."
        )
    if action == "apply_intake":
        summary = apply_case_intake(
            case_id,
            {
                "beneficiary_full_name": data.get("beneficiary_full_name", ""),
                "preferred_reference": data.get("preferred_reference", ""),
                "gender": data.get("gender", ""),
                "field": data.get("field", ""),
                "specialization": data.get("specialization", ""),
                "soc_code": data.get("soc_code", ""),
                "case_number": data.get("case_number", ""),
                "receipt_date": data.get("receipt_date", ""),
                "rfe_date": data.get("rfe_date", ""),
                "response_deadline": data.get("response_deadline", ""),
                "uscis_address": data.get("uscis_address", ""),
                "procedural_context": data.get("procedural_context", ""),
                "drafting_objective": data.get("drafting_objective", ""),
                "citizenship": data.get("citizenship", ""),
                "o1b_track": data.get("o1b_track", ""),
                "petitioner_company_name": data.get("petitioner_company_name", ""),
                "petitioner_company_address": data.get("petitioner_company_address", ""),
                "petitioner_type": data.get("petitioner_type", ""),
                "authorized_signatory": data.get("authorized_signatory", ""),
                "filing_processing": data.get("filing_processing", ""),
                "validity_start": data.get("validity_start", ""),
                "validity_end": data.get("validity_end", ""),
                "filing_uscis_address": data.get("filing_uscis_address", ""),
                "position_or_role": data.get("position_or_role", ""),
                "compensation": data.get("compensation", ""),
                "work_location": data.get("work_location", ""),
                "duties_summary": data.get("duties_summary", ""),
                "eb1a_template_variant": data.get("eb1a_template_variant", ""),
            },
            case_info_file=data.get("case_info_file", ""),
            source_folder_path=data.get("source_folder_path", ""),
            source_target_key=data.get("source_target_key", "source_originals"),
            source_folder_paths={
                "source_originals": data.get("source_originals_path", ""),
                "source_translations": data.get("source_translations_path", ""),
                "source_other": data.get("source_other_path", ""),
            },
            claimed_criteria=[
                role
                for role in (
                    "awards",
                    "memberships",
                    "media",
                    "judging",
                    "original_contribution",
                    "scholarly_articles",
                    "exhibitions",
                    "leading_critical_role",
                    "high_salary",
                    "commercial_success",
                    "lead_starring_productions",
                    "published_recognition",
                    "organization_role",
                    "commercial_critical_success",
                    "significant_recognition",
                    "comparable_evidence",
                )
                if data.get(f"criterion_{role}") == "on"
            ]
            if data.get("claimed_criteria_present") == "1"
            else None,
        )
        return f"Updated {summary.fields_updated} field(s); copied {summary.source_files_copied} source file(s)."
    if action == "build_working_memo":
        summary = build_working_memo(case_id, template_path=data.get("template_path", ""))
        return f"Built working memo: {summary.docx_path.name}; sections {summary.sections_written}; placeholders {summary.placeholders_seen}."
    if action == "parse_template":
        template = data.get("template_path", "").strip()
        if not template:
            raise ValueError("Template path is required.")
        report = parse_machine_template(Path(template))
        return f"Template parsed: {report.section_count} section(s), {report.placeholder_count} placeholder(s)."
    if action == "link_translations":
        summary = link_translations(case_id)
        return (
            f"Newly linked {summary.linked_translations}; already linked {summary.already_linked}; "
            f"ambiguous {summary.ambiguous_translations}; unmatched {summary.unmatched_translations}. "
            f"Review: reports/{summary.report_path.name}"
        )
    if action == "manual_link_translation":
        original_reference = data.get("original_path", "").strip() or data.get("original_document_id", "").strip()
        summary = manual_link_translation(
            case_id,
            data.get("translation_document_id", ""),
            original_reference,
            allow_shared_original=data.get("allow_shared_original") == "on",
        )
        link_translations(case_id, auto_match=False)
        displaced = (
            f" Returned to manual review: {', '.join(summary.displaced_translation_ids)}."
            if summary.displaced_translation_ids
            else ""
        )
        return f"Linked {summary.translation_document_id} to {summary.original_document_id}.{displaced}"
    if action == "unlink_translation":
        unlink_translation(case_id, data.get("translation_document_id", ""))
        link_translations(case_id, auto_match=False)
        return f"Removed translation link for {data.get('translation_document_id', '')}."
    if action == "open_case_file":
        path = _open_case_file_in_explorer(case_id, data.get("file_path", ""))
        return f"Opened in File Explorer: {path.name}"
    if action == "run_next":
        build = data.get("build_prompt") == "on"
        return run_next_report(case_id, build_prompt_file=build)
    if action == "build_prompt":
        step = data.get("step", "").strip()
        episode_id = data.get("episode_id", "").strip() or None
        episode_folder = data.get("episode_folder", "").strip() or None
        loaded = load_case(case_id)
        step_data = find_step(loaded.workflow, step)
        options = PromptOptions(episode_id=episode_id or "", episode_folder=episode_folder or "")
        stem = output_stem(step, episode_id or "")
        destination = destination_for_step(step_data, options)
        generated_root = loaded.case_dir / _case_path_value(loaded.config, "generated_prompts")
        validated_root = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs")
        already_exists = (
            (destination and (loaded.case_dir / destination).exists())
            or (validated_root / f"{stem}.json").exists()
            or (generated_root / f"{stem}.latest.prompt.md").exists()
        )
        if already_exists and data.get("force") != "on":
            raise ValueError(
                f"Stage {stem} has already been started or completed. Confirm overwrite/retry from the LLM workspace."
            )
        custom_instructions = data.get("custom_instructions") if "custom_instructions" in data else None
        prompt = build_prompt(
            case_id,
            step,
            [],
            episode_id=episode_id,
            episode_folder=episode_folder,
            custom_instructions=custom_instructions,
        )
        return f"Created prompt {prompt.name}."
    if action == "save_rfe_notes":
        save_case_file(case_id, "user_case_instructions.md", data.get("user_case_instructions", ""))
        save_case_file(case_id, "rfe_response_plan.md", data.get("rfe_response_plan", ""))
        save_case_file(
            case_id,
            "source_documents/rfe_response/strategy/browser_strategy_notes.md",
            data.get("browser_strategy_notes", ""),
        )
        return "Saved RFE strategy and response plan."
    if action == "import_output":
        step = data.get("step", "").strip()
        episode_id = data.get("episode_id", "").strip() or None
        output_text = data.get("output_json", "").strip()
        if not output_text:
            raise ValueError("Paste JSON output first.")
        try:
            parsed_output = parse_llm_json_object(output_text)
            output_data = parsed_output.data
        except ValueError as exc:
            raise ValueError(f"Output was not accepted: {exc}") from exc
        loaded = load_case(case_id)
        step_data = find_step(loaded.workflow, step)
        try:
            validate_llm_output(
                output_data,
                loaded,
                step,
                PromptOptions(episode_id=episode_id or ""),
            )
        except SystemExit as exc:
            raise ValueError(
                f"Output was not accepted: {exc}. Correct the indicated fields and paste the updated JSON again."
            ) from exc
        force = data.get("force") == "on"
        output_path = loaded.case_dir / _case_path_value(loaded.config, "llm_outputs") / f"{output_stem(step, episode_id or '')}.json"
        validated_path = loaded.case_dir / _case_path_value(loaded.config, "validated_outputs") / f"{output_stem(step, episode_id or '')}.json"
        destination = destination_for_step(step_data, PromptOptions(episode_id=episode_id or ""))
        destination_path = loaded.case_dir / destination if destination else None
        if not force and (output_path.exists() or validated_path.exists() or (destination_path and destination_path.exists())):
            raise ValueError(
                f"Stage {output_stem(step, episode_id or '')} already has saved results. "
                "Use Retry/overwrite from the LLM workspace if replacement is intentional."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        validated = import_llm_output(case_id, step, str(output_path), episode_id=episode_id, force=force)
        if data.get("insert_after_import") == "on":
            target = insert_section(case_id, step, episode_id=episode_id, force=force)
            next_report = run_next_report(case_id, build_prompt_file=True)
            return (
                f"Validated {validated.name}, inserted {target.name}, and refreshed working_memo.docx.\n\n"
                f"{next_report}"
            )
        repair = (
            f" Automatic JSON repair applied: {'; '.join(parsed_output.repair_notes)}."
            if parsed_output.repaired
            else ""
        )
        return f"Validated output {validated.name}.{repair}"
    if action == "insert_section":
        step = data.get("step", "").strip()
        episode_id = data.get("episode_id", "").strip() or None
        target = insert_section(case_id, step, episode_id=episode_id, force=data.get("force") == "on")
        next_report = run_next_report(case_id, build_prompt_file=True)
        return f"Inserted section {target.name} and refreshed working_memo.docx.\n\n{next_report}"
    if action == "refresh_layout_indexes":
        summary = refresh_layout_indexes(case_id)
        status = summary.status
        warning = ""
        if status.stale_document_ids or status.assignment_conflicts:
            warning = " Some references could not be fully matched; available documents can still be bundled."
        elif status.unsupported_documents:
            warning = " Indexes are ready; unsupported source files will be skipped unless converted."
        return (
            f"Refreshed indexes: scanned {summary.scanned_files} file(s), removed "
            f"{summary.auxiliary_rows_removed} auxiliary row(s), rebound "
            f"{summary.replacement_documents_rebound} replacement PDF(s), assigned "
            f"{status.assigned_used_documents}/{status.unique_used_documents} used document(s), "
            f"and built {status.exhibit_count} exhibit(s).{warning}"
        )
    if action == "build_index":
        summary = build_exhibit_index(case_id)
        if summary.documents_seen and not summary.documents_with_exhibit_number:
            raise ValueError(
                "No documents have Exhibit numbers. Use 'Refresh indexes' to derive them from validated LLM outputs first."
            )
        return f"Exhibits created {summary.exhibits_created}, updated {summary.exhibits_updated}."
    if action == "separators":
        summary = generate_separator_pages(case_id)
        return f"Wrote {summary.exhibit_pages_written} exhibit and {summary.document_pages_written} document separator page(s)."
    if action == "separator_pdfs":
        summary = render_separator_pdfs(case_id)
        return f"Wrote {summary.pdf_pages_written} separator PDF(s)."
    if action == "bundle_dry_run":
        summary = build_bundle_plan(case_id)
        return f"Bundle plan: {summary.ready_items} ready, {summary.missing_items} missing, {summary.unsupported_items} unsupported."
    if action == "prepare_selected_bundle":
        selected_exhibits = [
            key.removeprefix("select_exhibit_")
            for key, value in data.items()
            if key.startswith("select_exhibit_") and value == "on"
        ]
        selected_documents = [
            key.removeprefix("select_document_")
            for key, value in data.items()
            if key.startswith("select_document_") and value == "on"
        ]
        summary = prepare_selected_bundle(case_id, selected_exhibits, selected_documents)
        return (
            f"Prepared {len(summary.selection.exhibit_numbers)} exhibit(s) and "
            f"{len(summary.selection.document_ids)} document(s): rendered "
            f"{summary.separator_pdfs} separator PDF(s); plan has "
            f"{summary.plan.missing_items} missing and {summary.plan.unsupported_items} unsupported item(s)."
        )
    if action == "bundle_build":
        summary = build_evidence_bundle(case_id)
        return f"Built final PDF: {summary.final_pdf_path}."
    raise ValueError(f"Unknown action: {action}")


def render_home(query: str = "") -> str:
    params = parse_qs(query)
    cases = list_cases()
    message = _single(params, "message")
    error = _single(params, "error")
    cards = []
    for case_id in cases:
        progress = _safe_progress(case_id)
        cards.append(
            f'<a class="case-card" href="/case?case={quote(case_id)}">'
            f"<strong>{escape(progress.beneficiary_name)}</strong>"
            f"<span>{escape(case_id)} · {escape(_task_type_label(progress.task_type))}</span>"
            f"<span>Stage: {escape(progress.stage_label)} · {progress.completion_percent}%</span></a>"
        )
    return page(
        "Petitions UI",
        f"""
        {alert(message, "ok")}
        {alert(error, "error")}
        <section class="panel hero">
          <div>
            <h1>Petitions manual workflow</h1>
            <p>Local UI for drafting prompts, validating LLM JSON, indexes, separators, and bundle assembly.</p>
          </div>
          <form method="post" class="inline-form">
            <input type="hidden" name="action" value="init_case">
            <input name="new_case" placeholder="new_case_id" required>
            <select name="task_type">
              <option value="eb1a_petition">EB1A petition</option>
              <option value="o1b_petition">O-1B petition</option>
              <option value="eb1a_rfe_response">EB1A RFE response</option>
              <option value="document_layout">Document layout</option>
            </select>
            <button>Create case</button>
          </form>
        </section>
        <section class="panel">
          <h2>Case library</h2>
          {render_case_switch()}
          <p class="muted small">Cases are loaded from <code>case_workspace</code> and remain available after app or computer restarts.</p>
        </section>
        <section class="grid">{''.join(cards) if cards else '<p>No cases yet.</p>'}</section>
        """,
    )


def render_case_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    case_dir = _case_dir(case_id)
    if not case_dir.exists():
        return page("Case not found", f"<p>Case not found: {escape(case_id)}</p><p><a href='/'>Back</a></p>")
    message = _single(params, "message")
    error = _single(params, "error")
    task_type = _safe_case_task_type(case_id)
    if task_type == "document_layout":
        layout_status = load_layout_status(case_id)
        stage_one = 100 if layout_status.stage1_complete else 0
        stage_two = (
            0
            if not layout_status.stage2_available
            else round(
                (layout_status.fully_mapped_document_count / max(layout_status.document_count, 1)) * 100
            )
        )
        stage_three = 100 if layout_status.has_final else 0
        return page(
            f"Case {case_id}",
            f"""
            <div class="case-nav"><a href="/">&larr; Case library</a>{render_case_switch(case_id)}</div>
            {alert(message, "ok")}
            {alert(error, "error")}
            <section class="panel">
              <h1>{escape(case_id)}</h1>
              <p class="muted">Task type: {escape(_task_type_label(task_type))}</p>
              <p>This case uses the isolated document-layout workflow: parse the exhibit list, attach one or more real files to each document, then assemble a PDF bundle.</p>
            </section>
            <div class="stage-grid">
              {_stage_card("1", "Parse sources", stage_one, f"{layout_status.exhibit_count} exhibit(s), {layout_status.document_count} document(s)", f"/document-layout?case={quote(case_id)}", "Open layout workflow")}
              {_stage_card("2", "Map files", stage_two, f"{layout_status.fully_mapped_document_count}/{layout_status.document_count} document(s) linked to originals", f"/document-layout?case={quote(case_id)}", "Continue mapping")}
              {_stage_card("3", "Build PDF", stage_three, "Preview separators and assemble a selected final PDF.", f"/document-layout?case={quote(case_id)}", "Open final stage")}
            </div>
            """,
        )
    progress = _safe_progress(case_id)
    llm_stage = _safe_llm_stage(case_id)
    intake_percent = _stage_percent(progress, {"intake", "working_memo", "scan", "translations"})
    layout_percent = _stage_percent(progress, {"exhibits", "bundle"})
    return page(
        f"Case {case_id}",
        f"""
        <div class="case-nav"><a href="/">&larr; Case library</a>{render_case_switch(case_id)}</div>
        {alert(message, "ok")}
        {alert(error, "error")}
        <section class="panel">
          <h1>{escape(case_id)}</h1>
          <p class="muted">Task type: {escape(_task_type_label(task_type))}</p>
          <p>This page is the case overview. Open the stage you are working on; drafting and layout controls are kept separate.</p>
        </section>
        {render_case_progress(progress)}
        <div class="stage-grid">
          {_stage_card("1", "Intake & evidence", intake_percent, "Case data, working memorandum, document scan, and translation review.", f"/intake?case={quote(case_id)}", "Open intake")}
          {_stage_card("2", "LLM drafting", llm_stage.percent, f"{llm_stage.completed_units}/{llm_stage.total_units} drafting unit(s) completed.", f"/llm?case={quote(case_id)}", "Open LLM workspace")}
          {_stage_card("3", "Layout & bundle", layout_percent, "Exhibit index, separator pages, and final PDF assembly.", f"/layout?case={quote(case_id)}", "Open layout")}
        </div>
        """,
    )


def render_intake_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    task_type = _safe_case_task_type(case_id)
    status = _safe_text(lambda: build_status_report(case_id))
    return page(
        f"Intake - {case_id}",
        f"""
        {_stage_nav(case_id, "intake")}
        {alert(_single(params, 'message'), 'ok')}
        {alert(_single(params, 'error'), 'error')}
        <section class="panel">
          <h1>Intake & evidence</h1>
          {'' if task_type == 'eb1a_rfe_response' else '<div class="button-row">'}
          {'' if task_type == 'eb1a_rfe_response' else post_button(case_id, "build_working_memo", "Build working memo")}
          {'' if task_type == 'eb1a_rfe_response' else post_button(case_id, "scan_documents", "Scan documents")}
          {'' if task_type == 'eb1a_rfe_response' else post_button(case_id, "link_translations", "Auto-link translations")}
          {'' if task_type == 'eb1a_rfe_response' else f'<a class="action-link" href="/translations?case={quote(case_id)}">Review translation links</a>'}
          {'' if task_type == 'eb1a_rfe_response' else '</div>'}
        </section>
        {render_rfe_panel(case_id) if task_type == 'eb1a_rfe_response' else render_intake_panel(case_id, task_type)}
        <section class="panel"><h2>Evidence status</h2><pre>{escape(status)}</pre></section>
        """,
    )


def render_llm_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    stage = _safe_llm_stage(case_id)
    redo_step = _single(params, "redo").strip()
    redo_episode = _single(params, "episode").strip()
    selected_step = _single(params, "step").strip()
    target_step = redo_step or selected_step or stage.current_step_id
    target_episode = redo_episode if (redo_step or selected_step) else stage.current_episode_id
    current = _find_llm_unit(
        stage,
        target_step,
        target_episode,
    )
    selected_prompt = _single(params, "prompt").strip()
    if not selected_prompt and current and current.latest_prompt:
        selected_prompt = current.latest_prompt
    if not selected_prompt and current is None:
        prompts = latest_prompts(case_id)
        selected_prompt = prompts[0].name if prompts else ""
    prompt_text = read_case_file(case_id, f"generated_prompts/{selected_prompt}") if selected_prompt else ""
    custom_instructions = ""
    if current:
        custom_instructions = read_custom_prompt_instructions(
            load_case(case_id), current.step_id, current.episode_id
        )
    selected_key = current.key if current else ""
    timeline = "".join(_render_llm_unit(case_id, unit, selected_key) for unit in stage.units)
    current_panel = _render_llm_current(
        case_id,
        stage,
        current,
        prompt_text,
        selected_prompt,
        bool(redo_step),
        _dependency_warning(stage, current),
        custom_instructions,
    )
    transition = (
        f'<a class="action-link" href="/layout?case={quote(case_id)}">LLM drafting complete - continue to layout</a>'
        if stage.complete
        else ""
    )
    return page(
        f"LLM drafting - {case_id}",
        f"""
        {_stage_nav(case_id, "llm")}
        {alert(_single(params, 'message'), 'ok')}
        {alert(_single(params, 'error'), 'error')}
        <section class="panel">
          <div class="progress-heading"><div><h1>LLM drafting workspace</h1><p class="muted">{stage.completed_units}/{stage.total_units} unit(s) complete</p></div><strong>{stage.percent}%</strong></div>
          <div class="progress-bar"><span style="width:{stage.percent}%"></span></div>
          {transition}
        </section>
        <div class="llm-layout">
          <aside class="panel llm-timeline"><h2>Drafting units</h2><p class="muted small">Select any unit and work in the order you prefer. Dependency warnings remain visible for synthesis steps.</p>{timeline or '<p>No drafting units found.</p>'}</aside>
          <div>{current_panel}</div>
        </div>
        """,
    )


def render_layout_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    stage = _safe_llm_stage(case_id)
    progress = _safe_progress(case_id)
    layout_percent = _stage_percent(progress, {"exhibits", "bundle"})
    index_status = inspect_layout_index_status(case_id)
    index_ready = index_status.ready_for_separators
    catalog = bundle_catalog(case_id) if index_ready else []
    selection = load_bundle_selection(case_id) if index_ready else None
    preparation = inspect_bundle_preparation(case_id) if index_ready else None
    if not index_status.unique_used_documents:
        index_notice = (
            '<div class="alert error"><strong>No validated evidence selection found.</strong> '
            "Complete Stage 2 outputs before building the evidence index.</div>"
        )
    elif index_status.refresh_required:
        details = []
        if index_status.stale_document_ids:
            details.append(f"{len(index_status.stale_document_ids)} stale document reference(s)")
        if index_status.assignment_conflicts:
            details.append(f"{len(index_status.assignment_conflicts)} assignment conflict(s)")
        if index_status.indexed_sidecars:
            details.append(f"{len(index_status.indexed_sidecars)} auxiliary file(s) still indexed")
        detail_text = "; ".join(details) or "Exhibit numbers have not been assigned yet"
        index_notice = (
            '<div class="alert error"><strong>Index refresh required.</strong> '
            f"{escape(detail_text)}. Click <strong>Refresh indexes</strong> before generating separators.</div>"
        )
    else:
        index_notice = (
            '<div class="alert ok"><strong>Evidence indexes ready.</strong> '
            f"{index_status.assigned_used_documents} used document(s) assigned to "
            f"{index_status.exhibit_count} exhibit(s).</div>"
        )
    unsupported_notice = (
        '<div class="alert ok"><strong>Bundle warning.</strong> '
        "Unsupported or missing source files will be skipped unless replaced/converted.<ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in index_status.unsupported_documents)
        + "</ul></div>"
        if index_status.unsupported_documents
        else ""
    )
    selected_exhibits = set(selection.exhibit_numbers) if selection else set()
    selected_documents = set(selection.document_ids) if selection else set()
    exhibit_rows = []
    for exhibit in catalog:
        exhibit_number = str(exhibit["exhibit_number"])
        documents = exhibit["documents"]
        document_rows = "".join(
            '<label class="bundle-document">'
            f'<input type="checkbox" name="select_document_{escape(str(document.get("document_id", "")))}" '
            f'data-exhibit="{escape(exhibit_number)}"'
            f'{" checked" if str(document.get("document_id", "")) in selected_documents else ""}>'
            f'<code>{escape(str(document.get("document_id", "")))}</code> '
            f'<span>{escape(str(document.get("display_title", "") or document.get("original_file_name", "")))}</span>'
            '</label>'
            for document in documents
        )
        exhibit_rows.append(
            f'<details class="bundle-exhibit" open><summary><label>'
            f'<input type="checkbox" name="select_exhibit_{escape(exhibit_number)}" '
            f'data-exhibit-toggle="{escape(exhibit_number)}"'
            f'{" checked" if exhibit_number in selected_exhibits else ""}>'
            f'<strong>Exhibit {escape(exhibit_number)} — {escape(str(exhibit["display_title"]))}</strong> '
            f'<span class="muted">({len(documents)} documents)</span></label></summary>'
            f'<div class="bundle-documents">{document_rows}</div></details>'
        )
    selector = (
        '<form method="post" class="bundle-selection" data-bundle-selection>'
        f'<input type="hidden" name="case" value="{escape(case_id)}">'
        '<input type="hidden" name="action" value="prepare_selected_bundle">'
        '<div class="button-row"><button type="button" class="secondary" data-select-all>Select all</button>'
        '<button type="button" class="secondary" data-clear-all>Clear all</button></div>'
        + "".join(exhibit_rows)
        + f'<button{("" if index_ready else " disabled")}>Prepare selected bundle</button></form>'
    ) if catalog else '<p class="muted">Refresh indexes to load the exhibit list.</p>'
    preparation_ready = bool(preparation and preparation.ready_to_build)
    preparation_text = preparation.reason if preparation else "Refresh indexes first."
    phase_one_class = "done" if index_ready else "current"
    phase_two_class = "done" if preparation_ready else ("current" if index_ready else "locked")
    phase_three_class = "current" if preparation_ready else "locked"
    return page(
        f"Layout - {case_id}",
        f"""
        {_stage_nav(case_id, "layout")}
        {alert(_single(params, 'message'), 'ok')}
        {alert(_single(params, 'error'), 'error')}
        <section class="panel">
          <div class="progress-heading"><div><h1>Layout & evidence bundle</h1><p class="muted">LLM drafting: {stage.percent}% complete</p></div><strong>{layout_percent}%</strong></div>
          <div class="progress-bar"><span style="width:{layout_percent}%"></span></div>
          {'<p class="alert error">LLM drafting is not complete. A dry run is allowed, but final assembly should wait.</p>' if not stage.complete else ''}
          {index_notice}
          {unsupported_notice}
          <p class="muted small">Validated evidence references: {index_status.used_document_references}; unique documents: {index_status.unique_used_documents}; assigned: {index_status.assigned_used_documents}; exhibits: {index_status.exhibit_count}.</p>
        </section>
        <section class="bundle-pipeline">
          <div class="pipeline-phase {phase_one_class}"><span class="phase-number">1</span><h2>Refresh indexes</h2><p>Rescan evidence and derive exhibit numbering from validated Stage 2 outputs.</p>{post_button(case_id, "refresh_layout_indexes", "Refresh indexes")}</div>
          <div class="pipeline-arrow" aria-hidden="true">→</div>
          <div class="pipeline-phase {phase_two_class}"><span class="phase-number">2</span><h2>Select & prepare</h2><p>Choose all or only the exhibits and documents you need. Separator generation, PDF rendering, and validation run together.</p><p class="muted small">{escape(preparation_text)}</p></div>
          <div class="pipeline-arrow" aria-hidden="true">→</div>
          <div class="pipeline-phase {phase_three_class}"><span class="phase-number">3</span><h2>Build PDF</h2><p>Assemble the prepared selection into one evidence bundle.</p>{post_button(case_id, "bundle_build", "Build selected PDF", disabled=not preparation_ready)}</div>
        </section>
        <section class="panel"><h2>Exhibits and documents</h2><p class="muted">Review the contents, select entire exhibits or individual documents, then prepare the selection.</p>{selector}</section>
        <section class="panel"><h2>Bundle status</h2><pre>{escape(_safe_text(lambda: build_status_report(case_id)))}</pre></section>
        """,
    )


def render_document_layout_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    status = load_layout_status(case_id)
    if _safe_case_task_type(case_id) != "document_layout":
        return page(
            "Wrong case type",
            f"<section class='panel'><h1>Wrong case type</h1><p>{escape(case_id)} is not a document-layout case.</p></section>",
        )

    selected = load_layout_selection(case_id)
    selected_exhibits = set(selected.get("selected_exhibits", []))
    selected_documents = set(selected.get("selected_documents", []))
    if not selected_exhibits and not selected_documents:
        selected_exhibits = {
            str(exhibit.get("number", ""))
            for exhibit in status.structure.get("exhibits", [])
        }
        selected_documents = {
            str(document.get("id", ""))
            for exhibit in status.structure.get("exhibits", [])
            for episode in exhibit.get("episodes", [])
            for document in episode.get("documents", [])
        }

    stage_one_class = "done" if status.stage1_complete else "current"
    stage_two_class = "done" if status.stage2_complete else ("current" if status.stage2_available else "locked")
    stage_three_class = "current" if status.stage3_available else "locked"
    if status.has_final:
        stage_three_class = "done"

    settings = status.settings
    available_fonts = list_installed_fonts()
    font_family = settings.get("font_family", "Times New Roman") or "Times New Roman"
    if font_family not in available_fonts:
        available_fonts = [font_family, *available_fonts]
    font_options = "".join(
        f'<option value="{escape(name, quote=True)}"{" selected" if name == font_family else ""}>{escape(name)}</option>'
        for name in available_fonts
    )
    inventory = status.inventory
    directory_catalog = build_original_directory_catalog(case_id)
    directories_by_path = {
        str(item.get("directory", "")): item for item in directory_catalog
    }
    inventory_html = (
        f"<p class='muted small'>Indexed files: {len(inventory.get('original_files', []))} original(s), {len(inventory.get('translation_files', []))} translation(s).</p>"
        "<details><summary>View indexed files</summary>"
        f"<div class='inventory-grid'>{_render_inventory_group('Originals', inventory.get('original_files', []))}{_render_inventory_group('Translations', inventory.get('translation_files', []))}</div>"
        "</details>"
    )

    structure_rows: list[str] = []
    for exhibit in status.structure.get("exhibits", []):
        episode_rows: list[str] = []
        for episode in exhibit.get("episodes", []):
            document_rows = "".join(
                f"""
                <div class="layout-document-row">
                  <code>{escape(str(document.get('number', '')))}</code>
                  <input name="document_title_{escape(str(document.get('id', '')))}" value="{escape(str(document.get('title', '')), quote=True)}">
                </div>
                """
                for document in episode.get("documents", [])
            )
            episode_heading = (
                ""
                if episode.get("kind") == "direct"
                else f"""
                <div class="layout-episode-head">
                  <code>{escape(str(episode.get('number', '')))}</code>
                  <input name="episode_title_{escape(str(episode.get('id', '')))}" value="{escape(str(episode.get('title', '')), quote=True)}">
                </div>
                """
            )
            episode_rows.append(
                f"""
                <section class="layout-episode-card {'direct' if episode.get('kind') == 'direct' else ''}">
                  {episode_heading or '<p class="muted small">Documents directly under this Exhibit</p>'}
                  {document_rows}
                </section>
                """
            )
        structure_rows.append(
            f"""
            <section class="layout-exhibit-card">
              <div class="layout-exhibit-head">
                <input class="layout-exhibit-number" name="exhibit_number_{escape(str(exhibit.get('id', '')))}" value="{escape(str(exhibit.get('number', '')), quote=True)}">
                <input name="exhibit_title_{escape(str(exhibit.get('id', '')))}" value="{escape(str(exhibit.get('title', '')), quote=True)}">
              </div>
              {''.join(episode_rows)}
            </section>
            """
        )

    mapping_rows: list[str] = []
    folder_scope_rows: list[str] = []
    for exhibit in status.structure.get("exhibits", []):
        episode_rows = []
        exhibit_folder = str(exhibit.get("source_folder", ""))
        exhibit_options = _render_directory_options(
            directory_catalog,
            exhibit_folder,
        )
        for episode in exhibit.get("episodes", []):
            document_cards = []
            episode_folder = (
                exhibit_folder
                if episode.get("kind") == "direct"
                else str(episode.get("source_folder", ""))
            )
            if episode.get("kind") == "direct":
                episode_scope = "<p class='muted small'>Documents below use the Exhibit folder directly.</p>"
            else:
                episode_options = _render_directory_options(
                    [
                        item
                        for item in directory_catalog
                        if exhibit_folder
                        and _is_same_or_nested_directory(
                            str(item.get("directory", "")),
                            exhibit_folder,
                        )
                        and str(item.get("directory", "")) != exhibit_folder
                    ],
                    episode_folder,
                    include_blank=not exhibit_folder,
                    blank_label="Choose episode folder after Exhibit folder is selected",
                )
                episode_scope = (
                    f"""
                    <label><strong>Episode folder</strong>
                      <select name="episode_folder_{escape(str(episode.get('id', '')))}">
                        {episode_options}
                      </select>
                    </label>
                    """
                    if exhibit_folder
                    else "<p class='muted small'>Select the Exhibit folder first, then pick the episode folder.</p>"
                )
            candidate_files = _files_for_directory(directory_catalog, episode_folder)
            for document in episode.get("documents", []):
                document_id = str(document.get("id", ""))
                mapping = status.mappings.get(document_id, {})
                original_paths = list(mapping.get("original_paths", []))
                translation_paths = list(mapping.get("translation_paths", []))
                original_list = _render_mapping_list(case_id, document_id, "original", original_paths)
                translation_list = _render_mapping_list(case_id, document_id, "translation", translation_paths)
                choices_html = _render_document_choices(
                    case_id,
                    document_id,
                    candidate_files,
                    original_paths,
                    bool(episode_folder),
                )
                document_cards.append(
                    f"""
                    <article class="layout-mapping-card">
                      <div class="layout-mapping-head">
                        <div>
                          <strong>{escape(str(document.get('number', '')))} {escape(str(document.get('title', '')))}</strong>
                          <p class="muted small">{len(original_paths)} original file(s), {len(translation_paths)} translation file(s)</p>
                        </div>
                      </div>
                      <div class="layout-mapping-columns">
                        <section>
                          <h4>Original files</h4>
                          {original_list}
                          {choices_html}
                        </section>
                        <section>
                          <h4>Translation files</h4>
                          {translation_list}
                          <form method="post">
                            <input type="hidden" name="case" value="{escape(case_id)}">
                            <input type="hidden" name="action" value="layout_add_mapping">
                            <input type="hidden" name="document_id" value="{escape(document_id)}">
                            <input type="hidden" name="mapping_kind" value="translation">
                            <button class="secondary">Add translation file</button>
                          </form>
                        </section>
                      </div>
                    </article>
                    """
                )
            episode_title = (
                f"{episode.get('number', '')} {episode.get('title', '')}".strip()
                if episode.get("kind") != "direct"
                else "Documents directly under this Exhibit"
            )
            episode_rows.append(
                f"""
                <details class="layout-mapping-episode" open>
                  <summary>{escape(str(episode_title))}</summary>
                  <div class="layout-scope-box">{episode_scope}</div>
                  {''.join(document_cards)}
                </details>
                """
            )
        folder_scope_rows.append(
            f"""
            <section class="layout-mapping-exhibit">
              <h3>Exhibit {escape(str(exhibit.get('number', '')))} {escape(str(exhibit.get('title', '')))}</h3>
              <label><strong>Exhibit folder</strong>
                <select name="exhibit_folder_{escape(str(exhibit.get('id', '')))}">
                  {exhibit_options}
                </select>
              </label>
              <p class="muted small">Choose the folder in the originals directory that matches this Exhibit. If the Exhibit contains episodes, the episode folders are then narrowed to this folder.</p>
              {''.join(
                  f"<p class='muted small'><code>{escape(str(episode.get('number', '')))}</code> {escape(str(episode.get('title', '') or 'Direct exhibit documents'))}</p>"
                  for episode in exhibit.get('episodes', [])
                  if episode.get('kind') != 'direct'
              )}
            </section>
            """
        )
        mapping_rows.append(
            f"""
            <section class="layout-mapping-exhibit">
              <h3>Exhibit {escape(str(exhibit.get('number', '')))} {escape(str(exhibit.get('title', '')))}</h3>
              {''.join(episode_rows)}
            </section>
            """
        )

    build_exhibits: list[str] = []
    for exhibit in status.structure.get("exhibits", []):
        exhibit_number = str(exhibit.get("number", ""))
        document_rows = []
        for episode in exhibit.get("episodes", []):
            for document in episode.get("documents", []):
                document_id = str(document.get("id", ""))
                mapping = status.mappings.get(document_id, {})
                has_original = bool(mapping.get("original_paths"))
                document_rows.append(
                    f"""
                    <label class="bundle-document {'missing' if not has_original else ''}">
                      <input type="checkbox" name="select_layout_document_{escape(document_id)}" data-exhibit="{escape(exhibit_number)}"{' checked' if document_id in selected_documents else ''}>
                      <span><code>{escape(str(document.get('number', '')))}</code> {escape(str(document.get('title', '')))}</span>
                      <small>{'mapped' if has_original else 'needs original file'}</small>
                    </label>
                    """
                )
        build_exhibits.append(
            f"""
            <details class="bundle-exhibit" open>
              <summary>
                <label>
                  <input type="checkbox" name="select_layout_exhibit_{escape(exhibit_number)}" data-exhibit-toggle="{escape(exhibit_number)}"{' checked' if exhibit_number in selected_exhibits else ''}>
                  <strong>Exhibit {escape(exhibit_number)} {escape(str(exhibit.get('title', '')))}</strong>
                </label>
              </summary>
              <div class="bundle-documents">{''.join(document_rows)}</div>
            </details>
            """
        )

    preview_link = (
        f'<a class="action-link" href="/layout-artifact?case={quote(case_id)}&kind=preview" target="_blank">Open separator preview PDF</a>'
        if status.has_preview
        else ""
    )
    final_link = (
        f'<a class="action-link" href="/layout-artifact?case={quote(case_id)}&kind=final" target="_blank">Open final PDF</a>'
        if status.has_final
        else ""
    )
    unmapped_notice = (
        '<div class="alert error"><strong>Some documents still need originals.</strong><ul>'
        + "".join(
            f"<li><code>{escape(item['document_number'])}</code> {escape(item['document_title'])}</li>"
            for item in status.unmapped_documents[:40]
        )
        + ("<li>…</li>" if len(status.unmapped_documents) > 40 else "")
        + "</ul></div>"
        if status.unmapped_documents
        else '<div class="alert ok"><strong>All logical documents already have at least one original file attached.</strong></div>'
    )

    return page(
        f"Document layout - {case_id}",
        f"""
        {_stage_nav(case_id, "document-layout")}
        {alert(_single(params, 'message'), 'ok')}
        {alert(_single(params, 'error'), 'error')}
        <section class="panel">
          <div class="progress-heading"><div><h1>Standalone document layout</h1><p class="muted">3-stage isolated workflow for parsing an exhibit list, attaching real files, and assembling a PDF.</p></div><strong>{_safe_progress(case_id).completion_percent}%</strong></div>
          <div class="progress-bar"><span style="width:{_safe_progress(case_id).completion_percent}%"></span></div>
          <div class="layout-summary-grid">
            <div><strong>{status.exhibit_count}</strong><span>Exhibits</span></div>
            <div><strong>{status.episode_count}</strong><span>Episodes</span></div>
            <div><strong>{status.document_count}</strong><span>Logical documents</span></div>
            <div><strong>{status.fully_mapped_document_count}/{status.document_count}</strong><span>Mapped to originals</span></div>
          </div>
          {preview_link}
          {final_link}
        </section>
        <section class="bundle-pipeline">
          <div class="pipeline-phase {stage_one_class}"><span class="phase-number">1</span><h2>Folders and parsing</h2><p>Choose source folders and the exhibit-list document, then scan files and parse the structure.</p></div>
          <div class="pipeline-arrow" aria-hidden="true">→</div>
          <div class="pipeline-phase {stage_two_class}"><span class="phase-number">2</span><h2>Attach files</h2><p>For every logical document, attach one or more original files and optional translations.</p></div>
          <div class="pipeline-arrow" aria-hidden="true">→</div>
          <div class="pipeline-phase {stage_three_class}"><span class="phase-number">3</span><h2>Preview and build</h2><p>Open the separator-only preview or assemble a selected final PDF bundle.</p></div>
        </section>
        <section class="panel">
          <h2>Stage 1 · Choose folders and parse</h2>
          <div class="layout-picker-grid">
            <div class="layout-picker-row"><div><strong>Originals folder</strong><div class="path-box">{escape(settings.get('originals_dir', '') or 'Not selected yet')}</div></div>{post_button(case_id, "layout_pick_originals_dir", "Choose folder")}</div>
            <div class="layout-picker-row"><div><strong>Translations folder</strong><div class="path-box">{escape(settings.get('translations_dir', '') or 'Optional')}</div></div>{post_button(case_id, "layout_pick_translations_dir", "Choose folder")}</div>
            <div class="layout-picker-row"><div><strong>Exhibit list document</strong><div class="path-box">{escape(settings.get('list_document_path', '') or 'Not selected yet')}</div></div>{post_button(case_id, "layout_pick_list_document", "Choose file")}</div>
            <div class="layout-picker-row"><div><strong>Layout font</strong><div class="path-box">{escape(font_family)}</div></div><div class="muted small">Used for generated separator pages and text-based conversions.</div></div>
          </div>
          <form method="post" class="stack">
            <input type="hidden" name="case" value="{escape(case_id)}">
            <input type="hidden" name="action" value="layout_parse_sources">
            <input name="originals_dir" value="{escape(settings.get('originals_dir', ''), quote=True)}" placeholder="Folder with original documents">
            <input name="translations_dir" value="{escape(settings.get('translations_dir', ''), quote=True)}" placeholder="Optional folder with translations">
            <input name="list_document_path" value="{escape(settings.get('list_document_path', ''), quote=True)}" placeholder="DOCX / PDF / TXT with the exhibit list">
            <label><strong>Font for generated pages</strong><select name="font_family">{font_options}</select></label>
            <button>Scan folders and parse list</button>
          </form>
          {inventory_html}
        </section>
        <section class="panel {'panel-disabled' if not status.stage1_complete else ''}">
          <h2>Stage 1 output · Refine numbering and titles</h2>
          {'' if status.stage1_complete else '<p class="muted">This unlocks after Stage 1 parsing succeeds.</p>'}
          {'' if status.stage1_complete else ''}
          {(
            '<form method="post" class="stack"><input type="hidden" name="case" value="'
            + escape(case_id)
            + '"><input type="hidden" name="action" value="layout_save_structure">'
            + ''.join(structure_rows)
            + '<div class="button-row">'
            + '<button>Save titles and numbering</button>'
            + '</div></form>'
          ) if status.stage1_complete else ''}
          {(
            '<div class="button-row">'
            + post_button(case_id, "layout_preview", "Build separator preview PDF")
            + (preview_link or '')
            + '</div>'
          ) if status.stage1_complete else ''}
        </section>
        <section class="panel {'panel-disabled' if not status.stage2_available else ''}">
          <h2>Stage 2 · Attach one or more files to each logical document</h2>
          {'' if status.stage2_available else '<p class="muted">This unlocks after Stage 1 parsing succeeds.</p>'}
          {unmapped_notice if status.stage2_available else ''}
          {(
            '<form method="post" class="stack"><input type="hidden" name="case" value="'
            + escape(case_id)
            + '"><input type="hidden" name="action" value="layout_save_folder_scopes">'
            + ''.join(folder_scope_rows)
            + '<div class="button-row"><button>Save exhibit and episode folders</button></div></form>'
          ) if status.stage2_available else ''}
          {''.join(mapping_rows) if status.stage2_available else ''}
        </section>
        <section class="panel {'panel-disabled' if not status.stage3_available else ''}">
          <h2>Stage 3 · Select exhibits/documents and build PDF</h2>
          {'' if status.stage3_available else '<p class="muted">Attach at least one original file before this stage becomes active.</p>'}
          {(
            '<form method="post" class="bundle-selection" data-bundle-selection>'
            + f'<input type="hidden" name="case" value="{escape(case_id)}">'
            + '<input type="hidden" name="action" value="layout_build">'
            + '<div class="button-row"><button type="button" class="secondary" data-select-all>Select all</button><button type="button" class="secondary" data-clear-all>Clear all</button></div>'
            + ''.join(build_exhibits)
            + '<div class="button-row"><button>Build selected final PDF</button></div></form>'
          ) if status.stage3_available else ''}
          {preview_link if status.stage3_available else ''}
        </section>
        """,
    )


def _render_llm_unit(case_id: str, unit: LLMUnit, selected_key: str = "") -> str:
    status_labels = {
        "completed": "Completed",
        "validated": "Validated",
        "output_received": "Output received",
        "waiting_for_output": "Waiting for LLM output",
        "pending": "Pending",
    }
    episode = f"<small>Episode: {escape(unit.episode_folder or unit.episode_id)}</small>" if unit.episode_id else ""
    document_list = "".join(
        f"<li><code>{escape(document_id)}</code> — {escape(title)}</li>"
        for document_id, title in unit.selected_documents
    )
    documents = (
        f"<details><summary>Documents for prompt ({len(unit.selected_documents)})</summary><ul>{document_list}</ul></details>"
        if unit.selected_documents
        else "<small>Documents for prompt: none indexed</small>"
    )
    prompt_links = "".join(
        f'<a href="/llm?case={quote(case_id)}&step={quote(unit.step_id)}&episode={quote(unit.episode_id)}&prompt={quote(prompt_id)}">{escape(prompt_id)}</a>'
        for prompt_id in unit.prompt_ids
    )
    retry = (
        f'<a class="retry-link" href="/llm?case={quote(case_id)}&redo={quote(unit.step_id)}'
        f'&episode={quote(unit.episode_id)}">Retry / overwrite</a>'
        if unit.status != "pending"
        else ""
    )
    return f"""
    <article class="llm-unit {escape(unit.status)}{' current' if unit.current else ''}{' selected' if unit.key == selected_key else ''}">
      <div class="llm-unit-title"><a class="unit-select" href="/llm?case={quote(case_id)}&step={quote(unit.step_id)}&episode={quote(unit.episode_id)}"><strong>{escape(unit.title)}</strong></a><span>{escape(status_labels.get(unit.status, unit.status))}</span></div>
      <small>{escape(unit.criterion_label)}</small>{episode}
      <code>{escape(unit.key)}</code>
      {documents}
      <form method="post" class="document-refresh-form">
        <input type="hidden" name="action" value="refresh_unit_documents"><input type="hidden" name="case" value="{escape(case_id)}">
        <input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}">
        <button type="submit" class="secondary small-button">Refresh documents</button>
      </form>
      <div class="prompt-id-list">{prompt_links}</div>
      {retry}
    </article>
    """


def _render_llm_current(
    case_id: str,
    stage: LLMStage,
    unit: LLMUnit | None,
    prompt_text: str,
    selected_prompt: str,
    redo: bool,
    dependency_warning: str = "",
    custom_instructions: str = "",
) -> str:
    if unit is None:
        if stage.complete:
            return (
                '<section class="panel"><h2>LLM drafting complete</h2>'
                f'<p>All configured drafting units are complete.</p><a class="action-link" href="/layout?case={quote(case_id)}">Continue to layout</a></section>'
            )
        return f"""
        <section class="panel">
          <h2>Next action is blocked</h2>
          <p>{escape(stage.current_reason or stage.current_action_type)}</p>
          <form method="post"><input type="hidden" name="action" value="run_next"><input type="hidden" name="case" value="{escape(case_id)}"><button>Check next step</button></form>
        </section>
        """

    episode_text = (
        f'<p><strong>Criterion:</strong> {escape(unit.criterion_label)}<br><strong>Episode:</strong> {escape(unit.episode_folder or unit.episode_id)} <code>{escape(unit.episode_id)}</code></p>'
        if unit.episode_id
        else f'<p><strong>Section:</strong> {escape(unit.criterion_label)}</p>'
    )
    warning_html = (
        f'<section class="panel warning-panel"><h2>Dependency warning</h2><p>{escape(dependency_warning)}</p></section>'
        if dependency_warning
        else ""
    )
    prompt_section = ""
    if prompt_text:
        prompt_section = f"""
        <section class="panel">
          <div class="progress-heading"><div><h2>Current prompt</h2><p class="muted"><code>{escape(selected_prompt)}</code></p></div>
            <div class="button-row">
              <form method="post" data-confirm-submit="Refresh this generated prompt from the current documents and instructions?">
                <input type="hidden" name="action" value="build_prompt"><input type="hidden" name="case" value="{escape(case_id)}">
                <input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}">
                <input type="hidden" name="episode_folder" value="{escape(unit.episode_folder)}"><input type="hidden" name="force" value="on">
                <input type="hidden" name="redo_step" value="{escape(unit.step_id)}"><input type="hidden" name="redo_episode" value="{escape(unit.episode_id)}">
                <input type="hidden" name="custom_instructions" value="{escape(custom_instructions, quote=True)}">
                <button type="submit" class="secondary">Refresh prompt</button>
              </form>
              <button type="button" class="secondary" data-copy-target="current-prompt">Copy prompt</button>
            </div>
          </div>
          <textarea id="current-prompt" readonly rows="18">{escape(prompt_text)}</textarea>
        </section>
        """
    elif unit.latest_prompt:
        prompt_section = f"""
        <section class="panel">
          <h2>Current prompt</h2>
          <p class="muted">A latest prompt exists for this unit, but it was not loaded into the viewer. Reload this page or open <code>{escape(unit.latest_prompt)}</code> from the timeline.</p>
        </section>
        """

    action_section = ""
    if redo:
        action_section += f"""
        <section class="panel warning-panel">
          <h2>Retry an existing drafting unit</h2>
          <p>This unit has already been started or completed. Refreshing its prompt is safe; importing the resulting JSON will replace its saved result and the corresponding text in working_memo.docx after confirmation.</p>
        </section>
        """
    unit_action_type = _unit_action_type(unit)
    if not redo and unit_action_type == "insert_section":
        action_section += f"""
        <section class="panel"><h2>Insert validated output</h2>
          <form method="post"><input type="hidden" name="action" value="insert_section"><input type="hidden" name="case" value="{escape(case_id)}"><input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}"><button>Insert and refresh Word</button></form>
        </section>
        """

    prompt_started = unit.status != "pending" or bool(prompt_text)
    custom_force_fields = (
        '<input type="hidden" name="force" value="on">'
        f'<input type="hidden" name="redo_step" value="{escape(unit.step_id)}"><input type="hidden" name="redo_episode" value="{escape(unit.episode_id)}">'
        if prompt_started
        else ""
    )
    custom_confirm = (
        ' data-confirm-submit="Rebuild this unit prompt with the custom instructions below? The saved prompt text will be replaced."'
        if prompt_started
        else ""
    )
    custom_button = "Refresh prompt" if prompt_started else "Generate prompt"
    custom_section = f"""
    <section class="panel compact-panel">
      <h2>Optional custom instructions</h2>
      <p class="muted small">Add one-off strategy, style, emphasis, or drafting rules for this section. They are saved for this unit and inserted into the prompt as the highest-priority custom block.</p>
      <form method="post" class="stack"{custom_confirm}>
        <input type="hidden" name="action" value="build_prompt"><input type="hidden" name="case" value="{escape(case_id)}">
        <input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}">
        <input type="hidden" name="episode_folder" value="{escape(unit.episode_folder)}">{custom_force_fields}
        <textarea name="custom_instructions" rows="4" placeholder="Optional: emphasize specific facts, follow a preferred structure, avoid a phrase, address a strategic point...">{escape(custom_instructions)}</textarea>
        <button>{custom_button}</button>
      </form>
    </section>
    """

    can_accept_output = bool(prompt_text) and (redo or unit_action_type == "await_llm_output")
    output_section = ""
    if can_accept_output:
        force_fields = (
            '<input type="hidden" name="force" value="on">'
            f'<input type="hidden" name="redo_step" value="{escape(unit.step_id)}"><input type="hidden" name="redo_episode" value="{escape(unit.episode_id)}">'
            if redo
            else ""
        )
        confirm_attr = (
            ' data-confirm-submit="This will overwrite the existing validated output, draft section, and Word memorandum text. Continue?"'
            if redo
            else ""
        )
        output_section = f"""
        <section class="panel">
          <h2>Paste LLM JSON output</h2>
          <p>The technical identifiers are filled automatically.</p>
          <div class="metadata-chips"><code>step_id: {escape(unit.step_id)}</code>{f'<code>episode_id: {escape(unit.episode_id)}</code>' if unit.episode_id else ''}</div>
          <form method="post" class="stack"{confirm_attr}>
            <input type="hidden" name="action" value="import_output"><input type="hidden" name="case" value="{escape(case_id)}">
            <input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}">
            <textarea name="output_json" rows="18" placeholder="Paste one complete JSON object returned by the LLM" required></textarea>
            <input type="hidden" name="insert_after_import" value="on">{force_fields}
            <button>Validate, insert into Word, and prepare next prompt</button>
          </form>
        </section>
        """

    return f"""
    <section class="panel current-step-panel">
      <p class="eyebrow">{'Retrying' if redo else 'Current drafting unit'} · {escape(unit.key)}</p>
      <h1>{escape(unit.title)}</h1>
      {episode_text}
      <p>{escape(unit.objective)}</p>
      <p class="muted">You may work on any drafting unit. Importing a valid response inserts its petition text into Word and updates progress.</p>
      <details open><summary><strong>Documents for this prompt ({len(unit.selected_documents)})</strong></summary>
        {('<ul>' + ''.join(f'<li><code>{escape(document_id)}</code> — {escape(title)}</li>' for document_id, title in unit.selected_documents) + '</ul>') if unit.selected_documents else '<p class="muted small">No indexed documents are currently assigned to this prompt.</p>'}
        <form method="post" class="document-refresh-form">
          <input type="hidden" name="action" value="refresh_unit_documents"><input type="hidden" name="case" value="{escape(case_id)}">
          <input type="hidden" name="step" value="{escape(unit.step_id)}"><input type="hidden" name="episode_id" value="{escape(unit.episode_id)}">
          <button type="submit" class="secondary small-button">Refresh document list</button>
        </form>
      </details>
    </section>
    {warning_html}{action_section}{custom_section}{prompt_section}{output_section}
    """


def _unit_action_type(unit: LLMUnit) -> str:
    if unit.status == "pending":
        return "build_prompt"
    if unit.status in {"waiting_for_output", "output_received"}:
        return "await_llm_output"
    if unit.status == "validated":
        return "insert_section"
    return "completed"


def _dependency_warning(stage: LLMStage, unit: LLMUnit | None) -> str:
    if unit is None:
        return ""
    if unit.step_id == "final_overview":
        excluded = {"opening_context_intake", "template_review", "final_overview"}
        unfinished = [candidate for candidate in stage.units if candidate.step_id not in excluded and not candidate.complete]
        if unfinished:
            return (
                f"Final overview is a synthesis step, but {len(unfinished)} substantive drafting unit(s) are still incomplete. "
                "You can proceed, but the overview will reflect only the memorandum text currently available and should be regenerated later."
            )
    phase_pairs = {
        "criterion_original_contribution_significance": "criterion_original_contribution_fact",
        "criterion_leading_critical_role_reputation": "criterion_leading_critical_role_fact",
        "criterion_high_salary_comparison": "criterion_high_salary_fact",
        "o1b_criterion_iii_reputation": "o1b_criterion_iii_role",
        "o1b_criterion_vi_comparison": "o1b_criterion_vi_compensation",
    }
    prerequisite = phase_pairs.get(unit.step_id, "")
    if prerequisite:
        first_phase = _find_llm_unit(stage, prerequisite, unit.episode_id)
        if first_phase and not first_phase.complete:
            return "This is phase 2 for the selected item. Phase 1 is not complete, so the prompt may lack the settled factual foundation."
    return ""


def _find_llm_unit(stage: LLMStage, step_id: str, episode_id: str = "") -> LLMUnit | None:
    return next(
        (
            unit
            for unit in stage.units
            if unit.step_id == step_id and (unit.episode_id or "") == (episode_id or "")
        ),
        None,
    )


def _task_type_label(task_type: str) -> str:
    return {
        "eb1a_petition": "EB1A petition",
        "o1b_petition": "O-1B petition",
        "eb1a_rfe_response": "EB1A RFE response",
        "document_layout": "Document layout",
    }.get(task_type, task_type)


def _stage_nav(case_id: str, active: str) -> str:
    if _safe_case_task_type(case_id) == "document_layout":
        links = (
            ("overview", "Overview", f"/case?case={quote(case_id)}"),
            ("document-layout", "Document layout workflow", f"/document-layout?case={quote(case_id)}"),
        )
        return '<nav class="stage-nav">' + "".join(
            f'<a class="{"active" if key == active else ""}" href="{href}">{escape(label)}</a>'
            for key, label, href in links
        ) + "</nav>"
    links = (
        ("overview", "Overview", f"/case?case={quote(case_id)}"),
        ("intake", "1. Intake & evidence", f"/intake?case={quote(case_id)}"),
        ("llm", "2. LLM drafting", f"/llm?case={quote(case_id)}"),
        ("layout", "3. Layout & bundle", f"/layout?case={quote(case_id)}"),
    )
    return '<nav class="stage-nav">' + "".join(
        f'<a class="{"active" if key == active else ""}" href="{href}">{escape(label)}</a>'
        for key, label, href in links
    ) + "</nav>"


def _stage_card(number: str, title: str, percent: int, detail: str, href: str, action: str) -> str:
    return f"""
    <section class="panel stage-card">
      <p class="eyebrow">Stage {escape(number)}</p><div class="progress-heading"><h2>{escape(title)}</h2><strong>{percent}%</strong></div>
      <div class="progress-bar"><span style="width:{percent}%"></span></div><p>{escape(detail)}</p>
      <a class="action-link" href="{href}">{escape(action)}</a>
    </section>
    """


def _render_inventory_group(label: str, items: list[dict[str, str]]) -> str:
    rows = "".join(
        f"<li><code>{escape(item.get('relative_path', ''))}</code></li>" for item in items[:120]
    )
    more = "<li>…</li>" if len(items) > 120 else ""
    return f"<section><h3>{escape(label)}</h3><ul class='layout-inventory-list'>{rows}{more}</ul></section>"


def _render_mapping_list(case_id: str, document_id: str, kind: str, paths: list[str]) -> str:
    if not paths:
        return "<p class='muted small'>No files attached yet.</p>"
    rows = []
    for index, path in enumerate(paths):
        rows.append(
            f"""
            <div class="layout-mapping-pill">
              <code>{escape(Path(path).name)}</code>
              <form method="post">
                <input type="hidden" name="case" value="{escape(case_id)}">
                <input type="hidden" name="action" value="layout_remove_mapping">
                <input type="hidden" name="document_id" value="{escape(document_id)}">
                <input type="hidden" name="mapping_kind" value="{escape(kind)}">
                <input type="hidden" name="mapping_index" value="{index}">
                <button class="secondary small-button">Remove</button>
              </form>
            </div>
            """
        )
    return "".join(rows)


def _render_directory_options(
    directories: list[dict[str, object]],
    selected: str,
    *,
    include_blank: bool = True,
    blank_label: str = "Choose folder",
) -> str:
    options: list[str] = []
    if include_blank:
        options.append(
            f'<option value=""{" selected" if not selected else ""}>{escape(blank_label)}</option>'
        )
    for item in directories:
        directory = str(item.get("directory", ""))
        depth = int(item.get("depth", 0))
        prefix = "&nbsp;" * max(depth - 1, 0) * 4
        label = prefix + escape(str(item.get("label", directory or "[root]")))
        options.append(
            f'<option value="{escape(directory, quote=True)}"{" selected" if directory == selected else ""}>{label}</option>'
        )
    return "".join(options)


def _is_same_or_nested_directory(directory: str, parent: str) -> bool:
    if not parent:
        return True
    return directory == parent or directory.startswith(parent + "/")


def _files_for_directory(
    directories: list[dict[str, Any]], directory: str
) -> list[dict[str, str]]:
    for item in directories:
        if str(item.get("directory", "")) == directory:
            return [dict(file_entry) for file_entry in item.get("files", [])]
    return []


def _render_document_choices(
    case_id: str,
    document_id: str,
    candidate_files: list[dict[str, str]],
    selected_paths: list[str],
    folder_ready: bool,
) -> str:
    if not folder_ready:
        return "<p class='muted small'>Choose the Exhibit/Episode folder first.</p>"
    if not candidate_files:
        return "<p class='muted small'>No files were found directly inside the selected folder.</p>"
    selected_set = {str(Path(path).expanduser().resolve()) for path in selected_paths}
    choice_rows = []
    for index, file_entry in enumerate(candidate_files, start=1):
        absolute_path = str(Path(file_entry.get("path", "")).expanduser().resolve())
        checked = " checked" if absolute_path in selected_set else ""
        choice_rows.append(
            f"""
            <label class="layout-choice-row">
              <input type="checkbox" name="original_choice_{index}" value="{escape(absolute_path, quote=True)}"{checked}>
              <span>{escape(file_entry.get('name', ''))}</span>
            </label>
            """
        )
    return (
        '<form method="post" class="stack">'
        f'<input type="hidden" name="case" value="{escape(case_id)}">'
        '<input type="hidden" name="action" value="layout_save_document_originals">'
        f'<input type="hidden" name="document_id" value="{escape(document_id)}">'
        '<div class="layout-scroll-list">'
        + "".join(choice_rows)
        + "</div>"
        + '<div class="button-row"><button class="secondary">Save selected original files</button></div></form>'
    )


def render_translation_review_page(case_id: str, params: dict[str, list[str]]) -> str:
    validate_case_id(case_id)
    case_dir = _case_dir(case_id)
    if not case_dir.exists():
        return page("Case not found", f"<p>Case not found: {escape(case_id)}</p>")
    rows = _read_case_index(case_id)
    translations = [row for row in rows if row.get("translation_status") == "translation"]
    originals = [row for row in rows if row.get("translation_status") == "original"]
    unresolved = [row for row in translations if not row.get("parent_document_id")]
    translation_search = _single(params, "translation_search").strip()
    filtered = [
        row
        for row in unresolved
        if not translation_search or _row_search_text(row).find(translation_search.casefold()) >= 0
    ]
    selected_id = _single(params, "doc").strip()
    selected = next((row for row in unresolved if row.get("document_id") == selected_id), None)
    if selected is None and filtered:
        selected = filtered[0]

    report_rows = _read_csv_file(case_dir / "reports" / "translation_link_report.csv")
    report_by_id = {row.get("translation_document_id", ""): row for row in report_rows}
    row_by_id = {row.get("document_id", ""): row for row in rows}
    linked_count = sum(bool(row.get("parent_document_id")) for row in translations)
    ambiguous_count = sum(row.get("status") == "ambiguous" for row in report_rows)
    unmatched_count = sum(row.get("status") == "unmatched" for row in report_rows)

    list_items = []
    for row in filtered[:200]:
        doc_id = row.get("document_id", "")
        report = report_by_id.get(doc_id, {})
        status = report.get("status", "unresolved")
        active = " active" if selected and selected.get("document_id") == doc_id else ""
        list_items.append(
            f'<a class="review-item{active}" href="/translations?case={quote(case_id)}&doc={quote(doc_id)}'
            f'&translation_search={quote(translation_search)}">'
            f'<strong>{escape(row.get("original_file_name", doc_id))}</strong>'
            f'<span>{escape(doc_id)} · {escape(row.get("category", ""))} · {escape(status)}</span></a>'
        )

    detail = '<section class="panel"><p>No unresolved translations match the current search.</p></section>'
    if selected is not None:
        doc_id = selected.get("document_id", "")
        report = report_by_id.get(doc_id, {})
        suggestion_ids = [match.group(1) for match in re.finditer(r"(DOC\d+)\s+\([0-9.]+\)", report.get("suggested_originals", ""))]
        suggested_originals = [row_by_id[item] for item in suggestion_ids if item in row_by_id]
        original_search = _single(params, "original_search").strip()
        search_results = []
        if original_search:
            query = _case_search_query(original_search, case_dir)
            search_results = [row for row in originals if query in _row_search_text(row)][:50]
        candidate_rows: list[tuple[dict[str, str], str]] = []
        seen_candidates: set[str] = set()
        for row in suggested_originals:
            candidate_rows.append((row, "Suggested"))
            seen_candidates.add(row.get("document_id", ""))
        for row in search_results:
            if row.get("document_id", "") not in seen_candidates:
                candidate_rows.append((row, "Search"))
        candidate_html = "".join(
            '<div class="candidate-row"><label class="candidate">'
            f'<input form="translation-link-form" type="radio" name="original_document_id" value="{escape(row.get("document_id", ""))}">'
            f'<span><strong>{escape(row.get("original_file_name", ""))}</strong><br>'
            f'<small>{escape(label)} · {escape(row.get("document_id", ""))} · {escape(row.get("file_path", ""))}</small></span>'
            '</label>'
            '<form method="post">'
            '<input type="hidden" name="action" value="open_case_file">'
            f'<input type="hidden" name="case" value="{escape(case_id)}">'
            f'<input type="hidden" name="review_doc" value="{escape(doc_id)}">'
            f'<input type="hidden" name="file_path" value="{escape(row.get("file_path", ""))}">'
            '<button class="secondary">Open original</button></form></div>'
            for row, label in candidate_rows
        )
        if not candidate_html:
            candidate_html = '<p class="muted">Search for an original below or paste its path.</p>'
        detail = f"""
        <section class="panel review-detail">
          <p class="eyebrow">{escape(report.get('status', 'unresolved'))} · {escape(doc_id)}</p>
          <h2>{escape(selected.get('original_file_name', ''))}</h2>
          <p class="path-box">{escape(selected.get('file_path', ''))}</p>
          <form method="post" class="inline-form">
            <input type="hidden" name="action" value="open_case_file">
            <input type="hidden" name="case" value="{escape(case_id)}">
            <input type="hidden" name="review_doc" value="{escape(doc_id)}">
            <input type="hidden" name="file_path" value="{escape(selected.get('file_path', ''))}">
            <button>Open translation in File Explorer</button>
          </form>
          <h3>Find the original</h3>
          <form method="get" action="/translations" class="inline-form">
            <input type="hidden" name="case" value="{escape(case_id)}">
            <input type="hidden" name="doc" value="{escape(doc_id)}">
            <input name="original_search" value="{escape(original_search)}" placeholder="Search original filename or path">
            <button>Search originals</button>
          </form>
          <div class="candidate-list">{candidate_html}</div>
          <form id="translation-link-form" method="post" class="stack candidate-form">
            <input type="hidden" name="action" value="manual_link_translation">
            <input type="hidden" name="case" value="{escape(case_id)}">
            <input type="hidden" name="translation_document_id" value="{escape(doc_id)}">
            <label>Or paste an original document ID, relative path, or full path</label>
            <input name="original_path" placeholder="DOC0123 or source_documents/originals/... or C:\\...">
            <label><input type="checkbox" name="allow_shared_original"> Keep prior links too (one original intentionally has multiple translations)</label>
            <button>Confirm translation link</button>
          </form>
        </section>
        """

    return page(
        f"Translation review · {case_id}",
        f"""
        <div class="case-nav"><a href="/case?case={quote(case_id)}">&larr; Back to case</a>{render_case_switch(case_id)}</div>
        {alert(_single(params, 'message'), 'ok')}
        {alert(_single(params, 'error'), 'error')}
        <section class="panel">
          <h1>Translation matching review</h1>
          <p><strong>{linked_count}/{len(translations)}</strong> linked · {ambiguous_count} ambiguous · {unmatched_count} unmatched</p>
          <form method="get" action="/translations" class="inline-form">
            <input type="hidden" name="case" value="{escape(case_id)}">
            <input name="translation_search" value="{escape(translation_search)}" placeholder="Search unresolved translations">
            <button>Search translations</button>
          </form>
        </section>
        <div class="review-layout">
          <section class="panel review-list">
            <h2>Unresolved files ({len(unresolved)})</h2>
            {''.join(list_items) if list_items else '<p class="muted">No files.</p>'}
          </section>
          {detail}
        </div>
        """,
    )


def render_case_switch(current_case: str = "") -> str:
    options = []
    for case_id in list_cases():
        progress = _safe_progress(case_id)
        label = f"{progress.beneficiary_name} — {progress.stage_label}"
        options.append(f'<option value="{escape(case_id)}" label="{escape(label)}"></option>')
    return f"""
    <form method="get" action="/case" class="case-switch">
      <input name="case" list="case-library-options" value="{escape(current_case)}" placeholder="Search case by surname or ID" required>
      <datalist id="case-library-options">{''.join(options)}</datalist>
      <button>Open case</button>
    </form>
    """


def render_case_progress(progress: CaseProgress) -> str:
    items = []
    for step in progress.steps:
        status = "done" if step.complete else "current" if step.current else "pending"
        symbol = "✓" if step.complete else "→" if step.current else "·"
        items.append(
            f'<li class="progress-step {status}"><span class="progress-symbol">{symbol}</span>'
            f'<div><strong>{escape(step.label)}</strong><small>{escape(step.detail)}</small></div></li>'
        )
    return f"""
    <section class="panel">
      <div class="progress-heading"><div><h2>Case progress</h2><p class="muted">Current stage: {escape(progress.stage_label)}</p></div><strong>{progress.completion_percent}%</strong></div>
      <div class="progress-bar"><span style="width:{progress.completion_percent}%"></span></div>
      <ol class="progress-list">{''.join(items)}</ol>
    </section>
    """


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/png" href="/favicon.ico">
  <title>{escape(title)}</title>
  <style>
    :root {{ --bg:#f6f7fb; --panel:#fff; --ink:#1f2937; --muted:#6b7280; --line:#d8dee9; --brand:#1d4ed8; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: "Segoe UI", Arial, sans-serif; color:var(--ink); background:var(--bg); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1, h2 {{ margin-top: 0; }}
    a {{ color: var(--brand); text-decoration: none; }}
    .panel {{ background: var(--panel); border:1px solid var(--line); border-radius:16px; padding:20px; margin-bottom:18px; box-shadow:0 1px 2px #0000000d; }}
    .hero {{ display:flex; align-items:center; justify-content:space-between; gap:24px; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap:14px; }}
    .case-card {{ display:flex; flex-direction:column; gap:8px; background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px; color:var(--ink); }}
    .case-card span {{ color:var(--muted); }}
    .muted {{ color:var(--muted); }}
    .small {{ font-size: 0.92rem; }}
    .columns {{ display:grid; grid-template-columns: 1fr 1fr; gap:18px; }}
    fieldset {{ border:1px solid var(--line); border-radius:12px; padding:14px; }}
    legend {{ padding:0 6px; font-weight:700; }}
    .check-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 18px; }}
    .check-grid label {{ display:flex; align-items:center; gap:8px; }}
    .check-grid input {{ width:auto; }}
    .inline-form, .button-row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .stack {{ display:flex; flex-direction:column; gap:10px; }}
    input, select, textarea {{ width:100%; border:1px solid var(--line); border-radius:10px; padding:10px 12px; font:inherit; background:#fff; }}
    .inline-form input, .inline-form select {{ width:auto; min-width:190px; }}
    textarea {{ font-family: Consolas, "Courier New", monospace; }}
    table {{ width:100%; border-collapse:collapse; margin:10px 0 18px; }}
    td {{ border-top:1px solid var(--line); padding:8px 6px; vertical-align:top; }}
    code {{ background:#f3f4f6; border-radius:6px; padding:2px 5px; }}
    hr {{ border:0; border-top:1px solid var(--line); margin:18px 0; }}
    button {{ border:0; border-radius:10px; padding:10px 14px; background:var(--brand); color:#fff; font-weight:600; cursor:pointer; }}
    button:disabled {{ background:#9ca3af; cursor:not-allowed; }}
    button.secondary {{ background:#374151; }}
    button.small-button {{ padding:6px 9px; font-size:.82rem; }}
    .document-refresh-form {{ margin-top:8px; }}
    .document-refresh-form input {{ display:none; }}
    pre {{ white-space:pre-wrap; background:#0f172a; color:#e5e7eb; border-radius:12px; padding:14px; overflow:auto; max-height:420px; }}
    .alert {{ border-radius:12px; padding:12px 14px; margin-bottom:16px; white-space:pre-wrap; }}
    .ok {{ background:#ecfdf5; border:1px solid #a7f3d0; }}
    .error {{ background:#fef2f2; border:1px solid #fecaca; }}
    .case-nav {{ display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:18px; }}
    .case-switch {{ display:flex; align-items:center; gap:8px; width:min(620px, 100%); }}
    .case-switch input {{ min-width:260px; }}
    .action-link {{ display:inline-flex; align-items:center; padding:10px 14px; border-radius:10px; background:#0f766e; color:#fff; font-weight:600; }}
    .progress-heading {{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px; }}
    .progress-heading h2, .progress-heading p {{ margin-bottom:4px; }}
    .progress-heading > strong {{ font-size:1.35rem; color:var(--brand); }}
    .progress-bar {{ height:9px; overflow:hidden; border-radius:99px; background:#e5e7eb; margin:12px 0 18px; }}
    .progress-bar span {{ display:block; height:100%; border-radius:inherit; background:var(--brand); }}
    .progress-list {{ list-style:none; padding:0; margin:0; display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
    .progress-step {{ display:flex; gap:10px; padding:11px; border:1px solid var(--line); border-radius:11px; background:#f9fafb; }}
    .progress-step.current {{ border-color:#93c5fd; background:#eff6ff; }}
    .progress-step.done {{ border-color:#a7f3d0; background:#ecfdf5; }}
    .progress-step small {{ display:block; color:var(--muted); margin-top:3px; }}
    .progress-symbol {{ display:grid; place-items:center; flex:0 0 25px; height:25px; border-radius:50%; background:#e5e7eb; font-weight:800; }}
    .progress-step.done .progress-symbol {{ background:#059669; color:#fff; }}
    .progress-step.current .progress-symbol {{ background:var(--brand); color:#fff; }}
    .stage-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; margin-bottom:18px; }}
    .stage-card {{ position:relative; overflow:hidden; }}
    .stage-card::after {{ content:""; position:absolute; inset:auto -40px -60px auto; width:160px; height:160px; border-radius:50%; background:linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); opacity:.55; }}
    .stage-nav {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:18px; }}
    .stage-nav a {{ display:inline-flex; align-items:center; padding:10px 14px; border:1px solid var(--line); border-radius:999px; color:var(--ink); background:#fff; font-weight:600; }}
    .stage-nav a.active {{ border-color:#93c5fd; background:#eff6ff; color:#1e40af; }}
    .llm-layout {{ display:grid; grid-template-columns:minmax(300px, 360px) minmax(0, 1fr); gap:18px; align-items:start; }}
    .llm-timeline {{ max-height:80vh; overflow:auto; }}
    .llm-unit {{ display:flex; flex-direction:column; gap:8px; padding:13px; border:1px solid var(--line); border-radius:12px; background:#f9fafb; margin-bottom:10px; }}
    .llm-unit.current {{ border-color:#93c5fd; background:#eff6ff; }}
    .llm-unit.selected {{ outline:3px solid rgba(37,99,235,.18); border-color:#2563eb; }}
    .llm-unit.completed {{ border-color:#86efac; background:#ecfdf5; }}
    .llm-unit.validated {{ border-color:#fcd34d; background:#fffbeb; }}
    .llm-unit.output_received {{ border-color:#c4b5fd; background:#f5f3ff; }}
    .llm-unit.waiting_for_output {{ border-color:#93c5fd; background:#eff6ff; }}
    .llm-unit-title {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
    .llm-unit-title span {{ color:var(--muted); font-size:.84rem; text-align:right; }}
    .unit-select {{ color:var(--ink); text-decoration:none; }}
    .unit-select:hover {{ color:var(--accent); text-decoration:underline; }}
    .prompt-id-list {{ display:flex; flex-direction:column; gap:4px; }}
    .prompt-id-list a {{ font-size:.88rem; overflow-wrap:anywhere; }}
    .retry-link {{ font-size:.88rem; font-weight:600; }}
    .warning-panel {{ border-color:#fbbf24; background:#fffbeb; }}
    .metadata-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:6px; }}
    .metadata-chips code {{ font-size:.88rem; }}
    .current-step-panel h1 {{ margin-bottom:10px; }}
    .review-layout {{ display:grid; grid-template-columns:minmax(290px, 370px) minmax(0, 1fr); gap:18px; align-items:start; }}
    .review-list {{ max-height:72vh; overflow:auto; padding:12px; }}
    .review-list h2 {{ padding:8px; margin-bottom:4px; }}
    .review-item {{ display:flex; flex-direction:column; gap:5px; padding:11px; margin-bottom:5px; border-radius:10px; color:var(--ink); overflow-wrap:anywhere; }}
    .review-item:hover {{ background:#f3f4f6; }}
    .review-item.active {{ background:#eff6ff; outline:1px solid #93c5fd; }}
    .review-item span {{ color:var(--muted); font-size:.84rem; }}
    .review-detail {{ overflow-wrap:anywhere; }}
    .eyebrow {{ color:var(--brand); font-size:.78rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
    .path-box {{ padding:10px 12px; border-radius:10px; background:#f3f4f6; font-family:Consolas, monospace; font-size:.88rem; }}
    .candidate-form {{ margin-top:14px; }}
    .candidate-list {{ display:flex; flex-direction:column; gap:7px; max-height:360px; overflow:auto; }}
    .candidate-row {{ display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:8px; }}
    .candidate-row form {{ margin:0; }}
    .candidate {{ display:flex; align-items:flex-start; gap:10px; min-width:0; padding:10px; border:1px solid var(--line); border-radius:10px; cursor:pointer; }}
    .candidate:hover {{ border-color:#93c5fd; background:#f8fbff; }}
    .candidate input, .candidate-form label input {{ width:auto; min-width:auto; }}
    .candidate small {{ color:var(--muted); overflow-wrap:anywhere; }}
    .workflow-help {{ margin:14px 0 0; }}
    .source-folders {{ display:flex; flex-direction:column; gap:12px; }}
    .source-row {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:end; padding:12px; border:1px solid var(--line); border-radius:12px; background:#f9fafb; }}
    .source-row label {{ min-width:0; }}
    .source-row input {{ margin-top:7px; }}
    .source-actions {{ display:flex; align-items:center; justify-content:flex-end; gap:8px; flex-wrap:wrap; }}
    .source-actions code {{ max-width:320px; overflow-wrap:anywhere; }}
    .folder-link {{ display:inline-flex; align-items:center; padding:9px 11px; border:1px solid #93c5fd; border-radius:9px; background:#eff6ff; font-size:.88rem; font-weight:600; }}
    .bundle-pipeline {{ display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr); gap:12px; align-items:stretch; margin-bottom:18px; }}
    .pipeline-phase {{ position:relative; background:#fff; border:1px solid var(--line); border-radius:16px; padding:20px; }}
    .pipeline-phase.done {{ border-color:#86efac; background:#f0fdf4; }}
    .pipeline-phase.current {{ border-color:#93c5fd; background:#eff6ff; }}
    .pipeline-phase.locked {{ opacity:.62; background:#f3f4f6; }}
    .pipeline-phase h2 {{ margin:8px 0; font-size:1.1rem; }}
    .pipeline-phase p {{ font-size:.9rem; }}
    .phase-number {{ display:grid; place-items:center; width:30px; height:30px; border-radius:50%; background:#dbeafe; color:#1e40af; font-weight:800; }}
    .pipeline-phase.done .phase-number {{ background:#059669; color:#fff; }}
    .pipeline-arrow {{ align-self:center; color:var(--muted); font-size:1.8rem; font-weight:800; }}
    .bundle-selection {{ display:flex; flex-direction:column; gap:12px; }}
    .bundle-exhibit {{ border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:#f9fafb; }}
    .bundle-exhibit summary {{ cursor:pointer; }}
    .bundle-exhibit summary label, .bundle-document {{ display:flex; align-items:flex-start; gap:9px; }}
    .bundle-exhibit input {{ width:auto; flex:0 0 auto; }}
    .bundle-documents {{ display:flex; flex-direction:column; gap:7px; margin:10px 0 2px 26px; }}
    .bundle-document span {{ overflow-wrap:anywhere; }}
    .bundle-document.missing {{ border:1px dashed #fca5a5; border-radius:10px; padding:8px; background:#fff7f7; }}
    .bundle-document small {{ color:var(--muted); }}
    .panel-disabled {{ opacity:.68; }}
    .layout-summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-top:12px; }}
    .layout-summary-grid div {{ border:1px solid var(--line); border-radius:12px; padding:12px; background:#f9fafb; }}
    .layout-summary-grid strong {{ display:block; font-size:1.35rem; color:var(--brand); }}
    .layout-summary-grid span {{ color:var(--muted); font-size:.88rem; }}
    .layout-picker-grid {{ display:flex; flex-direction:column; gap:12px; margin-bottom:14px; }}
    .layout-picker-row {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:end; padding:12px; border:1px solid var(--line); border-radius:12px; background:#f9fafb; }}
    .layout-picker-row form {{ margin:0; }}
    .layout-exhibit-card {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#fbfcfd; }}
    .layout-exhibit-head, .layout-episode-head, .layout-document-row {{ display:grid; grid-template-columns:120px minmax(0,1fr); gap:10px; align-items:center; }}
    .layout-exhibit-number {{ max-width:120px; }}
    .layout-episode-card {{ display:flex; flex-direction:column; gap:10px; padding:12px; border:1px solid #e5e7eb; border-radius:12px; background:#fff; }}
    .layout-document-row code, .layout-exhibit-head code, .layout-episode-head code {{ justify-self:start; }}
    .layout-mapping-exhibit {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#fbfcfd; margin-bottom:14px; }}
    .layout-mapping-episode {{ border:1px solid var(--line); border-radius:12px; padding:10px 12px; background:#fff; margin-bottom:10px; }}
    .layout-scope-box {{ margin:10px 0 14px; padding:10px 12px; border-radius:10px; background:#f8fafc; border:1px solid #e5e7eb; }}
    .layout-mapping-card {{ border:1px solid #e5e7eb; border-radius:12px; padding:14px; background:#f9fafb; margin:10px 0; }}
    .layout-mapping-columns {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
    .layout-mapping-pill {{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 10px; border-radius:10px; background:#fff; border:1px solid #e5e7eb; margin-bottom:8px; }}
    .layout-scroll-list {{ max-height:220px; overflow:auto; padding:8px; border:1px solid #d1d5db; border-radius:10px; background:#fff; }}
    .layout-choice-row {{ display:flex; align-items:flex-start; gap:9px; padding:7px 6px; border-bottom:1px solid #f1f5f9; }}
    .layout-choice-row:last-child {{ border-bottom:0; }}
    .layout-choice-row input {{ width:auto; min-width:auto; }}
    .inventory-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin-top:12px; }}
    .layout-inventory-list {{ max-height:260px; overflow:auto; padding-left:18px; }}
    @media (max-width: 850px) {{
      .hero, .columns {{ display:block; }}
      .check-grid {{ grid-template-columns:1fr; }}
      .case-nav {{ align-items:flex-start; flex-direction:column; }}
      .case-switch {{ flex-wrap:wrap; }}
      .case-switch input {{ min-width:0; flex:1 1 230px; }}
      .llm-layout {{ grid-template-columns:1fr; }}
      .review-layout {{ grid-template-columns:1fr; }}
      .review-list {{ max-height:45vh; }}
      .source-row {{ grid-template-columns:1fr; }}
      .source-actions {{ justify-content:flex-start; }}
      .bundle-pipeline {{ grid-template-columns:1fr; }}
      .pipeline-arrow {{ transform:rotate(90deg); justify-self:center; }}
      .layout-picker-row {{ grid-template-columns:1fr; }}
      .layout-mapping-columns {{ grid-template-columns:1fr; }}
      .inventory-grid {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body><main>{body}</main>
<script>
  document.querySelectorAll('form[data-dirty-watch="true"]').forEach(function(form) {{
    const submit = form.querySelector('[data-dirty-submit="true"]');
    if (!submit) return;
    const snapshot = function() {{
      return Array.from(form.elements)
        .filter(function(element) {{ return element.name && !['action', 'case'].includes(element.name) && element.type !== 'submit'; }})
        .map(function(element) {{
          const value = ['checkbox', 'radio'].includes(element.type) ? String(element.checked) : element.value;
          return element.name + '=' + value;
        }}).join('&');
    }};
    const initial = snapshot();
    const forceDirty = form.dataset.forceDirty === 'true';
    const existing = form.dataset.existing === 'true';
    const update = function() {{
      const dirty = forceDirty || snapshot() !== initial;
      submit.disabled = !dirty;
      submit.textContent = dirty ? (existing ? 'Apply intake changes' : 'Save intake') : 'No intake changes';
    }};
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    form.addEventListener('submit', function(event) {{
      if (existing && !window.confirm(form.dataset.confirmMessage || 'Apply intake changes?')) {{
        event.preventDefault();
      }}
    }});
    update();
  }});
  document.querySelectorAll('form[data-confirm-submit]').forEach(function(form) {{
    form.addEventListener('submit', function(event) {{
      const message = form.dataset.confirmSubmit || 'Confirm this action?';
      if (!window.confirm(message)) {{
        event.preventDefault();
      }}
    }});
  }});
  document.querySelectorAll('[data-copy-target]').forEach(function(button) {{
    button.addEventListener('click', async function() {{
      const target = document.getElementById(button.dataset.copyTarget || '');
      if (!target) return;
      try {{
        await navigator.clipboard.writeText(target.value || target.textContent || '');
        const previous = button.textContent;
        button.textContent = 'Copied';
        window.setTimeout(function() {{
          button.textContent = previous;
        }}, 1200);
      }} catch (error) {{
        window.alert('Could not copy automatically. Please copy the prompt manually.');
      }}
    }});
  }});
  document.querySelectorAll('[data-bundle-selection]').forEach(function(form) {{
    const all = Array.from(form.querySelectorAll('input[type="checkbox"]'));
    const documentBoxes = Array.from(form.querySelectorAll('[data-exhibit]'));
    const exhibitBoxes = Array.from(form.querySelectorAll('[data-exhibit-toggle]'));
    const syncExhibit = function(exhibit) {{
      const parent = form.querySelector('[data-exhibit-toggle="' + CSS.escape(exhibit) + '"]');
      const children = documentBoxes.filter(function(box) {{ return box.dataset.exhibit === exhibit; }});
      if (!parent || !children.length) return;
      parent.checked = children.some(function(box) {{ return box.checked; }});
      parent.indeterminate = parent.checked && !children.every(function(box) {{ return box.checked; }});
    }};
    exhibitBoxes.forEach(function(parent) {{
      parent.addEventListener('change', function() {{
        documentBoxes.filter(function(box) {{ return box.dataset.exhibit === parent.dataset.exhibitToggle; }})
          .forEach(function(box) {{ box.checked = parent.checked; }});
        parent.indeterminate = false;
      }});
      syncExhibit(parent.dataset.exhibitToggle || '');
    }});
    documentBoxes.forEach(function(box) {{
      box.addEventListener('change', function() {{ syncExhibit(box.dataset.exhibit || ''); }});
    }});
    const setAll = function(checked) {{
      all.forEach(function(box) {{ box.checked = checked; box.indeterminate = false; }});
    }};
    form.querySelector('[data-select-all]')?.addEventListener('click', function() {{ setAll(true); }});
    form.querySelector('[data-clear-all]')?.addEventListener('click', function() {{ setAll(false); }});
  }});
</script>
</body>
</html>"""


def alert(message: str, kind: str) -> str:
    if not message:
        return ""
    return f'<div class="alert {kind}">{escape(message)}</div>'


def post_button(
    case_id: str, action: str, label: str, *, extra: str = "", disabled: bool = False
) -> str:
    return (
        '<form method="post">'
        f'<input type="hidden" name="case" value="{escape(case_id)}">'
        f'<input type="hidden" name="action" value="{escape(action)}">'
        f"{extra}<button{' disabled' if disabled else ''}>{escape(label)}</button></form>"
    )


def render_error(exc: BaseException) -> str:
    return page("Error", f"<section class='panel'><h1>Error</h1><pre>{escape(str(exc))}</pre><p><a href='/'>Back</a></p></section>")


def render_intake_panel(case_id: str, task_type: str) -> str:
    config = load_case(case_id).config
    beneficiary = config.get("beneficiary", {}) if isinstance(config.get("beneficiary"), dict) else {}
    rfe_metadata = config.get("rfe_metadata", {}) if isinstance(config.get("rfe_metadata"), dict) else {}
    configured_claimed = set(str(item) for item in config.get("claimed_criteria", []) or [])
    claimed = set(configured_claimed)
    source_imports = config.get("source_imports", {}) if isinstance(config.get("source_imports"), dict) else {}
    intake_sources = config.get("intake_sources", {}) if isinstance(config.get("intake_sources"), dict) else {}

    def field_value(value: object) -> str:
        text = "" if value is None else str(value)
        return "" if text.startswith("__") else escape(text, quote=True)

    gender = str(beneficiary.get("gender", ""))
    gender_options = "".join(
        f'<option value="{value}"{" selected" if gender == value else ""}>{label}</option>'
        for value, label in (("", "Gender / pronouns"), ("male", "Male — Mr./he"), ("female", "Female — Ms./she"), ("neutral", "Neutral — Mx./they"))
    )
    if task_type == "o1b_petition":
        criteria_labels = [
            ("lead_starring_productions", "(i) Lead/starring productions or events"),
            ("published_recognition", "(ii) Published recognition"),
            ("organization_role", "(iii) Lead/starring/critical organizational role"),
            ("commercial_critical_success", "(iv) Commercial or critically acclaimed success"),
            ("significant_recognition", "(v) Significant recognition"),
            ("high_salary", "(vi) High salary or substantial remuneration"),
            ("comparable_evidence", "Comparable evidence — Arts only"),
        ]
        criteria_legend = "Claimed O-1B criteria"
    else:
        criteria_labels = [
            ("awards", "(i) Awards"),
            ("memberships", "(ii) Memberships"),
            ("media", "(iii) Published material"),
            ("judging", "(iv) Judging"),
            ("original_contribution", "(v) Original contribution"),
            ("scholarly_articles", "(vi) Scholarly articles"),
            ("exhibitions", "(vii) Exhibitions"),
            ("leading_critical_role", "(viii) Leading / critical role"),
            ("high_salary", "(ix) High salary"),
            ("commercial_success", "(x) Commercial success"),
        ]
        criteria_legend = "Claimed EB1A criteria"
    if task_type in {"eb1a_petition", "o1b_petition"} and not claimed:
        roles = folder_role_map(config)
        originals = _case_dir(case_id) / "source_documents" / "originals"
        for role, _ in criteria_labels:
            folder = originals / str(roles.get(role, role))
            if folder.exists() and any(
                item.is_file() and item.name != ".gitkeep" for item in folder.rglob("*")
            ):
                claimed.add(role)
    criteria_html = "" if task_type not in {"eb1a_petition", "o1b_petition"} else (
        '<input type="hidden" name="claimed_criteria_present" value="1">'
        f'<fieldset><legend>{escape(criteria_legend)}</legend>'
        '<p class="muted small">Checked criteria are stored in the case configuration and control the working memorandum. When no selection was saved, they are inferred from non-empty evidence folders.</p>'
        '<div class="check-grid">'
        + "".join(
            f'<label><input type="checkbox" name="criterion_{role}"{" checked" if role in claimed else ""}> {escape(label)}</label>'
            for role, label in criteria_labels
        )
        + "</div></fieldset>"
    )
    eb1a_template_selector = ""
    if task_type == "eb1a_petition":
        current_variant = eb1a_template_variant(config)
        options = "".join(
            f'<option value="{escape(value)}"{" selected" if current_variant == value else ""}>{escape(meta["label"])}</option>'
            for value, meta in EB1A_TEMPLATE_VARIANTS.items()
        )
        eb1a_template_selector = f"""
        <label><strong>EB1A memorandum template</strong>
          <select name="eb1a_template_variant">{options}</select>
        </label>
        <p class="muted small">Controls Stage 2 drafting units and the working memo structure for this case.</p>
        """
    template_default = {
        "eb1a_rfe_response": "templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.yaml",
        "o1b_petition": "templates/O1B/MEMO O-1В_ver.1.0.docx",
    }.get(task_type, eb1a_machine_template_file(config))
    if task_type == "eb1a_rfe_response":
        source_target_options = [
            ("source_rfe_notice", "RFE notice"),
            ("source_rfe_issues", "RFE issue folders"),
            ("source_initial_filing_memo", "Initial filing memorandum"),
            ("source_initial_filing_issues", "Initial filing issue folders"),
            ("source_rfe_new_issue_documents", "New RFE issue documents"),
            ("source_rfe_new_evidence", "New RFE general evidence"),
        ]
        options = "".join(
            f'<option value="{escape(value)}">{escape(label)}</option>' for value, label in source_target_options
        )
        source_inputs_html = f"""
        <div class="source-row">
          <input name="source_folder_path" placeholder="Optional path to one RFE source folder">
          <select name="source_target_key">{options}</select>
        </div>
        """
    else:
        source_rows = []
        for key, input_name, label in (
            ("source_originals", "source_originals_path", "Original documents"),
            ("source_translations", "source_translations_path", "Translations"),
            ("source_other", "source_other_path", "Additional / other documents"),
        ):
            saved_import = str(source_imports.get(key, ""))
            paths = config.get("paths", {})
            case_relative = str(paths.get(key, "")) if isinstance(paths, dict) else ""
            open_import = (
                f'<a class="folder-link" href="/open-source-folder?case={quote(case_id)}&source_key={quote(key)}&location=import">Open imported source</a>'
                if saved_import
                else ""
            )
            source_rows.append(
                f'<div class="source-row"><label><strong>{escape(label)}</strong>'
                f'<input name="{escape(input_name)}" value="{escape(saved_import, quote=True)}" placeholder="Optional external folder to import"></label>'
                f'<div class="source-actions"><code>{escape(case_relative)}</code>'
                f'<a class="folder-link" href="/open-source-folder?case={quote(case_id)}&source_key={quote(key)}&location=case">Open case folder</a>'
                f'{open_import}</div></div>'
            )
        source_inputs_html = '<div class="source-folders">' + "".join(source_rows) + "</div>"

    if task_type == "eb1a_rfe_response":
        right_fields = f"""
        <input name="case_number" value="{field_value(rfe_metadata.get('case_number'))}" placeholder="RFE/case number">
        <input name="receipt_date" value="{field_value(rfe_metadata.get('receipt_date'))}" placeholder="Receipt / accepted date">
        <input name="rfe_date" value="{field_value(rfe_metadata.get('rfe_date'))}" placeholder="RFE date">
        <input name="response_deadline" value="{field_value(rfe_metadata.get('response_deadline'))}" placeholder="RFE response deadline">
        <input name="uscis_address" value="{field_value(rfe_metadata.get('uscis_address'))}" placeholder="USCIS address">
        """
        left_extra = ""
    elif task_type == "o1b_petition":
        petitioner = config.get("petitioner", {}) if isinstance(config.get("petitioner"), dict) else {}
        filing = config.get("filing", {}) if isinstance(config.get("filing"), dict) else {}
        us_work = config.get("us_work", {}) if isinstance(config.get("us_work"), dict) else {}
        track = str(config.get("o1b_track", "arts"))
        petitioner_type = str(petitioner.get("petitioner_type", "us_employer"))
        processing = str(filing.get("processing", "Regular Processing"))
        left_extra = f"""
        <input name="citizenship" value="{field_value(beneficiary.get('citizenship'))}" placeholder="Citizenship">
        <select name="o1b_track">
          <option value="arts"{" selected" if track == "arts" else ""}>O-1B Arts — distinction</option>
          <option value="mptv"{" selected" if track == "mptv" else ""}>O-1B MPTV — extraordinary achievement</option>
        </select>
        """
        right_fields = f"""
        <input name="petitioner_company_name" value="{field_value(petitioner.get('company_name'))}" placeholder="Petitioner / agent company name">
        <input name="petitioner_company_address" value="{field_value(petitioner.get('company_address'))}" placeholder="Petitioner company address">
        <select name="petitioner_type">
          <option value="us_employer"{" selected" if petitioner_type == "us_employer" else ""}>U.S. employer</option>
          <option value="us_agent"{" selected" if petitioner_type == "us_agent" else ""}>U.S. agent</option>
          <option value="us_agent_for_multiple_employers"{" selected" if petitioner_type == "us_agent_for_multiple_employers" else ""}>U.S. agent for multiple employers</option>
          <option value="us_agent_for_foreign_employer"{" selected" if petitioner_type == "us_agent_for_foreign_employer" else ""}>U.S. agent for foreign employer</option>
        </select>
        <input name="authorized_signatory" value="{field_value(petitioner.get('authorized_signatory'))}" placeholder="Authorized signatory and title">
        <select name="filing_processing">
          <option value="Regular Processing"{" selected" if processing == "Regular Processing" else ""}>Regular Processing</option>
          <option value="Premium Processing"{" selected" if processing == "Premium Processing" else ""}>Premium Processing</option>
        </select>
        <input name="validity_start" value="{field_value(filing.get('validity_start'))}" placeholder="Requested validity start">
        <input name="validity_end" value="{field_value(filing.get('validity_end'))}" placeholder="Requested validity end">
        <input name="filing_uscis_address" value="{field_value(filing.get('uscis_address'))}" placeholder="USCIS filing address">
        <input name="position_or_role" value="{field_value(us_work.get('position_or_role'))}" placeholder="U.S. position / role">
        <input name="compensation" value="{field_value(us_work.get('compensation'))}" placeholder="Compensation / salary">
        <input name="work_location" value="{field_value(us_work.get('work_location'))}" placeholder="Primary work location">
        <textarea name="duties_summary" rows="3" placeholder="Short duties summary">{field_value(us_work.get('duties_summary'))}</textarea>
        """
    else:
        procedural_value = field_value(config.get("procedural_context")) or "Initial EB-1A petition"
        drafting_value = field_value(config.get("drafting_objective")) or "Prepare EB-1A petition memorandum"
        right_fields = f"""
        <input name="procedural_context" value="{procedural_value}" placeholder="Procedural context, e.g. Initial EB-1A petition">
        <input name="drafting_objective" value="{drafting_value}" placeholder="Drafting objective, e.g. Prepare EB-1A petition memorandum">
        """
        left_extra = ""
    existing_intake = bool(field_value(beneficiary.get("full_name")))
    o1b_missing_intake = task_type == "o1b_petition" and any(
        not field_value(value)
        for value in (
            config.get("o1b_track"),
            (config.get("petitioner", {}) or {}).get("company_name") if isinstance(config.get("petitioner"), dict) else "",
            (config.get("us_work", {}) or {}).get("position_or_role") if isinstance(config.get("us_work"), dict) else "",
        )
    )
    inferred_unsaved = task_type in {"eb1a_petition", "o1b_petition"} and (
        (bool(claimed) and not bool(configured_claimed))
        or not field_value(config.get("procedural_context"))
        or not field_value(config.get("drafting_objective"))
        or o1b_missing_intake
    )
    submit_label = "Save inferred intake" if inferred_unsaved else "No intake changes"
    submit_disabled = "" if inferred_unsaved or not existing_intake else " disabled"
    force_dirty = "true" if inferred_unsaved or not existing_intake else "false"
    case_info_path = str(intake_sources.get("case_info_file", ""))
    return f"""
    <section class="panel">
      <h2>Case intake & working file</h2>
      <p class="muted small">
        This is the deterministic first step: apply basic case data, optionally copy a source folder,
        parse the machine template, and create <code>final_memo/working_memo.docx</code>.
      </p>
      <form method="post" class="stack" data-dirty-watch="true" data-existing="{'true' if existing_intake else 'false'}" data-force-dirty="{force_dirty}" data-confirm-message="This updates case_config.yaml and copies files from any non-empty source folders. Existing case documents and manual translation links are not deleted. Rebuild the working memorandum afterward if case data or criteria changed. Continue?">
        <input type="hidden" name="action" value="apply_intake">
        <input type="hidden" name="case" value="{escape(case_id)}">
        {eb1a_template_selector}
        <div class="columns">
          <div class="stack">
            <input name="beneficiary_full_name" value="{field_value(beneficiary.get('full_name'))}" placeholder="Beneficiary full name">
            <input name="preferred_reference" value="{field_value(beneficiary.get('preferred_reference'))}" placeholder="Preferred reference, e.g. Mr./Ms. Surname">
            {left_extra}
            <select name="gender">{gender_options}</select>
            <input name="field" value="{field_value(config.get('field'))}" placeholder="Area / field">
            <input name="specialization" value="{field_value(config.get('specialization'))}" placeholder="Specialization">
            <input name="soc_code" value="{field_value(config.get('soc_code'))}" placeholder="SOC code (optional)">
          </div>
          <div class="stack">
            {right_fields}
          </div>
        </div>
        {criteria_html}
        <label><strong>Optional YAML/TXT case information file</strong>
          <input name="case_info_file" value="{escape(case_info_path, quote=True)}" placeholder="Optional path to YAML/TXT case info file">
        </label>
        <h3>Document source folders</h3>
        <p class="muted small">External paths are remembered for later imports. The case-folder buttons open the copies actually used by the workflow.</p>
        {source_inputs_html}
        <button data-dirty-submit="true"{submit_disabled}>{submit_label}</button>
      </form>
      <form method="post" class="inline-form" data-confirm-submit="Refresh the remembered source folders and rebuild the document index? The working memorandum will not be changed.">
        <input type="hidden" name="action" value="refresh_intake_sources">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <button type="submit" class="secondary">Refresh sources + document index</button>
        <span class="muted small">Uses the saved folder paths even when the intake fields have not changed.</span>
      </form>
      <hr>
      <form method="post" class="stack">
        <input type="hidden" name="action" value="build_working_memo">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <input name="template_path" value="{escape(template_default)}" placeholder="Machine template path">
        <button>Parse template + build working DOCX</button>
      </form>
    </section>
    """


def render_rfe_panel(case_id: str) -> str:
    return _render_rfe_strategy_panel(case_id)


def _render_rfe_strategy_panel(case_id: str) -> str:
    loaded = load_case(case_id)
    imports = loaded.config.get("source_imports", {})
    if not isinstance(imports, dict):
        imports = {}
    manifest = load_strategy_manifest(loaded.case_dir)
    prompt = read_case_file_or_empty(case_id, "generated_prompts/rfe_strategy_bootstrap.latest.prompt.md")
    manifest_status = (
        f"Accepted: {len(manifest.get('units', []))} drafting unit(s)."
        if manifest
        else "Not accepted yet. Build the bootstrap prompt and paste the LLM JSON below."
    )

    def saved(key: str) -> str:
        return escape(str(imports.get(key, "")), quote=True)

    prompt_block = (
        f"""
        <div class="progress-heading"><div><strong>Generated bootstrap prompt</strong></div>
          <div class="button-row">
            <form method="post" data-confirm-submit="Refresh the strategy prompt from the saved strategy and RFE files?">
              <input type="hidden" name="action" value="build_rfe_strategy_prompt"><input type="hidden" name="case" value="{escape(case_id)}">
              <input type="hidden" name="strategy_path" value="{saved('rfe_strategy_file')}"><input type="hidden" name="rfe_path" value="{saved('rfe_notice_file')}">
              <button type="submit" class="secondary">Refresh prompt</button>
            </form>
            <button type="button" class="secondary" data-copy-target="rfe-bootstrap-prompt">Copy prompt</button>
          </div>
        </div>
        <textarea id="rfe-bootstrap-prompt" rows="18" readonly>{escape(prompt)}</textarea>
        """
        if prompt
        else '<p class="muted small">The prompt will appear here after both source files are imported.</p>'
    )
    evidence_disabled = "" if manifest else " disabled"
    return f"""
    <section class="panel">
      <h2>RFE Stage 1A - strategy bootstrap</h2>
      <p class="muted small">
        Select the human strategy and the full RFE notice. The script copies both into the case,
        extracts their text, combines them with the base RFE template and produces one prompt.
      </p>
      <form method="post" class="stack" data-dirty-watch="true">
        <input type="hidden" name="action" value="build_rfe_strategy_prompt">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <label>Human strategy file (.docx/.txt/.md)
          <input name="strategy_path" value="{saved('rfe_strategy_file')}" placeholder="C:\\path\\strategy.docx" required>
        </label>
        <label>Full RFE notice (.pdf/.docx/.txt)
          <input name="rfe_path" value="{saved('rfe_notice_file')}" placeholder="C:\\path\\RFE.pdf" required>
        </label>
        <button>Import sources + build strategy prompt</button>
      </form>
      {prompt_block}
    </section>

    <section class="panel">
      <h2>RFE Stage 1B - accept strategy output</h2>
      <p><strong>{escape(manifest_status)}</strong></p>
      <p class="muted small">
        Paste the JSON returned by the LLM. Validation creates
        <code>case_strategy/strategy_manifest.json</code>, per-unit strategy files,
        <code>rfe_response_plan.md</code>, and a substantially populated working Word response
        cloned from the company DOCX template.
      </p>
      <form method="post" class="stack">
        <input type="hidden" name="action" value="import_rfe_strategy_output">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <textarea name="strategy_output_json" rows="18" placeholder='{{"case_id": "{escape(case_id)}", ...}}' required></textarea>
        <button>Validate strategy + build working template</button>
      </form>
    </section>

    <section class="panel">
      <h2>RFE Stage 1C - import and scan the record</h2>
      <p class="muted small">
        This step unlocks after the strategy is accepted. The initial filing is represented only
        by its memorandum; its criterion sections and document lists are extracted automatically.
        New evidence may contain <code>originals</code>/<code>translations</code>; otherwise the
        selected folder is treated as originals. Criterion and episode subfolders are preserved.
      </p>
      <form method="post" class="stack">
        <input type="hidden" name="action" value="import_rfe_evidence">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <label>Initial filing memorandum
          <input name="initial_memo_path" value="{saved('initial_filing_memo')}" placeholder="C:\\path\\initial_filing_memo.docx" required{evidence_disabled}>
        </label>
        <label>New RFE documents folder
          <input name="new_documents_path" value="{saved('rfe_new_documents')}" placeholder="C:\\path\\new_docs" required{evidence_disabled}>
        </label>
        <button{evidence_disabled}>Import, scan, partition initial filing, link translations</button>
      </form>
      <form method="post" class="inline-form" data-confirm-submit="Refresh the saved initial-filing memorandum and RFE evidence folders? The working memorandum will not be changed.">
        <input type="hidden" name="action" value="refresh_intake_sources">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <button type="submit" class="secondary"{evidence_disabled}>Refresh imported record + document index</button>
        <span class="muted small">Reuses the saved paths and leaves the memorandum untouched.</span>
      </form>
      <div class="button-row">
        <a class="action-link" href="/translations?case={quote(case_id)}">Review translation links</a>
        <a class="action-link" href="/llm?case={quote(case_id)}">Continue to LLM drafting</a>
      </div>
    </section>
    """


def _legacy_render_rfe_panel(case_id: str) -> str:
    instructions = read_case_file(case_id, "user_case_instructions.md")
    plan = read_case_file(case_id, "rfe_response_plan.md")
    browser_notes = read_case_file_or_empty(
        case_id, "source_documents/rfe_response/strategy/browser_strategy_notes.md"
    )
    folders = [
        ("RFE notice", "source_documents/rfe/notice"),
        ("RFE issue text", "source_documents/rfe/issues/<episode_folder>"),
        ("Initial filing memo", "source_documents/initial_filing/memorandum"),
        ("Initial filing issue text", "source_documents/initial_filing/issues/<episode_folder>"),
        ("New RFE docs", "source_documents/rfe_response/new_documents/issues/<episode_folder>"),
        ("Strategy notes", "source_documents/rfe_response/strategy"),
    ]
    folder_rows = "".join(
        f"<tr><td>{escape(label)}</td><td><code>{escape(path)}</code></td></tr>"
        for label, path in folders
    )
    return f"""
    <section class="panel">
      <h2>RFE track</h2>
      <p class="muted small">
        Use this panel to control RFE strategy. The highest-priority custom instructions go into
        <code>user_case_instructions.md</code>; the response order and issue map go into
        <code>rfe_response_plan.md</code>.
      </p>
      <table>
        <tbody>{folder_rows}</tbody>
      </table>
      <form method="post" class="stack">
        <input type="hidden" name="action" value="save_rfe_notes">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <label>Highest-priority custom strategy / style instructions</label>
        <textarea name="user_case_instructions" rows="8">{escape(instructions)}</textarea>
        <label>RFE response plan: order, headings, issue IDs, episode folders</label>
        <textarea name="rfe_response_plan" rows="10">{escape(plan)}</textarea>
        <label>Additional browser strategy notes included as source evidence</label>
        <textarea name="browser_strategy_notes" rows="6">{escape(browser_notes)}</textarea>
        <button>Save RFE notes</button>
      </form>
      <hr>
      <h3>Build one RFE issue prompt</h3>
      <form method="post" class="stack">
        <input type="hidden" name="action" value="build_prompt">
        <input type="hidden" name="case" value="{escape(case_id)}">
        <input type="hidden" name="step" value="rfe_issue_response">
        <input name="episode_id" placeholder="issue_id, e.g. continued_work or awards_1" required>
        <input name="episode_folder" placeholder='folder under issue folders, e.g. continued_work or "1. Награды/1 episode"'>
        <button>Build RFE issue prompt</button>
      </form>
    </section>
    """


def list_cases() -> list[str]:
    if not CASE_ROOT.exists():
        return []
    return sorted(path.name for path in CASE_ROOT.iterdir() if path.is_dir() and path.name != "_template")


def latest_prompts(case_id: str) -> list[Path]:
    prompt_dir = _case_dir(case_id) / "generated_prompts"
    if not prompt_dir.exists():
        return []
    return sorted(prompt_dir.glob("*.latest.prompt.md"), key=lambda path: path.stat().st_mtime, reverse=True)


def read_case_file(case_id: str, rel_path: str) -> str:
    validate_case_id(case_id)
    rel = Path(unquote(rel_path))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Invalid relative path.")
    path = _case_dir(case_id) / rel
    resolved = path.resolve()
    case_dir = _case_dir(case_id).resolve()
    if case_dir not in resolved.parents and resolved != case_dir:
        raise ValueError("Path escapes case directory.")
    if not path.exists():
        return f"[Missing file: {rel_path}]"
    return path.read_text(encoding="utf-8-sig", errors="replace")


def read_case_file_or_empty(case_id: str, rel_path: str) -> str:
    text = read_case_file(case_id, rel_path)
    return "" if text.startswith("[Missing file:") else text


def save_case_file(case_id: str, rel_path: str, text: str) -> Path:
    validate_case_id(case_id)
    rel = Path(unquote(rel_path))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Invalid relative path.")
    path = _case_dir(case_id) / rel
    resolved = path.resolve()
    case_dir = _case_dir(case_id).resolve()
    if case_dir not in resolved.parents and resolved != case_dir:
        raise ValueError("Path escapes case directory.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _read_case_index(case_id: str) -> list[dict[str, str]]:
    loaded = load_case(case_id)
    paths = loaded.config.get("paths", {})
    value = paths.get("document_index", "indexes/document_index.csv") if isinstance(paths, dict) else "indexes/document_index.csv"
    return _read_csv_file(loaded.case_dir / str(value))


def _read_csv_file(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: value or "" for key, value in row.items() if key} for row in csv.DictReader(handle)]


def _row_search_text(row: dict[str, str]) -> str:
    return " ".join(
        [
            row.get("document_id", ""),
            row.get("original_file_name", ""),
            row.get("display_title", ""),
            row.get("file_path", ""),
            row.get("category", ""),
        ]
    ).replace("\\", "/").casefold()


def _case_search_query(value: str, case_dir: Path) -> str:
    cleaned = value.strip()
    quote_pairs = {('"', '"'), ("'", "'"), ("“", "”"), ("«", "»")}
    while len(cleaned) >= 2 and (cleaned[0], cleaned[-1]) in quote_pairs:
        cleaned = cleaned[1:-1].strip()
    try:
        path = Path(cleaned)
        if path.is_absolute():
            resolved = path.resolve()
            case_resolved = case_dir.resolve()
            if resolved == case_resolved or case_resolved in resolved.parents:
                cleaned = resolved.relative_to(case_resolved).as_posix()
    except OSError:
        pass
    return cleaned.replace("\\", "/").casefold()


def _open_case_file_in_explorer(case_id: str, file_path: str) -> Path:
    validate_case_id(case_id)
    case_dir = _case_dir(case_id).resolve()
    rel = Path(unquote(file_path))
    target = rel.resolve() if rel.is_absolute() else (case_dir / rel).resolve()
    if target != case_dir and case_dir not in target.parents:
        raise ValueError("File path escapes the case workspace.")
    if not target.exists():
        raise ValueError(f"Case file not found: {file_path}")
    subprocess.Popen(["explorer.exe", "/select,", str(target)])  # noqa: S603 - explicit local user action.
    return target


def _open_source_folder(case_id: str, source_key: str, location: str) -> Path:
    validate_case_id(case_id)
    allowed_keys = {"source_originals", "source_translations", "source_other"}
    if source_key not in allowed_keys:
        raise ValueError(f"Unsupported source folder: {source_key}")
    loaded = load_case(case_id)
    if location == "import":
        source_imports = loaded.config.get("source_imports", {})
        raw_path = source_imports.get(source_key, "") if isinstance(source_imports, dict) else ""
        if not str(raw_path).strip():
            raise ValueError("No external import folder has been saved for this source.")
        target = Path(str(raw_path)).resolve()
    elif location == "case":
        paths = loaded.config.get("paths", {})
        raw_path = paths.get(source_key, "") if isinstance(paths, dict) else ""
        if not str(raw_path).strip():
            raise ValueError(f"case_config.yaml has no paths.{source_key}")
        target = (loaded.case_dir / str(raw_path)).resolve()
    else:
        raise ValueError(f"Unsupported source location: {location}")
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Source folder not found: {target}")
    subprocess.Popen(["explorer.exe", str(target)])  # noqa: S603 - explicit local user action.
    return target


def _safe_progress(case_id: str) -> CaseProgress:
    try:
        return build_case_progress(case_id)
    except Exception:  # noqa: BLE001 - one damaged case must not break the case library.
        return CaseProgress(
            case_id=case_id,
            beneficiary_name=case_id,
            task_type="unknown",
            stage_label="Needs attention",
            completion_percent=0,
            steps=[],
            indexed_documents=0,
            linked_translations=0,
            total_translations=0,
        )


def _safe_llm_stage(case_id: str) -> LLMStage:
    try:
        return build_llm_stage(case_id)
    except Exception:  # noqa: BLE001 - damaged drafting state should remain inspectable in UI.
        return LLMStage(
            case_id=case_id,
            units=(),
            completed_units=0,
            total_units=0,
            percent=0,
            complete=False,
            current_action_type="blocked",
            current_step_id="",
            current_episode_id="",
            current_episode_folder="",
            current_reason="Could not calculate the LLM drafting stage.",
        )


def _stage_percent(progress: CaseProgress, keys: set[str]) -> int:
    selected = [step for step in progress.steps if step.key in keys]
    if not selected:
        return 0
    return round((sum(step.complete for step in selected) / len(selected)) * 100)


def _action_route(action: str) -> str:
    if action in {
        "apply_intake",
        "build_working_memo",
        "parse_template",
        "scan_documents",
        "link_translations",
        "save_rfe_notes",
        "build_rfe_strategy_prompt",
        "import_rfe_strategy_output",
        "import_rfe_evidence",
        "refresh_intake_sources",
    }:
        return "/intake"
    if action in {"run_next", "build_prompt", "import_output", "insert_section", "refresh_unit_documents"}:
        return "/llm"
    if action in {
        "refresh_layout_indexes",
        "build_index",
        "separators",
        "separator_pdfs",
        "bundle_dry_run",
        "prepare_selected_bundle",
        "bundle_build",
    }:
        return "/layout"
    if action in {
        "layout_pick_originals_dir",
        "layout_pick_translations_dir",
        "layout_pick_list_document",
        "layout_parse_sources",
        "layout_save_structure",
        "layout_save_folder_scopes",
        "layout_save_document_originals",
        "layout_add_mapping",
        "layout_remove_mapping",
        "layout_preview",
        "layout_build",
    }:
        return "/document-layout"
    return "/case"


def _safe_case_task_type(case_id: str) -> str:
    try:
        return str(load_case(case_id).config.get("task_type", ""))
    except Exception as exc:  # noqa: BLE001
        return f"[unknown: {exc}]"


def _safe_layout_setting(case_id: str, key: str) -> str:
    try:
        return str(load_layout_status(case_id).settings.get(key, ""))
    except Exception:
        return ""


def _pick_directory(initial: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Directory picker is not available in this environment.") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(initialdir=initial or None)
    root.destroy()
    return str(selected or "")


def _pick_file(initial: str = "") -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # noqa: BLE001
        raise ValueError("File picker is not available in this environment.") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    initial_dir = initial if Path(initial).is_dir() else str(Path(initial).parent) if initial else None
    selected = filedialog.askopenfilename(initialdir=initial_dir)
    root.destroy()
    return str(selected or "")


def _case_dir(case_id: str) -> Path:
    validate_case_id(case_id)
    return CASE_ROOT / case_id


def _single(params: dict[str, list[str]], key: str) -> str:
    values = params.get(key, [""])
    return values[-1] if values else ""


def _safe_text(callback: object) -> str:
    try:
        return callback()  # type: ignore[operator]
    except Exception as exc:  # noqa: BLE001
        return f"[Error]\n{exc}"


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return "Done."


if __name__ == "__main__":
    raise SystemExit(main())
