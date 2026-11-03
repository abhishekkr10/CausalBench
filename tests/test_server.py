import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from causalbench.engine import make_trace
from causalbench.server import Store, handler, connection


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite"
        self.store = Store(self.path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_exact_evidence_download_retains_numeric_representation(self):
        from causalbench.studies import spec_trace
        from causalbench.engine import verify
        run = self.store.create(spec_trace({'scenario': 'stale'}))
        with urllib.request.urlopen(self.url + '/api/evidence/' + run['id']) as response:
            raw = response.read()
        self.assertIn(b'0.0', raw)
        self.assertTrue(verify(json.loads(raw)))
        request = urllib.request.Request(self.url + '/api/verify', data=raw,
                                        headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            self.assertTrue(json.load(response)['valid'])

    def test_offline_design_fonts_are_served_with_correct_type(self):
        for filename in ('manrope-latin-400-normal.woff2', 'manrope-latin-600-normal.woff2',
                         'ibm-plex-mono-latin-400-normal.woff2', 'ibm-plex-mono-latin-500-normal.woff2'):
            with self.subTest(filename=filename), urllib.request.urlopen(self.url + '/vendor/' + filename) as response:
                self.assertEqual(response.headers['Content-Type'], 'font/woff2')
                self.assertEqual(response.read(4), b'wOF2')

    def request(self, path, body=None, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin: headers["Origin"] = origin
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def test_create_and_retrieve(self):
        run = self.request("/api/runs", {"scenario": "stale"})
        self.assertEqual(self.request("/api/runs/" + run["id"]), run)

    def test_history_persists_across_store_instances(self):
        run = self.store.create(make_trace("normal"))
        self.assertEqual(Store(self.path).get(run["id"]), run)

    def test_invalid_scenario_returns_400(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/runs", {"scenario": "bad"})
        self.assertEqual(raised.exception.code, 400)

    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/runs", {"scenario": "normal"}, "https://example.com")
        self.assertEqual(raised.exception.code, 403)

    def test_unknown_run_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/runs/missing")
        self.assertEqual(raised.exception.code, 404)

    def test_verify_endpoint(self):
        run = self.request("/api/runs", {"scenario": "duplicate"})
        self.assertTrue(self.request("/api/verify", run["bundle"])["valid"])

    def test_modified_database_rejected_on_read(self):
        run = self.store.create(make_trace("normal"))
        bundle = run["bundle"]
        bundle["manifest"]["head"] = "bad"
        with connection(self.path) as db:
            db.execute("UPDATE runs SET bundle=? WHERE id=?", (json.dumps(bundle), run["id"]))
        with self.assertRaises(ValueError): self.store.get(run["id"])

    def test_static_page_and_no_traversal(self):
        with urllib.request.urlopen(self.url + "/") as response:
            self.assertIn(b"CausalBench", response.read())
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(self.url + "/../causalbench/server.py")
        self.assertEqual(raised.exception.code, 404)

    def test_health(self):
        self.assertEqual(self.request("/api/health")["status"], "ok")


if __name__ == "__main__": unittest.main()
