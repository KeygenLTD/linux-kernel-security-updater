"""HMAC-authenticated reporting client and persistent fleet dashboard."""
import argparse
import hashlib
import hmac
import json
from urllib.parse import urlsplit
import sqlite3
import ssl
import time
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def signature(secret, timestamp, body):
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def send_report(config, payload):
    fleet = config.get("fleet") or {}
    if not fleet.get("url"):
        return None
    endpoint = fleet["url"].rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid fleet URL: credentials and query parameters are forbidden")
    try:
        local_host = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    except ValueError as exc:
        raise ValueError("Invalid fleet URL") from exc
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local_host):
        raise ValueError("Fleet telemetry requires HTTPS (HTTP only allowed for loopback)")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    if len(body) > 1024 * 1024:
        raise ValueError("Fleet report exceeds 1 MiB limit")
    timestamp = str(int(time.time()))
    request = urllib.request.Request(endpoint + "/api/v1/report", data=body, method="POST", headers={
        "Content-Type": "application/json", "X-LKSU-Server": fleet["server_id"],
        "X-LKSU-Timestamp": timestamp, "X-LKSU-Signature": signature(fleet["secret"], timestamp, body),
    })
    with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
        return response.status


def init_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS reports (server_id TEXT PRIMARY KEY, received_at INTEGER NOT NULL, payload TEXT NOT NULL)")
    db.commit()
    return db


def handler_factory(db_path, secrets, dashboard_token, stale_after_seconds=900):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LKSUFleet/0.2"

        def send_json(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def send_html(self, body):
            data = body.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def authorized_dashboard(self):
            return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + dashboard_token)

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def do_POST(self):
            if self.path != "/api/v1/report": return self.send_json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self.send_json(400, {"error": "invalid Content-Length"})
            if length < 2 or length > 1024 * 1024: return self.send_json(413, {"error": "invalid size"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self.send_json(415, {"error": "Content-Type must be application/json"})
            body = self.rfile.read(length); server_id = self.headers.get("X-LKSU-Server", "")
            timestamp = self.headers.get("X-LKSU-Timestamp", ""); supplied = self.headers.get("X-LKSU-Signature", "")
            secret = secrets.get(server_id)
            try: fresh = abs(int(time.time()) - int(timestamp)) <= 300
            except ValueError: fresh = False
            if not secret or not fresh or not hmac.compare_digest(supplied, signature(secret, timestamp, body)):
                return self.send_json(401, {"error": "unauthorized"})
            try: payload = json.loads(body)
            except json.JSONDecodeError: return self.send_json(400, {"error": "invalid json"})
            with closing(init_db(db_path)) as db:
                db.execute("INSERT INTO reports(server_id,received_at,payload) VALUES(?,?,?) ON CONFLICT(server_id) DO UPDATE SET received_at=excluded.received_at,payload=excluded.payload", (server_id, int(time.time()), json.dumps(payload)))
                db.commit()
            self.send_json(202, {"accepted": True})

        def do_GET(self):
            if self.path == "/healthz": return self.send_json(200, {"ok": True})
            if self.path == "/":
                return self.send_html("""<!doctype html><meta charset=utf-8><title>LKSU Fleet</title>
<style>body{font:16px system-ui;background:#08131f;color:#d9e8f5;max-width:1100px;margin:40px auto;padding:20px}input,button{padding:10px;margin:4px;background:#12263a;color:white;border:1px solid #285274;border-radius:7px}table{width:100%;border-collapse:collapse;margin-top:20px}td,th{padding:10px;border-bottom:1px solid #24445e;text-align:left}.ok{color:#55dc8a}.bad{color:#ffb45e}</style>
<h1>LKSU Fleet</h1><p>Enter the dashboard token. It stays in this browser tab and is sent only as an Authorization header.</p>
<input id=t type=password autocomplete=off><button onclick=load()>Refresh</button><div id=s></div>
<script>async function load(){let r=await fetch('/api/v1/servers',{headers:{Authorization:'Bearer '+document.querySelector('#t').value}});if(!r.ok){s.textContent='Unauthorized';return}let d=await r.json();s.innerHTML='<table><tr><th>Server</th><th>Last report</th><th>Command</th><th>Status</th></tr>'+d.map(x=>`<tr><td>${esc(x.server_id)}</td><td>${new Date(x.received_at*1000).toLocaleString()}</td><td>${esc(x.report.command||'')}</td><td class=${x.stale||x.report.result?.status==='alert'||x.report.result?.healthy===false?'bad':'ok'}>${x.stale?'SILENT / STALE':esc(x.report.result?.status||String(x.report.result?.healthy??''))}</td></tr>`).join('')+'</table>'}function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</script>""")
            if self.path != "/api/v1/servers" or not self.authorized_dashboard(): return self.send_json(401, {"error": "unauthorized"})
            with closing(init_db(db_path)) as db:
                now = int(time.time())
                rows = [{"server_id": row[0], "received_at": row[1], "stale": now - row[1] > stale_after_seconds, "report": json.loads(row[2])} for row in db.execute("SELECT server_id,received_at,payload FROM reports ORDER BY server_id")]
            self.send_json(200, rows)

        def log_message(self, fmt, *args):
            return
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="LKSU fleet report collector")
    parser.add_argument("--config", default="/etc/lksu/fleet-server.json")
    args = parser.parse_args(argv); config = json.loads(Path(args.config).read_text())
    bind = config.get("bind", "127.0.0.1"); port = int(config.get("port", 9443))
    if bind not in {"127.0.0.1", "::1", "localhost"} and not (config.get("tls_cert") and config.get("tls_key")):
        raise SystemExit("TLS certificate and key are required for a non-loopback bind")
    server = ThreadingHTTPServer((bind, port), handler_factory(config["database"], config["servers"], config["dashboard_token"], int(config.get("stale_after_seconds", 900))))
    server.daemon_threads = True
    if config.get("tls_cert"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(config["tls_cert"], config["tls_key"])
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__": main()
