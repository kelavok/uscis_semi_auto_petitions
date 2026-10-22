import csv
import json
import os
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import cli_support, evidence, memo_builder, web, workflow
from app.case_lock import locked_case
from app.safe_io import atomic_open, atomic_write_text, contained_path, relative_path, staged_directory
from stage0_support import SyntheticCase


class StorageRegressionTests(SyntheticCase):
    def test_atomic_failure_keeps_previous_file_and_cleans_temporary(self):
        target = self.root / "result.json"
        target.write_text("previous", encoding="utf-8")
        with self.assertRaises(OSError):
            with atomic_open(target, encoding="utf-8") as handle:
                handle.write("partial")
                raise OSError("Synthetic disk failure")
        self.assertEqual(target.read_text(), "previous")
        self.assertEqual(list(self.root.iterdir()), [target])
        with patch("app.safe_io.os.replace", side_effect=PermissionError("Synthetic locked file")):
            with self.assertRaises(PermissionError):
                atomic_write_text(target, "replacement")
        self.assertEqual(target.read_text(), "previous")

    def test_staged_generation_failure_preserves_directory(self):
        output = self.root / "separators"
        output.mkdir()
        (output / "old.pdf").write_bytes(b"previous")
        with self.assertRaises(ValueError):
            with staged_directory(output) as temporary:
                (temporary / "new.pdf").write_bytes(b"partial")
                raise ValueError("Synthetic generator failure")
        self.assertEqual((output / "old.pdf").read_bytes(), b"previous")
        self.assertEqual(list(self.root.iterdir()), [output])
        rename = Path.rename
        def fail_publication_and_restore(path, destination):
            if path.name.startswith(".separators."):
                raise OSError("Synthetic publish/restore failure")
            return rename(path, destination)
        with patch.object(Path, "rename", fail_publication_and_restore):
            with self.assertRaises(OSError):
                with staged_directory(output) as temporary:
                    (temporary / "new.pdf").write_bytes(b"completed")
        backups = list(self.root.glob(".separators.*.previous"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "old.pdf").read_bytes(), b"previous")

    def test_relative_paths_reject_traversal_drives_streams_and_invalid_types(self):
        for value in ("../outside", "..\\outside", "/outside", "C:outside", "C:\\outside", "\\\\host\\share", "folder:stream", "CON", "name. ", {"path": "x"}, ["x"], True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                relative_path(value)
        self.assertEqual(relative_path("документы/award.txt"), Path("документы/award.txt"))

    def test_symlink_and_config_outputs_cannot_escape_workspace(self):
        self.create()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.case_dir / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            # Windows junctions work without Developer Mode or symlink privileges.
            if os.name != "nt":
                raise
            subprocess.run(["cmd", "/c", "mklink", "/J", str(self.case_dir / "linked"), str(outside)], check=True, capture_output=True)
        for operation in (lambda: contained_path(self.case_dir, "linked/file.txt"),
                          lambda: web.save_case_file(self.case_id, "linked/file.txt", "synthetic"),
                          lambda: workflow.render_evidence_files(workflow.load_case(self.case_id), [self.case_dir / "linked/file.txt"], {}),
                          lambda: workflow.build_prompt(self.case_id, "criterion_awards_episode", [], episode_id="1", episode_folder="../../outside")):
            with self.assertRaises(ValueError):
                operation()
        config = workflow.load_case(self.case_id).config
        config["paths"]["final_memo"] = "../outside"
        memo_builder._write_yaml_file(self.case_dir / "case_config.yaml", config)
        with self.assertRaises(ValueError):
            memo_builder.build_working_memo(self.case_id)
        self.assertEqual(list(outside.iterdir()), [])

    def test_external_import_is_allowed_and_nested_import_is_rejected(self):
        self.create()
        external = self.root / "внешние документы"
        external.mkdir()
        (external / "sample.txt").write_text("Synthetic import", encoding="utf-8")
        memo_builder.apply_case_intake(self.case_id, {}, source_folder_path=str(external))
        self.assertEqual((self.case_dir / "source_documents/originals/sample.txt").read_text(), "Synthetic import")
        with self.assertRaises(ValueError):
            memo_builder._copy_source_folder(external, external / "child", mirror=True)

    def test_failed_source_refresh_does_not_prune_previous_files(self):
        source, target = self.root / "source", self.root / "target"
        source.mkdir(); target.mkdir()
        (source / "new.txt").write_text("new", encoding="utf-8")
        (target / "previous.txt").write_text("previous", encoding="utf-8")
        with patch.object(memo_builder, "atomic_copy", side_effect=OSError("Synthetic copy failure")):
            with self.assertRaises(OSError):
                memo_builder._copy_source_folder(source, target, refresh_existing=True, mirror=True)
        self.assertTrue((target / "previous.txt").exists())

    def test_yaml_syntax_errors_are_not_silently_accepted_and_roundtrip_preserves_values(self):
        target = self.root / "config.yaml"
        for malformed in ("paths: [unclosed", "paths:\n  key: one\n bad indentation: two", "paths: !unknown x\ninvalid: ["):
            target.write_text(malformed, encoding="utf-8")
            with self.assertRaises(ValueError):
                workflow.load_yaml_file(target)
        data = {"label": "Награда: #1 !important", "enabled": False, "count": 0, "nested": ["on", "null", {"path": "C:\\local\\folder"}]}
        memo_builder._write_yaml_file(target, data)
        self.assertEqual(workflow.load_yaml_file(target), data)

    def test_eb1a_creation_populates_all_configured_roles_and_missing_template_fails_early(self):
        self.create()
        loaded = workflow.load_case(self.case_id)
        for folder in loaded.config["eb1a_folder_roles"].values():
            self.assertTrue((self.case_dir / "source_documents/originals" / folder).is_dir(), folder)
        with patch.object(cli_support, "PROJECT_ROOT", self.root):
            with self.assertRaisesRegex(SystemExit, "required source folder template"):
                cli_support.create_case_from_template("missing_template", "eb1a_petition")
        self.assertFalse((self.case_root / "missing_template").exists())

    def test_cli_uses_explicit_workspace_from_an_unrelated_working_directory(self):
        env = dict(os.environ, PETITIONS_CASE_ROOT=str(self.case_root))
        command = [sys.executable, "-m", "app.draft", "init-case", "--case", "outside_cwd", "--task-type", "eb1a_petition"]
        result = subprocess.run(command, env=env, cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.case_root / "outside_cwd/case_config.yaml").exists())
        result = subprocess.run([sys.executable, "-m", "app.web", "--help"], env=env, cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--max-post-bytes", result.stdout)

    def test_rejected_reimport_has_no_document_title_side_effect(self):
        self.create(); self.source(); evidence.scan_documents(self.case_id)
        data = self.payload()
        self.import_payload(data)
        before_index = (self.case_dir / "indexes/document_index.csv").read_bytes()
        before_json = (self.case_dir / "validated_outputs/criterion_awards_episode.1.json").read_bytes()
        data["used_documents"][0]["document_title"] = "Changed title from rejected import"
        with self.assertRaisesRegex(SystemExit, "already exists"):
            self.import_payload(data)
        self.assertEqual((self.case_dir / "indexes/document_index.csv").read_bytes(), before_index)
        self.assertEqual((self.case_dir / "validated_outputs/criterion_awards_episode.1.json").read_bytes(), before_json)
        self.import_payload(data, force=True)
        self.assertEqual(self.rows()[0]["display_title"], "Changed title from rejected import")

    def test_invalid_json_metadata_and_document_ids_never_replace_validated_result(self):
        self.create(); self.source(); evidence.scan_documents(self.case_id)
        self.import_payload()
        saved = self.case_dir / "validated_outputs/criterion_awards_episode.1.json"
        previous = saved.read_bytes()
        for field, value in (("case_id", "other"), ("task_type", "o1b_petition"), ("step_id", "other"), ("episode_id", "other"), ("draft_text", ""), ("used_documents", [{"document_id": "DOC9999", "document_title": "Unknown", "used_for": "Synthetic"}])):
            data = self.payload(); data[field] = value
            source = self.case_dir / "llm_outputs/invalid.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(field=field), self.assertRaises(SystemExit):
                workflow.import_llm_output(self.case_id, "criterion_awards_episode", str(source), episode_id="1", force=True)
            self.assertEqual(saved.read_bytes(), previous)
        (self.case_dir / "llm_outputs/invalid.json").write_text("{invalid", encoding="utf-8")
        with self.assertRaises(SystemExit):
            workflow.import_llm_output(self.case_id, "criterion_awards_episode", "llm_outputs/invalid.json", episode_id="1", force=True)
        self.assertEqual(saved.read_bytes(), previous)

    def test_docx_writer_failure_keeps_previous_memo(self):
        self.create(); self.source(); evidence.scan_documents(self.case_id)
        summary = memo_builder.build_working_memo(self.case_id)
        previous = summary.docx_path.read_bytes()
        previous_md = summary.markdown_path.read_bytes()
        with patch("app.memo_builder.zipfile.ZipFile.writestr", side_effect=OSError("Synthetic ZIP failure")):
            with self.assertRaises(OSError):
                memo_builder.build_working_memo(self.case_id)
        self.assertEqual(summary.docx_path.read_bytes(), previous)
        self.assertEqual(summary.markdown_path.read_bytes(), previous_md)
        with zipfile.ZipFile(summary.docx_path) as archive:
            self.assertIsNone(archive.testzip())

    def test_insert_section_reports_partial_success_and_respects_overwrite(self):
        self.create(); self.source(); evidence.scan_documents(self.case_id); self.import_payload()
        memo = memo_builder.build_working_memo(self.case_id).docx_path
        previous = memo.read_bytes()
        with patch.object(memo_builder, "build_working_memo", side_effect=SystemExit("Synthetic template unavailable")):
            with self.assertWarnsRegex(UserWarning, "may be outdated"):
                target = workflow.insert_section(self.case_id, "criterion_awards_episode", episode_id="1")
        self.assertTrue(target.exists())
        self.assertEqual(memo.read_bytes(), previous)
        self.assertIn("incomplete", (self.case_dir / "reports/draft_sync_status.md").read_text())
        with self.assertRaisesRegex(SystemExit, "already exists"):
            workflow.insert_section(self.case_id, "criterion_awards_episode", episode_id="1")
        workflow.insert_section(self.case_id, "criterion_awards_episode", episode_id="1", force=True)
        self.assertIn("synchronization complete", (self.case_dir / "reports/draft_sync_status.md").read_text())

    def test_case_locks_serialize_threads_and_cli_processes(self):
        self.create()
        acquired = threading.Event()
        with ThreadPoolExecutor(1) as pool:
            with locked_case(self.case_id):
                def attempt():
                    with locked_case(self.case_id):
                        acquired.set()
                future = pool.submit(attempt)
                self.assertFalse(acquired.wait(0.05))
            future.result(timeout=5)
        self.assertTrue(acquired.is_set())
        ready, finished = self.root / "ready", self.root / "finished"
        code = ("from pathlib import Path\nfrom app.case_lock import locked_case\n"
                f"Path({str(ready)!r}).touch()\n"
                f"with locked_case({self.case_id!r}):\n    Path({str(finished)!r}).touch()\n")
        env = dict(os.environ, PETITIONS_CASE_ROOT=str(self.case_root))
        with locked_case(self.case_id):
            process = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.addCleanup(lambda: process.kill() if process.poll() is None else None)
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            self.assertFalse(finished.exists())
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr.decode())
        self.assertTrue(finished.exists())
