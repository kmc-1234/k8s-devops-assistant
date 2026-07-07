from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .notifier import maybe_send_alert
from .runner import run_diagnosis

STATIC_ROOT = Path(__file__).resolve().parent.parent / "dashboard"


class AssistantHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/dashboard"}:
            self._static_file("index.html")
            return

        if parsed.path.startswith("/static/"):
            self._static_file(parsed.path.removeprefix("/static/"))
            return

        if parsed.path == "/healthz":
            self._json(200, {"status": "ok"})
            return

        if parsed.path not in {"/diagnose", "/alerts"}:
            self._json(404, {"error": "not found"})
            return

        query = parse_qs(parsed.query)
        namespace = _one(query, "namespace", "default")
        pod = _one(query, "pod")
        deployment = _one(query, "deployment")
        use_ai = _one(query, "ai", "false").lower() == "true"
        notify = parsed.path == "/alerts" or _one(query, "notify", "false").lower() == "true"

        try:
            diagnosis = run_diagnosis(
                namespace=namespace,
                pod=pod,
                deployment=deployment,
                include_ai=use_ai,
            )
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return

        payload = diagnosis.as_dict()
        if notify:
            try:
                payload["notification"] = maybe_send_alert(diagnosis)
            except Exception as exc:
                payload["notification"] = {"enabled": True, "sent": False, "error": str(exc)}

        self._json(200, payload)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static_file(self, relative_path: str) -> None:
        target = (STATIC_ROOT / relative_path).resolve()
        if STATIC_ROOT not in target.parents and target != STATIC_ROOT:
            self._json(403, {"error": "forbidden"})
            return
        if not target.is_file():
            self._json(404, {"error": "not found"})
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), AssistantHandler)
    print(f"Serving Kubernetes assistant on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        server.server_close()


def _one(query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = query.get(key)
    if not values:
        return default
    return values[0]
