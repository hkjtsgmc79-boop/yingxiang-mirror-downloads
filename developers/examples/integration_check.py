#!/usr/bin/env python3
"""Run real loopback HTTP checks with an independently invoked example client."""
import argparse
import hashlib
import json
import os
import secrets
import select
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = HERE.parent / "api" / "service.py"


def run_checks(output):
    output.mkdir(parents=True, exist_ok=True)
    token_a, token_b = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.pop("MIRROR_API_TOKEN", None)
    env["MIRROR_API_TOKENS_JSON"] = json.dumps({"integration-client-a": token_a, "integration-client-b": token_b})
    log_path = output / "http-requests.jsonl"
    if log_path.exists():
        log_path.write_text("")
    server = subprocess.Popen([sys.executable, str(API), "--port", "0", "--log", str(log_path.resolve())],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    checks = []
    requests = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    summary = None
    try:
        if not select.select([server.stdout], [], [], 8)[0]:
            raise RuntimeError("Local API startup timed out")
        line = server.stdout.readline()
        if not line:
            raise RuntimeError("Local API failed to start; check catalog and port configuration")
        listening = json.loads(line)
        base = listening["base_url"]

        def call(method, route, body=None, token=token_a, key=None, raw=None, headers=None):
            hs = dict(headers or {})
            if token is not None:
                hs["Authorization"] = "Bearer " + token
            if key is not None:
                hs["Idempotency-Key"] = key
            data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
            if data is not None:
                hs.setdefault("Content-Type", "application/json")
            req = urllib.request.Request(base + route, data=data, headers=hs, method=method)
            before = time.monotonic()
            try:
                res = opener.open(req, timeout=5)
            except urllib.error.HTTPError as err:
                res = err
            with res:
                content = res.read(1024 * 1024)
                status = res.code
                rid = res.headers.get("X-Request-ID")
                kind = res.headers.get("Content-Type", "")
            parsed = json.loads(content) if "application/json" in kind else content
            requests.append({"method": method, "path": route, "http_status": status, "request_id": rid,
                             "elapsed_ms": round((time.monotonic() - before) * 1000, 3)})
            return status, parsed

        def check(name, actual, expected, note):
            passed = actual == expected
            checks.append({"case_id": f"API-{len(checks)+1:02d}", "case": name, "expected": expected,
                           "actual": actual, "passed": passed, "observation": note})
            if not passed:
                raise AssertionError("Integration check failed: " + name)

        status, value = call("GET", "/v1/health", token=None)
        check("health", [status, value.get("execution_mode")], [200, "fixture_replay"], "The HTTP service reports its actual fixed-reference mode")
        status, value = call("GET", "/v1/templates", token=None)
        check("missing authentication", [status, value.get("error", {}).get("code")], [401, "UNAUTHENTICATED"], "Catalog access rejects a request without a runtime client token")
        status, value = call("GET", "/v1/templates", token="invalid-token")
        check("wrong authentication", status, 401, "An invalid runtime token is rejected")
        status, value = call("GET", "/v1/templates")
        check("catalog", [status, sorted(r["template_id"] for r in value.get("templates", []))], [200, ["opera-hualian", "opera-qingyi", "opera-wusheng"]], "All three published template IDs match the service catalog")
        body = {"template_id": "opera-qingyi", "input_asset_ref": "fixture:portrait-01"}
        status, first = call("POST", "/v1/tasks", body, key="integration_valid_01")
        check("create task", [status, first.get("client_id"), first.get("model_inference")], [201, "integration-client-a", False], "The client identity is resolved by the server token mapping; no model inference occurs")
        task_id = first["task_id"]
        status, again = call("POST", "/v1/tasks", body, key="integration_valid_01")
        check("idempotency reuse", [status, again.get("task_id")], [200, task_id], "Repeating the same request reuses the existing task")
        status, value = call("POST", "/v1/tasks", {**body, "template_id": "opera-wusheng"}, key="integration_valid_01")
        check("idempotency conflict", [status, value.get("error", {}).get("code")], [409, "IDEMPOTENCY_CONFLICT"], "Reusing the same key for different content does not create a second task")
        for name, data, key in [
            ("unknown template", {**body, "template_id": "unknown"}, "bad_template"),
            ("external asset rejected", {**body, "input_asset_ref": "https://example.invalid/photo.jpg"}, "bad_asset"),
            ("spoofed client rejected", {**body, "client_id": "integration-client-b"}, "bad_client"),
            ("non-string template rejected", {**body, "template_id": []}, "bad_type"),
            ("missing idempotency key", body, None),
        ]:
            status, value = call("POST", "/v1/tasks", data, key=key)
            check(name, [status, value.get("error", {}).get("code")], [400, "INVALID_ARGUMENT"], "Invalid input is rejected before task creation")
        status, value = call("POST", "/v1/tasks", key="bad_json", raw=b"{broken")
        check("malformed JSON", status, 400, "Malformed JSON returns an explicit client error")
        status, value = call("POST", "/v1/tasks", key="oversized", raw=b"x" * 4097)
        check("body size limit", [status, value.get("error", {}).get("code")], [413, "PAYLOAD_TOO_LARGE"], "A body above 4096 bytes is refused")
        status, value = call("POST", "/v1/tasks", body, key="wrong_media", headers={"Content-Type": "text/plain"})
        check("content type", status, 415, "Only JSON task requests are accepted")
        status, value = call("GET", "/v1/tasks/" + task_id, token=token_b)
        check("cross-client task isolation", [status, value.get("error", {}).get("code")], [404, "TASK_NOT_FOUND"], "A second authorized client cannot read the first client's task")
        status, value = call("GET", "/v1/results/" + task_id + ".svg", token=token_b)
        check("cross-client result isolation", [status, value.get("error", {}).get("code")], [404, "TASK_NOT_FOUND"], "The result route enforces the same client ownership check")
        for _ in range(50):
            status, task = call("GET", "/v1/tasks/" + task_id)
            if task.get("status") == "succeeded":
                break
            time.sleep(0.025)
        check("poll to completion", [status, task.get("status"), task.get("output_kind")], [200, "succeeded", "fixed_reference_svg"], "The HTTP task reaches its documented fixed-reference completion state")
        status, svg = call("GET", task["output_asset_ref"])
        check("retrieve result", [status, b"fixture_replay" in svg, "固定参考输出".encode() in svg], [200, True, True], "The returned SVG visibly identifies the fixed-reference mode")
        (output / "checked-result.svg").write_bytes(svg)
        status, value = call("GET", "/v1/tasks/tsk_" + "0" * 24)
        check("missing task", status, 404, "An unknown task returns 404")
        status, value = call("GET", "/v1/unknown")
        check("missing route", status, 404, "An unknown API route returns 404")
        status, value = call("GET", "/v1/health", headers={"Host": "untrusted.invalid"})
        check("loopback host protection", [status, value.get("error", {}).get("code")], [400, "INVALID_HOST"], "An untrusted Host header is rejected")
        child_env = os.environ.copy()
        child_env["MIRROR_API_BASE"] = base
        child_env["MIRROR_API_TOKEN"] = token_a
        child_env.pop("MIRROR_API_TOKENS_JSON", None)
        completed = subprocess.run([sys.executable, str(HERE / "run_client.py"), "--output", str((output / "independent-client").resolve())],
                                   env=child_env, capture_output=True, text=True, timeout=15)
        check("independent client process", completed.returncode, 0, "A separately invoked Python example performs catalog, task, polling and result requests over HTTP")
        child_report = json.loads((output / "independent-client/client-result.json").read_text())
        check("independent client result", [child_report["success"], child_report["execution_mode"], child_report["model_inference"]], [True, "fixture_replay", False], "The independent client saved its actual request IDs and SVG checksum")
        for p in output.rglob("*"):
            if p.is_file():
                data = p.read_bytes()
                if token_a.encode() in data or token_b.encode() in data:
                    raise AssertionError("A runtime credential was included in an output artifact")
        check("credential redaction", True, True, "Generated logs and result files contain neither runtime client token")
        summary = {"success": True, "executed_at_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
                   "passed": len(checks), "failed": 0, "request_count": len(requests), "requests": requests,
                   "elapsed_seconds": round(time.monotonic() - started, 3), "execution_mode": "fixture_replay",
                   "model_inference": False, "real_partner_integration_claimed": False, "runtime_tokens_logged": False,
                   "environment": {"python": sys.version.split()[0], "transport": "real HTTP over 127.0.0.1", "client_execution": "separate subprocess"},
                   "result_sha256": hashlib.sha256(svg).hexdigest()}
        (output / "integration-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "SUMMARY.txt").write_text(f"Actual loopback HTTP integration: {len(checks)} checks passed.\nExecution mode: fixture_replay.\nModel inference: false.\nIndependent example client: separate process.\nExternal partner integration: not claimed.\nRuntime tokens: environment/in-memory only, absent from artifacts.\n", encoding="utf-8")
        return summary
    finally:
        server.terminate()
        try:
            server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("integration-results"))
    args = parser.parse_args()
    try:
        report = run_checks(args.output)
    except (AssertionError, RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # Exception messages are fixed text and never contain credentials or raw requests.
        raise SystemExit("Integration check failed: " + str(exc)) from None
    print(json.dumps({"success": report["success"], "passed": report["passed"], "failed": report["failed"], "execution_mode": report["execution_mode"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
