from __future__ import annotations
import json, sqlite3, threading
from pathlib import Path

class RunStore:
    """Durable JSON-domain store supporting local SQLite or local PostgreSQL."""
    def __init__(self, path: Path, database_url: str = ""):
        self.path=path; self.url=database_url; self._lock=threading.RLock(); self._init()
    def _connect(self):
        if self.url.startswith("postgresql"):
            import psycopg
            c=psycopg.connect(self.url, autocommit=True)
            return c
        c=sqlite3.connect(self.path, timeout=30, check_same_thread=False); c.row_factory=sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON"); return c
    def _init(self):
        with self._connect() as c:
            if self.url.startswith("postgresql"):
                c.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), payload TEXT NOT NULL)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            else:
                c.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, payload TEXT NOT NULL)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
    def save(self, run):
        payload=run.model_dump_json()
        with self._lock, self._connect() as c:
            if self.url.startswith("postgresql"):
                c.execute("INSERT INTO runs(id,status,updated_at,payload) VALUES(%s,%s,NOW(),%s) ON CONFLICT(id) DO UPDATE SET status=EXCLUDED.status,updated_at=NOW(),payload=EXCLUDED.payload", (run.id,run.status.value,payload))
            else:
                c.execute("INSERT INTO runs(id,status,updated_at,payload) VALUES(?,?,CURRENT_TIMESTAMP,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated_at=CURRENT_TIMESTAMP,payload=excluded.payload", (run.id,run.status.value,payload))
    def get_payload(self,rid):
        with self._connect() as c:
            row=c.execute("SELECT payload FROM runs WHERE id=%s" if self.url.startswith("postgresql") else "SELECT payload FROM runs WHERE id=?",(rid,)).fetchone()
        if not row: raise KeyError(rid)
        return row[0]
    def list_payloads(self):
        with self._connect() as c:
            return [r[0] for r in c.execute("SELECT payload FROM runs ORDER BY updated_at DESC")]
    def delete(self,rid):
        with self._lock, self._connect() as c: c.execute("DELETE FROM runs WHERE id=%s" if self.url.startswith("postgresql") else "DELETE FROM runs WHERE id=?",(rid,))
