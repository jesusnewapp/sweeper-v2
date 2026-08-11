from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  source_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  sha256 TEXT,
  bytes INTEGER,
  local_path TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (source_id, item_id)
);
CREATE INDEX IF NOT EXISTS items_sha256 ON items(sha256);
"""


class State:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def status(self, source_id: str, item_id: str) -> Optional[str]:
        row = self.db.execute(
            "SELECT status FROM items WHERE source_id=? AND item_id=?", (source_id, item_id)
        ).fetchone()
        return row[0] if row else None

    def hash_owner(self, digest: str) -> Optional[str]:
        row = self.db.execute(
            "SELECT source_id || ':' || item_id FROM items WHERE sha256=? AND status='accepted' LIMIT 1",
            (digest,),
        ).fetchone()
        return row[0] if row else None

    def record(self, *, source_id: str, item_id: str, url: str, title: str, status: str,
               updated_at: str, reason: str = "", digest: Optional[str] = None,
               size: Optional[int] = None, local_path: Optional[str] = None) -> None:
        with self.db:
            self.db.execute(
                """INSERT INTO items(source_id,item_id,url,title,status,reason,sha256,bytes,local_path,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id,item_id) DO UPDATE SET
                     url=excluded.url,title=excluded.title,status=excluded.status,reason=excluded.reason,
                     sha256=excluded.sha256,bytes=excluded.bytes,local_path=excluded.local_path,
                     updated_at=excluded.updated_at""",
                (source_id, item_id, url, title, status, reason, digest, size, local_path, updated_at),
            )

    def counts(self) -> dict:
        return {row[0]: row[1] for row in self.db.execute("SELECT status, COUNT(*) FROM items GROUP BY status")}

    def accepted_count(self, source_id: str) -> int:
        row = self.db.execute("SELECT COUNT(*) FROM items WHERE source_id=? AND status='accepted'",
                              (source_id,)).fetchone()
        return int(row[0]) if row else 0

    def source_counts(self, source_id: str) -> dict:
        return {row[0]: int(row[1]) for row in self.db.execute(
            "SELECT status, COUNT(*) FROM items WHERE source_id=? GROUP BY status", (source_id,)
        )}

    def accepted_items(self) -> list[dict]:
        columns = ("source_id", "item_id", "url", "title", "sha256", "bytes", "local_path", "updated_at")
        rows = self.db.execute(
            "SELECT source_id,item_id,url,title,sha256,bytes,local_path,updated_at "
            "FROM items WHERE status='accepted' ORDER BY source_id,item_id"
        )
        return [dict(zip(columns, row)) for row in rows]
