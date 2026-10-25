"""Durable local catalog. Media files are never moved or deleted here."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "catalog.sqlite3")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tapes (id TEXT PRIMARY KEY, data TEXT NOT NULL, cover BLOB);
            CREATE TABLE IF NOT EXISTS queue (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        """)
        self.db.commit()
        # An interrupted transfer is offered again, never auto-started at launch.
        for item in self.queue():
            if item["status"] not in ("pending", "complete", "failed", "cancelled"):
                self.update_queue(item["id"], status="pending", error="Interrupted; ready to retry")

    def setting(self, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def add_tape(self, data, cover=b""):
        data = dict(data, id=uuid.uuid4().hex, created_at=now())
        with self.db:
            self.db.execute("INSERT INTO tapes VALUES (?,?,?)", (data["id"], json.dumps(data, ensure_ascii=False), cover))
        return data

    def tapes(self, query=""):
        rows = [json.loads(row[0]) for row in self.db.execute("SELECT data FROM tapes ORDER BY rowid DESC")]
        key = query.strip().casefold()
        return [row for row in rows if not key or key in (row.get("title", "") + " " + row.get("creator", "")).casefold()]

    def tape(self, key):
        row = self.db.execute("SELECT data FROM tapes WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def cover(self, key):
        row = self.db.execute("SELECT cover FROM tapes WHERE id=?", (key,)).fetchone()
        return bytes(row[0] or b"") if row else b""

    def update_tape(self, key, **values):
        item = self.tape(key)
        if item:
            item.update(values)
            with self.db:
                self.db.execute("UPDATE tapes SET data=? WHERE id=?", (json.dumps(item, ensure_ascii=False), key))

    def add_queue(self, urls, profile):
        with self.db:
            for url in urls:
                item = dict(id=uuid.uuid4().hex, url=url, title=url, profile=profile,
                            status="pending", error="", created_at=now())
                self.db.execute("INSERT INTO queue VALUES (?,?)", (item["id"], json.dumps(item)))

    def queue(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM queue ORDER BY rowid")]

    def update_queue(self, key, **values):
        row = self.db.execute("SELECT data FROM queue WHERE id=?", (key,)).fetchone()
        if row:
            item = json.loads(row[0]); item.update(values)
            with self.db:
                self.db.execute("UPDATE queue SET data=? WHERE id=?", (json.dumps(item, ensure_ascii=False), key))

    def close(self):
        self.db.close()
