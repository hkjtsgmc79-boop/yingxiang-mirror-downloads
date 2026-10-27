#!/usr/bin/env python3
"""Loopback HTTP integration service; fixed fixture output, no model requests."""
import argparse
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urljoin

MODE = "fixture_replay"
MAX_BODY = 4096
MAX_TASKS = 128
IDS = {"opera-qingyi", "opera-wusheng", "opera-hualian"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def load_catalog(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("templates", []) if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        raise ValueError("catalog.json must provide a nonempty templates array")
    rows = [{**r, "template_id": r.get("template_id", r.get("id"))} for r in rows]
    for row in rows:
        if row.get("preview_url"):
            row["preview_url"] = urljoin("https://hkjtsgmc79-boop.github.io/yingxiang-mirror-downloads/developers/", row["preview_url"])
    if {r.get("template_id") for r in rows} != IDS:
        raise ValueError("catalog.json template IDs must match the three documented templates")
    return rows


def load_tokens():
    raw = os.environ.get("MIRROR_API_TOKENS_JSON", "")
    if raw:
        mapping = json.loads(raw)
    else:
        token = os.environ.get("MIRROR_API_TOKEN", "")
        mapping = {"local-demo-client": token}
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Supply MIRROR_API_TOKEN or MIRROR_API_TOKENS_JSON in the environment")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", k) or not isinstance(v, str) or len(v) < 24 for k, v in mapping.items()):
        raise ValueError("Client IDs must be simple identifiers and each runtime token must be at least 24 characters")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Each client needs a distinct runtime token")
    return mapping


class IntegrationServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, catalog, tokens, log_path=None):
        super().__init__(address, Handler)
        self.catalog = catalog
        self.tokens = tokens
        self.tasks = {}
        self.idempotency = {}
        self.lock = threading.Lock()
        self.log_path = log_path

    def record(self, row):
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    server_version = "MirrorIntegration/0.1"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, fmt, *args):
        # Base logging includes URLs; authorization and user payloads stay private.
        pass

    def prepare(self):
        self.request_id = "req_" + secrets.token_hex(12)
        self.client_id = None
        self.started_at = time.monotonic()
        self.path_only = urlsplit(self.path).path
        expected_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host", "") not in expected_hosts:
            self.error(400, "INVALID_HOST", "Use the documented loopback host and port")
            return False
        if urlsplit(self.path).query:
            self.error(400, "INVALID_ARGUMENT", "Query parameters are not accepted")
            return False
        return True

    def auth(self):
        value = self.headers.get("Authorization", "")
        candidate = value[7:] if value.startswith("Bearer ") else ""
        for client, token in self.server.tokens.items():
            if hmac.compare_digest(candidate.encode("utf-8"), token.encode("utf-8")):
                self.client_id = client
                return True
        self.error(401, "UNAUTHENTICATED", "A valid runtime client token is required")
        return False

    def send_payload(self, status, data, content_type="application/json; charset=utf-8", event=None):
        if isinstance(data, dict):
            body = json.dumps({"request_id": self.request_id, "execution_mode": MODE, **data}, ensure_ascii=False).encode()
        else:
            body = data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; sandbox")
        self.send_header("X-Request-ID", self.request_id)
        self.end_headers()
        self.wfile.write(body)
        self.server.record({"timestamp_utc": now(), "request_id": self.request_id, "client_id": self.client_id,
                            "method": self.command, "path": self.path_only, "http_status": status,
                            "event": event or "response", "elapsed_ms": round((time.monotonic() - self.started_at) * 1000, 3),
                            "execution_mode": MODE})

    def error(self, status, code, message):
        self.send_payload(status, {"error": {"code": code, "message": message}}, event=code)

    def task_view(self, task):
        state = "succeeded" if time.monotonic() - task["created_monotonic"] >= 0.08 else "queued"
        return {"task_id": task["task_id"], "client_id": task["client_id"], "template_id": task["template_id"],
                "input_asset_ref": "fixture:portrait-01", "status": state, "created_at": task["created_at"],
                "output_asset_ref": f"/v1/results/{task['task_id']}.svg" if state == "succeeded" else None,
                "output_kind": "fixed_reference_svg", "model_inference": False}

    def do_GET(self):
        if not self.prepare():
            return
        if self.path_only == "/v1/health":
            self.send_payload(200, {"status": "ok", "api_version": "0.1.0", "model_inference": False})
            return
        if not self.auth():
            return
        if self.path_only == "/v1/templates":
            self.send_payload(200, {"templates": self.server.catalog})
            return
        match = re.fullmatch(r"/v1/tasks/(tsk_[a-f0-9]{24})", self.path_only)
        result = re.fullmatch(r"/v1/results/(tsk_[a-f0-9]{24})\.svg", self.path_only)
        if not (match or result):
            self.error(404, "NOT_FOUND", "No matching API route")
            return
        task_id = (match or result).group(1)
        with self.server.lock:
            task = self.server.tasks.get(task_id)
        if not task or task["client_id"] != self.client_id:
            self.error(404, "TASK_NOT_FOUND", "Task does not exist or is not accessible by this client")
            return
        view = self.task_view(task)
        if match:
            self.send_payload(200, view)
        elif view["status"] != "succeeded":
            self.error(409, "RESULT_NOT_READY", "Query the task until it succeeds")
        else:
            row = next(r for r in self.server.catalog if r["template_id"] == task["template_id"])
            label = html.escape(str(row.get("name", row.get("title", row["template_id"]))))
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640"><rect width="960" height="640" fill="#f4f0e7"/><rect x="60" y="60" width="840" height="520" rx="16" fill="#fff" stroke="#344b5b"/><circle cx="480" cy="250" r="88" fill="#d9b57c"/><path d="M340 470Q480 315 620 470" fill="#344b5b"/><text x="480" y="115" text-anchor="middle" font-size="30" fill="#344b5b">映像魔镜 接口联调</text><text x="480" y="520" text-anchor="middle" font-size="24">{label} · 固定参考输出</text><text x="480" y="552" text-anchor="middle" font-size="17">fixture_replay · 无模型生成 · 无真实人像</text></svg>'''.encode()
            self.send_payload(200, svg, "image/svg+xml; charset=utf-8", event="fixed_reference_result")

    def do_POST(self):
        if not self.prepare() or not self.auth():
            return
        if self.path_only != "/v1/tasks":
            self.error(404, "NOT_FOUND", "No matching API route")
            return
        if self.headers.get("Transfer-Encoding"):
            self.error(400, "INVALID_ARGUMENT", "Chunked requests are not accepted")
            return
        if self.headers.get_content_type() != "application/json":
            self.error(415, "UNSUPPORTED_MEDIA_TYPE", "Send application/json")
            return
        length_text = self.headers.get("Content-Length")
        if length_text is None:
            self.error(411, "LENGTH_REQUIRED", "Content-Length is required")
            return
        try:
            length = int(length_text)
            if length < 0:
                raise ValueError()
        except ValueError:
            self.error(400, "INVALID_ARGUMENT", "Invalid Content-Length")
            return
        if length > MAX_BODY:
            self.error(413, "PAYLOAD_TOO_LARGE", "Request body limit is 4096 bytes")
            return
        key = self.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
            self.error(400, "INVALID_ARGUMENT", "Idempotency-Key must be a 1-80 character identifier")
            return
        try:
            raw = self.rfile.read(length)
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            self.error(400, "INVALID_ARGUMENT", "Invalid JSON body")
            return
        if not isinstance(body, dict) or set(body) != {"template_id", "input_asset_ref"}:
            self.error(400, "INVALID_ARGUMENT", "Only template_id and input_asset_ref are accepted")
            return
        if not isinstance(body.get("template_id"), str) or body["template_id"] not in IDS or body.get("input_asset_ref") != "fixture:portrait-01":
            self.error(400, "INVALID_ARGUMENT", "Select a documented template and the fixed input fixture")
            return
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        id_key = (self.client_id, key)
        with self.server.lock:
            previous = self.server.idempotency.get(id_key)
            if previous:
                if previous["digest"] != digest:
                    conflict = True
                    task = None
                else:
                    conflict = False
                    task = self.server.tasks[previous["task_id"]]
                status = 200
            elif len(self.server.tasks) >= MAX_TASKS:
                conflict = False
                task = None
                status = 429
            else:
                conflict = False
                task_id = "tsk_" + secrets.token_hex(12)
                task = {"task_id": task_id, "client_id": self.client_id, "template_id": body["template_id"],
                        "created_at": now(), "created_monotonic": time.monotonic()}
                self.server.tasks[task_id] = task
                self.server.idempotency[id_key] = {"task_id": task_id, "digest": digest}
                status = 201
        if conflict:
            self.error(409, "IDEMPOTENCY_CONFLICT", "The idempotency key is already associated with different request content")
        elif status == 429:
            self.error(429, "RATE_LIMITED", "The local service task limit is reached; restart for a new isolated session")
        else:
            self.send_payload(status, self.task_view(task), event="task_reused" if status == 200 else "task_created")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parent.parent / "catalog.json")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    try:
        server = IntegrationServer(("127.0.0.1", args.port), load_catalog(args.catalog), load_tokens(), args.log)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        # Configuration errors do not include raw environment values.
        raise SystemExit("Startup failed: check the loopback port, catalog and runtime token configuration") from None
    print(json.dumps({"event": "listening", "base_url": f"http://127.0.0.1:{server.server_port}", "api_version": "0.1.0", "execution_mode": MODE}), flush=True)
    try:
        server.serve_forever(poll_interval=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
