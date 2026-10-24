"""Local-only Context7 gateway. MCP/authentication are a later deployment stage."""
import argparse
import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get('GATEWAY_DATA', '/data'))
TTL = 7 * 86400
CEILING = 900

class Blocked(Exception):
    pass

@contextmanager
def database():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'gateway.sqlite3', timeout=60)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
          CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT);
          INSERT OR IGNORE INTO state VALUES (1, '{}');
          CREATE TABLE IF NOT EXISTS cache (id TEXT PRIMARY KEY, fetched REAL, body TEXT);
        ''')
        yield db
    finally:
        db.close()

def load(db):
    return json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])

def save(db, state):
    db.execute('UPDATE state SET value=? WHERE id=1', (json.dumps(state),))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def upstream(path, params=None):
    key = Path('/run/secrets/context7_api_key').read_text().strip()
    if not key:
        raise Blocked('Context7 key is empty')
    url = 'https://context7.com/api/' + path
    if params:
        url += '?' + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise Blocked('Upstream response exceeded 4 MiB')
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        raise Blocked(f'Context7 returned HTTP {exc.code}; no automatic retry') from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Blocked('Context7 unavailable or returned invalid JSON; no automatic retry') from None

def reconcile(db, state):
    usage = upstream('v2/usage')
    try:
        reset = usage['usageResetsAt']
        timestamp = datetime.fromisoformat(reset.replace('Z', '+00:00')).timestamp()
        used = usage['member']['requests']
        included = usage['member']['includedInPlan']
        now = time.time()
        if (type(used) is not int or type(included) is not int or used < 0
                or included <= 0 or not now < timestamp <= now + 32 * 86400):
            raise ValueError()
        # Reject stale or unexpected billing periods rather than resetting the meter early.
        if state.get('reset') != reset:
            if state.get('reset_epoch', 0) > now:
                raise ValueError()
            state['spent'] = 0
        state.update(reset=reset, reset_epoch=timestamp,
                     spent=max(state.get('spent', 0), used),
                     provider_used=used, ceiling=min(CEILING, included), synced_at=now)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Blocked('Invalid or unexpected usage response; fresh lookups blocked') from None
    save(db, state)

def status(sync=False):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(db)
        if sync:
            reconcile(db, state)
        db.commit()
        now = time.time()
        return {**state, 'configured_monthly_ceiling': CEILING,
                'authorization_active': state.get('expires', 0) > now and state.get('calls', 0) > 0,
                'cached_queries': db.execute('SELECT COUNT(*) FROM cache').fetchone()[0]}

def authorize(minutes, calls):
    if not 1 <= minutes <= 60 or not 1 <= calls <= 10:
        raise ValueError('Use 1–60 minutes and 1–10 calls')
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(db)
        state.update(expires=time.time() + minutes * 60, calls=calls)
        save(db, state)
        db.commit()

def revoke():
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        state = load(db)
        state.update(expires=0, calls=0)
        save(db, state)
        db.commit()

def normalize(payload):
    if not isinstance(payload, dict) or set(payload) - {'query', 'library', 'version', 'language'}:
        raise ValueError('Allowed fields: query, library, version, language')
    result = {'type': 'json'}
    for field in ('query', 'version', 'language'):
        value = payload.get(field, '')
        if not isinstance(value, str) or len(value) > 4000:
            raise ValueError('Invalid ' + field)
        if value.strip():
            result[field] = ' '.join(value.split())
    if 'query' not in result:
        raise ValueError('query is required')
    libs = payload.get('library', [])
    if isinstance(libs, str):
        libs = [libs]
    if (not isinstance(libs, list) or len(libs) > 4
            or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in libs)):
        raise ValueError('library must contain up to four nonempty strings')
    if libs:
        result['library'] = sorted(set(x.strip() for x in libs))
    if 'version' in result and not libs:
        raise ValueError('version requires library')
    return result

def search(payload):
    params = normalize(payload)
    cache_id = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    with database() as db:
        # Serialize usage reconciliation, reservation and outbound work across processes.
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM cache WHERE id=?', (cache_id,)).fetchone()
        now = time.time()
        if row and 0 <= now - row['fetched'] < TTL:
            db.commit()
            return {'cache_id': cache_id, 'cached': True, 'age_seconds': int(now-row['fetched']),
                    'fetched_at': row['fetched'], 'documentation': json.loads(row['body'])}
        state = load(db)
        if state.get('expires', 0) <= now or state.get('calls', 0) <= 0:
            raise Blocked('Fresh lookups locked; authorize from the server CLI')
        reconcile(db, state)
        if state['spent'] >= state['ceiling']:
            db.commit()
            raise Blocked('Monthly ceiling reached')
        # Recheck time after network I/O; do not send at a billing boundary.
        if time.time() >= min(state['expires'], state['reset_epoch'] - 30):
            db.commit()
            raise Blocked('Authorization expired or monthly reset is imminent')
        state['spent'] += 1
        state['calls'] -= 1
        save(db, state)
        db.commit()  # Durable BEFORE sending; failures/crashes remain charged locally.
        result = upstream('v3/search', params)
        fetched = time.time()
        db.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)',
                   (cache_id, fetched, json.dumps(result)))
        # Bound the cache to 500 entries, each upstream body at most 4 MiB.
        db.execute('DELETE FROM cache WHERE id NOT IN (SELECT id FROM cache ORDER BY fetched DESC LIMIT 500)')
        db.commit()
        return {'cache_id': cache_id, 'cached': False, 'age_seconds': 0,
                'fetched_at': fetched, 'documentation': result}

def read_cache(cache_id):
    with database() as db:
        row = db.execute('SELECT * FROM cache WHERE id=?', (cache_id,)).fetchone()
        if not row:
            raise ValueError('Unknown cache ID')
        age = max(0, int(time.time() - row['fetched']))
        return {'cache_id': cache_id, 'cached': True, 'age_seconds': age,
                'stale': age >= TTL, 'fetched_at': row['fetched'],
                'documentation': json.loads(row['body'])}

class Handler(BaseHTTPRequestHandler):
    timeout = 10

    def log_message(self, *args):
        pass  # Avoid logging queries, document contents or credentials.

    def reply(self, code, body):
        encoded = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        try:
            if self.path == '/health':
                with database() as db:
                    db.execute('SELECT 1').fetchone()
                self.reply(200, {'status': 'ok', 'stage': 'meter-and-cache'})
            elif self.path == '/status':
                self.reply(200, status())
            elif self.path.startswith('/cache/'):
                self.reply(200, read_cache(self.path.removeprefix('/cache/')))
            else:
                self.reply(404, {'error': 'Unknown endpoint'})
        except ValueError as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            self.reply(503, {'error': 'Local storage unavailable'})

    def do_POST(self):
        if self.path != '/search':
            self.reply(404, {'error': 'Unknown endpoint'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Request must be 1–16384 bytes')
            self.reply(200, search(json.loads(self.rfile.read(length))))
        except Blocked as exc:
            self.reply(429, {'error': str(exc)})
        except (ValueError, UnicodeError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            self.reply(503, {'error': 'Gateway unavailable; request may have been reserved'})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs='?', choices=['serve', 'status', 'authorize', 'revoke'], default='serve')
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--minutes', type=int, default=60)
    parser.add_argument('--calls', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'serve':
        with database():
            pass
        ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
    else:
        if args.command == 'authorize':
            authorize(args.minutes, args.calls)
        elif args.command == 'revoke':
            revoke()
        print(json.dumps(status(args.sync), indent=2))

if __name__ == '__main__':
    main()
