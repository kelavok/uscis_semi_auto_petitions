"""Local-only HTTP boundary; this is not a public-service authentication system."""
from __future__ import annotations

import hmac
import ipaddress
import re
import secrets
import threading
from functools import wraps
from urllib.parse import urlsplit

DEFAULT_MAX_POST_BYTES = 16 * 1024 * 1024
_TOKEN = secrets.token_urlsafe(32)
_requests = threading.RLock()


def loopback_host(value: str) -> str:
    if value.casefold() == "localhost":
        return "127.0.0.1"
    try:
        if ipaddress.ip_address(value).is_loopback:
            return value
    except ValueError:
        pass
    raise ValueError("The web UI supports loopback hosts only; public deployment is unsupported.")


def local_request(function):
    @wraps(function)
    def run(self):
        with _requests:
            self.connection.settimeout(15)
            try:
                if not self._local_headers():
                    return
            except ValueError:
                self.send_error(400, "Invalid request origin")
                return
            return function(self)
    return run


class LocalRequestMixin:
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def _local_headers(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or not self._allowed_authority(hosts[0]):
            self.send_error(403, "Invalid local Host header")
            return False
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            self.send_error(403, "Cross-site requests are not allowed")
            return False
        for name in ("Origin", "Referer"):
            if name in self.headers:
                value = urlsplit(self.headers[name])
                if value.scheme != "http" or value.netloc.lower() != hosts[0].lower():
                    self.send_error(403, "Request origin does not match this local UI")
                    return False
        return True

    def _allowed_authority(self, authority: str) -> bool:
        try:
            parsed = urlsplit("http://" + authority)
            host = parsed.hostname or ""
            loopback_host(host)
            return (parsed.port or 80) == self.server.server_port and not parsed.username and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment
        except ValueError:
            return False

    def _post_body(self) -> str | None:
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0]):
            self.send_error(400, "A single valid Content-Length is required")
            return None
        length = int(lengths[0])
        maximum = getattr(self.server, "max_post_bytes", DEFAULT_MAX_POST_BYTES)
        if length > maximum:
            self.send_error(413, f"Request exceeds the configured {maximum} byte limit")
            return None
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(415, "Expected form-urlencoded data")
            return None
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body")
            return body.decode("utf-8")
        except (ValueError, OSError):
            self.send_error(400, "Incomplete or invalid UTF-8 request body")
            return None

    def _valid_token(self, data: dict[str, str]) -> bool:
        if not hmac.compare_digest(data.get("csrf_token", "").encode("utf-8"), _TOKEN.encode("ascii")):
            self.send_error(403, "Reload this page and submit the form again")
            return False
        return True

    def _csrf_forms(self, html: str) -> str:
        return re.sub(
            r'(<form\b[^>]*\bmethod=["\']post["\'][^>]*>)',
            lambda match: match.group(0) + f'<input type="hidden" name="csrf_token" value="{_TOKEN}">',
            html, flags=re.IGNORECASE,
        )
