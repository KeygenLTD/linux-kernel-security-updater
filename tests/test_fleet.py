import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from lksu.fleet import handler_factory, signature

class FleetTests(unittest.TestCase):
    def test_signature_is_stable_and_body_bound(self):
        first = signature("secret", "100", b"one")
        self.assertEqual(first, signature("secret", "100", b"one"))
        self.assertNotEqual(first, signature("secret", "100", b"two"))

    def test_collector_accepts_signed_report_and_persists_it(self):
        with tempfile.TemporaryDirectory(dir=".") as temp:
            database = str(Path(temp) / "fleet.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(database, {"node-1": "secret"}, "dashboard"))
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                body = json.dumps({"command": "check", "result": {"status": "ok"}}).encode()
                timestamp = str(int(time.time()))
                request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/v1/report", data=body, method="POST", headers={
                    "X-LKSU-Server": "node-1", "X-LKSU-Timestamp": timestamp,
                    "X-LKSU-Signature": signature("secret", timestamp, body), "Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response: self.assertEqual(response.status, 202)
                listing = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/v1/servers", headers={"Authorization": "Bearer dashboard"})
                with urllib.request.urlopen(listing) as response: data = json.load(response)
                self.assertEqual(data[0]["server_id"], "node-1")
                self.assertFalse(data[0]["stale"])
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

if __name__ == "__main__": unittest.main()
