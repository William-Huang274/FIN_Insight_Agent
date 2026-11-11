"""Shared public-response cache and request admission using SQLite + FileLock.

Not a research state store. Keys include provider credential identity; failed
requests consume the local request allowance but are never cached as data.
"""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time

from filelock import FileLock, Timeout


class PublicProviderCache:
    def __init__(self, root, *, provider, credential='', daily_limit=25, spacing=1.1, ttl=3600):
        self.root = Path(root)
        self.account = sha256((provider + '\0' + credential).encode()).hexdigest()
        self.daily_limit, self.spacing, self.ttl = daily_limit, spacing, ttl

    async def get(self, request, fetch):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.root / (self.account + '.lock')), timeout=60, thread_local=False)
        deadline = time.monotonic() + 60
        while True:
            try:
                lock.acquire(timeout=0)
                break
            except Timeout:
                if time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(0.1)
        try:
            with closing(sqlite3.connect(self.root / (self.account + '.sqlite'))) as db:
                db.execute('CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, captured REAL, body TEXT)')
                db.execute('CREATE TABLE IF NOT EXISTS quota (id INTEGER PRIMARY KEY, day TEXT, count INTEGER, next_at REAL)')
                key = sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                now = time.time()
                row = db.execute('SELECT captured,body FROM responses WHERE key=?', (key,)).fetchone()
                if row and now - row[0] < self.ttl:
                    return {**json.loads(row[1]), 'cache_hit': True}
                day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
                quota = db.execute('SELECT day,count,next_at FROM quota WHERE id=1').fetchone()
                count = quota[1] if quota and quota[0] == day else 0
                if count >= self.daily_limit:
                    return {'status': 'provider_daily_limit', 'request_dispatched': False,
                            'detail': 'Local daily request allowance reached; reuse saved results. No retry made.'}
                delay = max(0, quota[2] - now) if quota else 0
                if delay > 2:
                    return {'status': 'provider_cooldown', 'request_dispatched': False,
                            'retry_after_seconds': int(delay) + 1}
                if delay:
                    await asyncio.sleep(delay)
                dispatched = time.time()
                db.execute('INSERT OR REPLACE INTO quota VALUES (1,?,?,?)',
                           (day, count + 1, dispatched + self.spacing))
                db.commit()
                result = await fetch()
                captured = datetime.now(timezone.utc).isoformat()
                result = {**result, 'captured_at': captured, 'cache_hit': False}
                if result.get('status') == 'ok':
                    db.execute('INSERT OR REPLACE INTO responses VALUES (?,?,?)',
                               (key, time.time(), json.dumps(result, ensure_ascii=False)))
                elif result.get('status') == 'provider_rate_limited':
                    db.execute('UPDATE quota SET next_at=? WHERE id=1', (time.time() + 60,))
                db.commit()
                return result
        finally:
            lock.release()
