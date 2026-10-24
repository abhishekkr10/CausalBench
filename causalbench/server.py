"""Loopback-only HTTP service with durable SQLite experiment storage."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import argparse
import base64
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .engine import SCENARIOS, canonical, compare, make_trace, seal, validate_trace, verify, digest
from .studies import spec_trace, regression, check_regression
from .faults import configuration
from .controllers import registry
from .capture import Recorder
from .jobs import Jobs
from . import packages

ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def connection(path):
    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = threading.Lock()
        with connection(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, scenario TEXT NOT NULL, bundle TEXT NOT NULL)")
            db.execute('CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, created TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS source_sets (id TEXT PRIMARY KEY, sha TEXT NOT NULL, payload BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS run_sources (run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS artifact_sources (artifact_id TEXT PRIMARY KEY, source_id TEXT NOT NULL)')

    def create(self, trace):
        validate_trace(trace)
        bundle = seal(trace, compare(trace))
        run_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        source_id, source_bytes = packages.source_snapshot()
        with self.lock, connection(self.path) as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?)", (run_id, created, str(trace.get("scenario", "imported"))[:100], canonical(bundle)))
            import hashlib
            db.execute('INSERT OR IGNORE INTO source_sets VALUES (?,?,?)',(source_id,hashlib.sha256(source_bytes).hexdigest(),source_bytes))
            db.execute('INSERT INTO run_sources VALUES (?,?)',(run_id,source_id))
        return {"id": run_id, "created": created, "bundle": bundle}

    def get(self, run_id):
        with connection(self.path) as db:
            row = db.execute("SELECT id,created,bundle FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Run not found")
        bundle = json.loads(row[2])
        if not verify(bundle):
            raise ValueError("Stored experiment failed integrity verification")
        return {"id": row[0], "created": row[1], "bundle": bundle}

    def list(self):
        with connection(self.path) as db:
            rows = db.execute("SELECT id,created,scenario FROM runs ORDER BY created DESC LIMIT 100").fetchall()
        return [dict(zip(("id", "created", "scenario"), row)) for row in rows]

    def package(self, run_id):
        import hashlib
        run=self.get(run_id)
        with connection(self.path) as db:
            row=db.execute('SELECT s.sha,s.payload FROM source_sets s JOIN run_sources r ON s.id=r.source_id WHERE r.run_id=?',(run_id,)).fetchone()
        if row is None:
            raise ValueError('This older run has no archived source. Replay it into a new run before packaging.')
        if hashlib.sha256(row[1]).hexdigest()!=row[0]:
            raise ValueError('Archived source integrity failed')
        return packages.build(run['bundle'],row[1])

    def save_artifact(self,kind,payload,source=None):
        identity=uuid.uuid4().hex
        created=datetime.now(timezone.utc).isoformat()
        value=canonical(payload)
        source_id,source_bytes=source if source is not None else packages.source_snapshot()
        if len(value.encode())>16000000:
            raise ValueError('Analysis artifact exceeds 16 MB')
        with self.lock,connection(self.path) as db:
            db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)',(identity,created,kind,value,digest(payload)))
            import hashlib
            db.execute('INSERT OR IGNORE INTO source_sets VALUES (?,?,?)',(source_id,hashlib.sha256(source_bytes).hexdigest(),source_bytes))
            db.execute('INSERT INTO artifact_sources VALUES (?,?)',(identity,source_id))
        return {'id':identity,'created':created,'kind':kind,'payload':payload}

    def artifact_package(self,identity):
        import hashlib
        artifact=self.artifact(identity)
        with connection(self.path) as db:
            row=db.execute('SELECT s.sha,s.payload FROM source_sets s JOIN artifact_sources a ON s.id=a.source_id WHERE a.artifact_id=?',(identity,)).fetchone()
        if row is None or hashlib.sha256(row[1]).hexdigest()!=row[0]:
            raise ValueError('Archived analysis source missing or modified')
        return packages.build_analysis(artifact['payload'],row[1])

    def artifact(self,identity):
        with connection(self.path) as db:
            row=db.execute('SELECT id,created,kind,payload,digest FROM artifacts WHERE id=?',(identity,)).fetchone()
        if row is None:
            raise KeyError('Artifact not found')
        payload=json.loads(row[3])
        if digest(payload)!=row[4]:
            raise ValueError('Stored artifact integrity failed')
        return {'id':row[0],'created':row[1],'kind':row[2],'payload':payload}

    def artifacts(self,kind=None):
        with connection(self.path) as db:
            rows=db.execute('SELECT id,created,kind FROM artifacts WHERE (? IS NULL OR kind=?) ORDER BY created DESC LIMIT 100',(kind,kind)).fetchall()
        return [dict(zip(('id','created','kind'),row)) for row in rows]


def handler(store):
    recorder=Recorder()
    jobs=Jobs(store)
    class Handler(BaseHTTPRequestHandler):
        def local_host(self):
            port=self.server.server_port
            return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')

        def send(self, status, value, content_type="application/json"):
            data = canonical(value).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.local_host():
                self.send(403,{'error':'Loopback Host header required'})
                return
            try:
                if self.path == "/api/health":
                    self.send(200, {"status": "ok", "mode": "simulation", "engine": "2.0.0"})
                elif self.path == '/api/controllers':
                    self.send(200,registry())
                elif self.path == '/api/capture':
                    self.send(200,recorder.snapshot())
                elif self.path == '/api/artifacts':
                    self.send(200,store.artifacts())
                elif self.path.startswith('/api/artifacts/'):
                    self.send(200,store.artifact(self.path.split('/')[-1]))
                elif self.path.startswith('/api/jobs/'):
                    self.send(200,jobs.get(self.path.split('/')[-1]))
                elif self.path == '/api/profiles':
                    self.send(200,[store.artifact(a['id']) for a in store.artifacts('profile')])
                elif self.path == '/api/regressions':
                    self.send(200,[store.artifact(a['id']) for a in store.artifacts('regression')])
                elif self.path.startswith('/api/packages/'):
                    self.send(200,store.package(self.path.split('/')[-1]),'application/zip')
                elif self.path.startswith('/api/artifact-packages/'):
                    self.send(200,store.artifact_package(self.path.split('/')[-1]),'application/zip')
                elif self.path == "/api/runs":
                    self.send(200, store.list())
                elif self.path.startswith("/api/runs/"):
                    self.send(200, store.get(self.path.split("/")[-1]))
                elif self.path in ("/", "/app.js", "/lab.js", "/style.css"):
                    name = "index.html" if self.path == "/" else self.path[1:]
                    kind = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "lab.js":"text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
                    self.send(200, (ROOT / "web" / name).read_bytes(), kind)
                else:
                    self.send(404, {"error": "Not found"})
            except KeyError:
                self.send(404, {"error": "Run not found"})
            except (ValueError,TypeError,OSError) as error:
                self.send(409, {"error": str(error)})

        def do_POST(self):
            if not self.local_host():
                self.send(403,{'error':'Loopback Host header required'})
                return
            # Reject cross-origin browser mutations and non-JSON form requests.
            host = self.headers.get("Host", "")
            if self.headers.get("Origin") not in (None, f"http://{host}"):
                self.send(403, {"error": "Cross-origin request rejected"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send(415, {"error": "JSON required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit=24000000 if self.path=='/api/packages/import' else 32000000 if self.path=='/api/verify' else 2500000 if self.path=='/api/runs' else 2000000
                if not 1 <= length <= limit:
                    raise ValueError(f"Body must be 1..{limit} bytes")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                if self.path == "/api/runs":
                    trace = body.get("trace") if "trace" in body else spec_trace(body) if any(k in body for k in ('faults','controllers','configs','multistream','events')) else make_trace(body.get("scenario"))
                    self.send(201, store.create(trace))
                elif self.path == '/api/jobs':
                    self.send(202,jobs.submit(body.get('kind'),body))
                elif self.path == '/api/profiles':
                    name=body.get('name')
                    if not isinstance(name,str) or not 1<=len(name)<=100:
                        raise ValueError('Profile name must be 1..100 characters')
                    cfg=configuration(body.get('configuration'))
                    self.send(201,store.save_artifact('profile',{'name':name,'configuration':cfg}))
                elif self.path == '/api/regressions':
                    run=store.get(body.get('run_id',''))
                    case=regression(run['bundle']['manifest']['trace'],body.get('name'),body.get('limits'))
                    self.send(201,store.save_artifact('regression',case))
                elif self.path == '/api/regressions/check':
                    cases=[store.artifact(body['id'])] if 'id' in body else [store.artifact(a['id']) for a in store.artifacts('regression')]
                    if any(c['kind']!='regression' for c in cases):
                        raise ValueError('Selected artifact is not a regression')
                    result={'kind':'regression-check','cases':[check_regression(c['payload']) for c in cases]}
                    result['reproduction_input']={'cases':[c['payload'] for c in cases]}
                    self.send(200,store.save_artifact('regression-check',result))
                elif self.path == '/api/capture/start':
                    self.send(201,recorder.start(body))
                elif self.path == '/api/capture/stop':
                    self.send(200,recorder.stop())
                elif self.path == '/api/capture/snapshot':
                    trace=recorder.trace()
                    if 'configs' in body:
                        trace['controller_configs']=body['configs']
                    if 'controllers' in body:
                        trace['controllers']=body['controllers']
                    self.send(201,store.create(trace))
                elif self.path == '/api/packages/import':
                    try:
                        data=base64.b64decode(body.get('data',''),validate=True)
                    except Exception as exc:
                        raise ValueError('Package data must be base64') from exc
                    checked=packages.inspect(data)
                    if checked.get('kind')=='analysis':
                        artifact=store.save_artifact(checked['analysis']['kind'],checked['analysis'],packages.archived_sources(data))
                        self.send(201,{'inspection':{k:v for k,v in checked.items() if k!='analysis'},'artifact':artifact})
                        return
                    # Archived source is inspected only. Current installed controllers execute the imported trace.
                    run=store.create(checked['bundle']['manifest']['trace'])
                    self.send(201,{'inspection':{k:v for k,v in checked.items() if k!='bundle'},'run':run})
                elif self.path == "/api/verify":
                    self.send(200, {"valid": verify(body)})
                else:
                    self.send(404, {"error": "Not found"})
            except KeyError as error:
                self.send(404, {'error':str(error)})
            except (ValueError, TypeError, OSError) as error:
                self.send(400, {"error": str(error)})

        def log_message(self, format, *args):
            pass
    Handler.recorder = recorder
    return Handler


def main():
    parser = argparse.ArgumentParser(description="CausalBench local simulation laboratory")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--database", default=str(ROOT / "data" / "experiments.sqlite"))
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(Store(args.database)))
    print(f"CausalBench: http://127.0.0.1:{args.port} — simulation only", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
