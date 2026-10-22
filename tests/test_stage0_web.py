import http.client
import json
import re
import socket
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode

from app import web, memo_builder
from app.web_security import DEFAULT_MAX_POST_BYTES
from stage0_support import SyntheticCase


class LocalHTTPTests(SyntheticCase):
    def setUp(self):
        super().setUp()
        class QuietHandler(web.PetitionsHandler):
            def log_message(self, *args):
                pass
        class TestServer(ThreadingHTTPServer):
            # Wait for active requests before deleting their temporary cases.
            daemon_threads = False
        self.server = TestServer(("127.0.0.1", 0), QuietHandler)
        self.port = self.server.server_port
        self.origin = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        def close():
            self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)
        self.addCleanup(close)

    def request(self, method="GET", path="/", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8", errors="replace")
        finally:
            connection.close()

    def token(self):
        status, headers, html = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def form(self, **data):
        return self.request("POST", body=urlencode(data), headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin})

    def test_local_browser_form_creates_case_and_switches_pages(self):
        status, headers, html = self.form(csrf_token=self.token(), action="init_case", new_case="from_web", task_type="eb1a_petition")
        self.assertEqual(status, 303)
        self.assertTrue((self.case_root / "from_web/case_config.yaml").exists())
        self.assertIn("from_web", headers["Location"])
        for route in ("/case", "/intake", "/llm", "/layout", "/translations"):
            with self.subTest(route=route):
                self.assertEqual(self.request(path=route + "?case=from_web")[0], 200)
        status, _, html = self.form(csrf_token=self.token(), action="init_case", new_case="second_web", task_type="o1b_petition")
        self.assertEqual(status, 303)
        self.assertIn("second_web", self.request()[2])

    def test_http_intake_scan_prompt_json_import_and_section_insertion(self):
        self.create()
        memo_builder.apply_case_intake(self.case_id, {}, claimed_criteria=["awards"])
        self.source()
        token = self.token()
        for action, values in (
            ("scan_documents", {}),
            ("build_prompt", {"step": "criterion_awards_episode", "episode_id": "1", "episode_folder": "1. Award"}),
        ):
            status, _, html = self.form(csrf_token=token, action=action, case=self.case_id, **values)
            self.assertEqual(status, 303, html)
        data = self.payload()
        status, _, html = self.form(csrf_token=token, action="import_output", case=self.case_id, step="criterion_awards_episode", episode_id="1", output_json=json.dumps(data), insert_after_import="on")
        self.assertEqual(status, 303, html)
        self.assertTrue((self.case_dir / "draft_sections/criteria/awards/1.md").exists())
        self.assertTrue((self.case_dir / "final_memo/working_memo.docx").exists())
        status, _, html = self.form(csrf_token=token, action="import_output", case=self.case_id, step="criterion_awards_episode", episode_id="1", output_json=json.dumps(data))
        self.assertEqual(status, 400)
        self.assertIn("already has saved results", html)
        self.assertIn("Synthetic award document", html)

    def test_cross_site_host_origin_fetch_metadata_and_missing_token_are_rejected(self):
        token = self.token()
        body = urlencode({"action": "init_case", "new_case": "must_not_exist", "csrf_token": token})
        with patch.object(web, "handle_action") as action:
            for headers in ({"Host": f"attacker.invalid:{self.port}"},
                            {"Origin": "https://attacker.invalid"},
                            {"Origin": "null"},
                            {"Referer": "http://127.0.0.1:9999/"},
                            {"Sec-Fetch-Site": "cross-site"}):
                with self.subTest(headers=headers):
                    request_headers = {"Content-Type": "application/x-www-form-urlencoded", **headers}
                    self.assertEqual(self.request("POST", body=body, headers=request_headers)[0], 403)
            self.assertEqual(self.form(action="init_case", new_case="must_not_exist")[0], 403)
            action.assert_not_called()
        self.assertFalse((self.case_root / "must_not_exist").exists())

    def test_post_length_encoding_and_content_type_limits(self):
        self.server.max_post_bytes = 256
        for length in ("-1", "not-a-number", "1,2", "1" * 5000):
            with self.subTest(length=length[:20]):
                status, _, _ = self.request("POST", body=b"", headers={"Content-Length": length, "Content-Type": "application/x-www-form-urlencoded"})
                self.assertEqual(status, 400)
        self.assertEqual(self.request("POST", body=b"", headers={"Content-Length": "257", "Content-Type": "application/x-www-form-urlencoded"})[0], 413)
        self.assertEqual(self.request("POST", body="{}", headers={"Content-Type": "application/json"})[0], 415)
        self.assertEqual(self.request("POST", body=b"\xff", headers={"Content-Type": "application/x-www-form-urlencoded"})[0], 400)
        self.assertEqual(self.request("POST", body="", headers={"Transfer-Encoding": "chunked", "Content-Type": "application/x-www-form-urlencoded"})[0], 400)

    def test_duplicate_or_absent_length_is_rejected(self):
        for duplicate in (False, True):
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            connection.putrequest("POST", "/")
            if duplicate:
                connection.putheader("Content-Length", "0")
                connection.putheader("Content-Length", "0")
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read(); connection.close()

    def test_default_limit_allows_large_json_and_errors_preserve_submitted_values(self):
        self.assertEqual(web.build_parser().parse_args([]).max_post_bytes, DEFAULT_MAX_POST_BYTES)
        value = "Synthetic pasted JSON " + "A" * (1024 * 1024)
        with patch.object(web, "handle_action", side_effect=ValueError("Synthetic validation error")):
            status, headers, html = self.form(csrf_token=self.token(), action="import_output", case="synthetic", json_output=value)
        self.assertEqual(status, 400)
        self.assertNotIn("Location", headers)
        self.assertIn(value, html)
        self.assertIn("Synthetic validation error", html)
        self.assertIn('name="csrf_token"', html)

    def test_internal_errors_are_sanitized_and_folder_open_get_is_read_only(self):
        with patch.object(web, "render_home", side_effect=OSError("C:\\private\\client\\secret.txt")):
            status, _, html = self.request()
            self.assertEqual(status, 500)
            self.assertNotIn("secret.txt", html)
        with patch.object(web, "_open_source_folder") as opener:
            self.assertEqual(self.request(path="/open-source-folder?case=synthetic&source_key=source_originals")[0], 200)
            opener.assert_not_called()

    def test_main_rejects_non_loopback_binding_before_server_creation(self):
        with patch.object(web, "ThreadingHTTPServer") as server:
            for host in ("0.0.0.0", "192.168.1.1", "::", "example.com"):
                with self.subTest(host=host), self.assertRaisesRegex(SystemExit, "loopback"):
                    web.main(["--host", host])
            server.assert_not_called()
