#!/usr/bin/env python3
"""Independent HTTP client for the fixed-reference integration API."""
import argparse
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run(base, token, output_dir, template_id="opera-qingyi"):
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path not in ["", "/"] or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an http://127.0.0.1:PORT base for this local integration client")
    if len(token) < 24:
        raise ValueError("Provide a runtime token in MIRROR_API_TOKEN")
    base = base.rstrip("/")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    records = []

    def request(method, path, body=None, key=None):
        headers = {"Authorization": "Bearer " + token}
        if key:
            headers["Idempotency-Key"] = key
        payload = json.dumps(body).encode() if body is not None else None
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base + path, data=payload, headers=headers, method=method)
        started = time.monotonic()
        with opener.open(req, timeout=5) as res:
            content = res.read(1024 * 1024)
            status = res.status
            request_id = res.headers.get("X-Request-ID")
        records.append({"method": method, "path": path, "http_status": status, "request_id": request_id,
                        "elapsed_ms": round((time.monotonic() - started) * 1000, 3)})
        return json.loads(content) if not path.endswith(".svg") else content

    templates = request("GET", "/v1/templates")
    if template_id not in [x["template_id"] for x in templates["templates"]]:
        raise ValueError("The selected template is absent from the API catalog")
    created = request("POST", "/v1/tasks", {"template_id": template_id, "input_asset_ref": "fixture:portrait-01"}, "client_" + secrets.token_hex(8))
    task_id = created["task_id"]
    task = created
    for _ in range(50):
        task = request("GET", "/v1/tasks/" + task_id)
        if task["status"] == "succeeded":
            break
        time.sleep(0.025)
    if task["status"] != "succeeded" or task.get("execution_mode") != "fixture_replay":
        raise RuntimeError("The integration task did not complete in the documented fixed-reference mode")
    image = request("GET", task["output_asset_ref"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.svg").write_bytes(image)
    report = {"executed_at_utc": datetime.now(timezone.utc).isoformat(), "client": "independent-python-example",
              "environment": "loopback HTTP integration", "execution_mode": "fixture_replay", "model_inference": False,
              "real_partner_integration_claimed": False, "base_url": base, "task_id": task_id, "template_id": template_id,
              "result_file": "result.svg", "result_sha256": hashlib.sha256(image).hexdigest(), "requests": records,
              "success": True, "runtime_token_logged": False}
    (output_dir / "client-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("integration-results/client"))
    parser.add_argument("--template", default="opera-qingyi")
    args = parser.parse_args()
    try:
        report = run(os.environ.get("MIRROR_API_BASE", "http://127.0.0.1:8791"), os.environ.get("MIRROR_API_TOKEN", ""), args.output, args.template)
    except (ValueError, OSError, KeyError, urllib.error.URLError, RuntimeError):
        raise SystemExit("Client failed: check the running local service, runtime token and API response; no token was printed") from None
    print(json.dumps({"success": report["success"], "task_id": report["task_id"], "execution_mode": report["execution_mode"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
