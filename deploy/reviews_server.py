#!/usr/bin/env python3
"""Gallop review collector. Stdlib only, no database.

POST /api/reviews            body: one review JSON object  -> appended to REVIEWS_FILE as one line
GET  /api/reviews?token=...  -> the whole file (application/x-ndjson); token must match REVIEWS_TOKEN
GET  /api/reviews/health     -> ok

Runs behind the gallop nginx container (see nginx.conf, location /api/).
No access log and no IP stored: reviews carry only what the reviewer typed
plus a server timestamp.

    python reviews_server.py          # serve on PORT (default 8080)
    python reviews_server.py --check  # self-test against a temp file
"""
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = os.environ.get("REVIEWS_FILE", "/data/reviews.jsonl")
TOKEN = os.environ.get("REVIEWS_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") != "/api/reviews":
            return self._send(404, '{"error":"not found"}')
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._send(413, '{"error":"body must be 1 byte to 64 KB"}')
        try:
            r = json.loads(self.rfile.read(n))
            if not isinstance(r, dict) or not isinstance(r.get("case_id"), str) or not r["case_id"]:
                raise ValueError
        except Exception:
            return self._send(400, '{"error":"expected a review object with a case_id"}')
        r["received_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        os.makedirs(os.path.dirname(DATA) or ".", exist_ok=True)
        with open(DATA, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self._send(200, '{"ok":true}')

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path == "/api/reviews/health":
            return self._send(200, "ok", "text/plain")
        if path.rstrip("/") != "/api/reviews":
            return self._send(404, '{"error":"not found"}')
        if not TOKEN or not hmac.compare_digest(params.get("token", ""), TOKEN):
            return self._send(403, '{"error":"token required"}')
        body = open(DATA, "rb").read() if os.path.exists(DATA) else b""
        self._send(200, body, "application/x-ndjson")

    def log_message(self, *args):  # no access log: nothing about who reviewed is recorded beyond what they typed
        pass


def serve():
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


def check():
    import tempfile
    import threading
    import urllib.request
    from urllib.error import HTTPError

    global DATA, TOKEN
    DATA = os.path.join(tempfile.mkdtemp(), "reviews.jsonl")
    TOKEN = "t3st"
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def req(method, path, data=None):
        rq = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq) as resp:
                return resp.status, resp.read()
        except HTTPError as e:
            return e.code, e.read()

    assert req("GET", "/api/reviews/health") == (200, b"ok")
    assert req("POST", "/api/reviews", b'{"case_id":"as-ejection","answers":{"R10":"Not yet"}}')[0] == 200
    assert req("POST", "/api/reviews", b'{"answers":{}}')[0] == 400, "case_id required"
    assert req("POST", "/api/reviews", b"x" * (MAX_BODY + 1))[0] == 413, "size cap"
    assert req("GET", "/api/reviews")[0] == 403, "token required"
    assert req("GET", "/api/reviews?token=wrong")[0] == 403
    code, body = req("GET", "/api/reviews?token=t3st")
    rows = [json.loads(l) for l in body.decode().splitlines()]
    assert code == 200 and len(rows) == 1 and rows[0]["case_id"] == "as-ejection" and "received_at" in rows[0]
    srv.shutdown()
    print("reviews_server self-check OK")


if __name__ == "__main__":
    check() if "--check" in sys.argv else serve()
