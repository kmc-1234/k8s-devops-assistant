from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .runner import run_diagnosis


class AssistantHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json(200, {"status": "ok"})
            return

        if parsed.path != "/diagnose":
            self._json(404, {"error": "not found"})
            return

        query = parse_qs(parsed.query)
        namespace = _one(query, "namespace", "default")
        pod = _one(query, "pod")
        deployment = _one(query, "deployment")
        use_ai = _one(query, "ai", "false").lower() == "true"

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

        self._json(200, diagnosis.as_dict())

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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
