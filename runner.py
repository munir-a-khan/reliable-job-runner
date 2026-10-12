"""Local synthetic job runner. Python standard library only."""
import argparse
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as c:
            c.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL, due REAL NOT NULL, lease REAL,
                    token TEXT, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    job_id TEXT NOT NULL, number INTEGER NOT NULL, token TEXT NOT NULL,
                    started REAL NOT NULL, ended REAL, outcome TEXT,
                    PRIMARY KEY(job_id, number));
                CREATE TABLE IF NOT EXISTS effects (
                    job_id TEXT PRIMARY KEY, result TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ready_jobs ON jobs(state, due);
            ''')

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            c.execute('PRAGMA foreign_keys=ON')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def submit(self, key, payload):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key):
            raise ValueError('key must contain 1-64 letters, digits, underscores or hyphens')
        if not isinstance(payload, dict) or set(payload) != {'value', 'failures', 'permanent', 'max_attempts'}:
            raise ValueError('payload requires value, failures, permanent, max_attempts')
        if (type(payload['value']) is not int or abs(payload['value']) > 1000000
                or type(payload['failures']) is not int or not 0 <= payload['failures'] <= 5
                or type(payload['permanent']) is not bool
                or type(payload['max_attempts']) is not int or not 1 <= payload['max_attempts'] <= 5):
            raise ValueError('invalid synthetic job parameters')
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT * FROM jobs WHERE request_key=?', (key,)).fetchone()
            if old:
                if old['payload'] != encoded:
                    raise ValueError('key already belongs to a different payload')
                return old['id'], False
            job_id = uuid.uuid4().hex
            now = time.time()
            c.execute('INSERT INTO jobs VALUES(?,?,?,\'queued\',0,?,?,NULL,NULL,?)',
                      (job_id, key, encoded, payload['max_attempts'], now, now))
            return job_id, True

    def claim(self, lease_seconds=5):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            now = time.time()
            expired = c.execute("SELECT * FROM jobs WHERE state='running' AND lease<=?", (now,)).fetchall()
            for job in expired:
                c.execute("UPDATE attempts SET ended=?,outcome='lease_expired' WHERE token=? AND ended IS NULL", (now, job['token']))
                state = 'failed' if job['attempts'] >= job['max_attempts'] else 'retry_wait'
                c.execute('UPDATE jobs SET state=?,due=?,lease=NULL,token=NULL WHERE id=?',
                          (state, now + min(8, 2 ** (job['attempts'] - 1)), job['id']))
            job = c.execute("SELECT * FROM jobs WHERE state IN ('queued','retry_wait') AND due<=? ORDER BY created,id LIMIT 1", (now,)).fetchone()
            if not job:
                return None
            token = uuid.uuid4().hex
            number = job['attempts'] + 1
            c.execute("UPDATE jobs SET state='running',attempts=?,token=?,lease=? WHERE id=?", (number, token, now + lease_seconds, job['id']))
            c.execute('INSERT INTO attempts VALUES(?,?,?,?,NULL,NULL)', (job['id'], number, token, now))
            return dict(job) | {'attempts': number, 'token': token}

    def finish(self, job):
        p = json.loads(job['payload'])
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            now = time.time()
            current = c.execute('SELECT * FROM jobs WHERE id=?', (job['id'],)).fetchone()
            if current['state'] != 'running' or current['token'] != job['token'] or current['lease'] <= now:
                return False  # Fence stale workers before committing any demo effect.
            error = 'permanent_failure' if p['permanent'] else ('transient_failure' if job['attempts'] <= p['failures'] else None)
            state = ('failed' if p['permanent'] or job['attempts'] >= current['max_attempts'] else 'retry_wait') if error else 'succeeded'
            if not error:
                c.execute('INSERT INTO effects VALUES(?,?)', (job['id'], str(p['value'] * p['value'])))
            c.execute('UPDATE jobs SET state=?,due=?,lease=NULL,token=NULL WHERE id=?',
                      (state, now + min(8, 2 ** (job['attempts'] - 1)), job['id']))
            c.execute('UPDATE attempts SET ended=?,outcome=? WHERE token=?', (now, error or 'succeeded', job['token']))
            return True

    def history(self):
        with self.db() as c:
            return {table: [dict(r) for r in c.execute(f'SELECT * FROM {table}')] for table in ('jobs', 'attempts', 'effects')}


def worker(store, once=False, lease_seconds=5, pause_after_claim=0, pause_after_commit=0):
    while True:
        try:
            job = store.claim(lease_seconds)
            if job:
                print('claimed ' + job['id'], flush=True)
                time.sleep(pause_after_claim)
                committed = store.finish(job)
                print(('finished ' if committed else 'fenced ') + job['id'], flush=True)
                time.sleep(pause_after_commit)
        except sqlite3.OperationalError:
            print('database temporarily unavailable; retrying', flush=True)
        if once:
            return
        time.sleep(0.2)


def serve(store, port):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass  # Request bodies and arbitrary headers never enter logs.

        def send(self, status, body, content_type='application/json'):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                return self.send(403, {'error': 'host rejected'})
            if self.path == '/api/jobs':
                self.send(200, store.history())
            elif self.path == '/':
                self.send(200, Path(__file__).with_name('dashboard.html').read_text(encoding='utf-8'), 'text/html; charset=utf-8')
            else:
                self.send(404, {'error': 'not found'})

        def do_POST(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                return self.send(403, {'error': 'host rejected'})
            if self.path != '/api/jobs':
                return self.send(404, {'error': 'not found'})
            if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}'):
                return self.send(403, {'error': 'origin rejected'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2048 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('send application/json up to 2048 bytes')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or set(data) != {'key', 'payload'}:
                    raise ValueError('request requires key and payload')
                job_id, created = store.submit(data['key'], data['payload'])
                self.send(201 if created else 200, {'id': job_id, 'created': created})
            except (ValueError, UnicodeError, RecursionError):
                self.send(409, {'error': 'invalid request or key/payload conflict'})
            except sqlite3.Error:
                self.send(503, {'error': 'database unavailable'})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Dashboard: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['api', 'worker'])
    parser.add_argument('--db', default='jobs.sqlite')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--lease-seconds', type=float, default=5)
    parser.add_argument('--pause-after-claim', type=float, default=0)
    parser.add_argument('--pause-after-commit', type=float, default=0)
    args = parser.parse_args()
    store = Store(args.db)
    if args.mode == 'api':
        serve(store, args.port)
    else:
        worker(store, args.once, args.lease_seconds, args.pause_after_claim, args.pause_after_commit)
