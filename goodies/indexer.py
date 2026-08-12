#!/usr/bin/env python3
"""Standalone staged/live JSONL indexer; intentionally separate from Sweeper."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  scope TEXT NOT NULL CHECK(scope IN ('staged','live')),
  record_id TEXT NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL,
  body TEXT NOT NULL, source_json TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  PRIMARY KEY(scope,record_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  scope UNINDEXED, record_id UNINDEXED, title, category, body,
  tokenize='unicode61 remove_diacritics 2'
);
"""


def text(value) -> str:
    if isinstance(value, list): return " ".join(map(str, value))
    if isinstance(value, dict): return " ".join(f"{key} {text(item)}" for key, item in value.items())
    return str(value or "")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path)); db.executescript(SCHEMA); return db


def index_jsonl(database: Path, source: Path, scope: str, categories: set[str] | None = None) -> dict:
    if scope not in {"staged", "live"}: raise ValueError("scope must be staged or live")
    db = connect(database); indexed = unchanged = rejected = 0
    try:
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip(): continue
            try: record = json.loads(line)
            except ValueError: rejected += 1; continue
            ident = str(record.get("id") or "").strip(); title = str(record.get("title") or "").strip()
            category = str(record.get("category") or "Uncategorized").strip()
            if not ident or not title or (categories is not None and category not in categories):
                rejected += 1; continue
            canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            old = db.execute("SELECT source_sha256 FROM records WHERE scope=? AND record_id=?",
                             (scope, ident)).fetchone()
            if old and old[0] == digest: unchanged += 1; continue
            body = " ".join([text(record.get("subjects")), text(record.get("keywords")),
                             text(record.get("description")), text(record.get("text")),
                             text(record.get("metadata"))])
            with db:
                db.execute("DELETE FROM records_fts WHERE scope=? AND record_id=?", (scope, ident))
                db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?,?)",
                    (scope, ident, title, category, body, canonical, digest))
                db.execute("INSERT INTO records_fts(scope,record_id,title,category,body) VALUES(?,?,?,?,?)",
                    (scope, ident, title, category, body))
            indexed += 1
        return {"scope": scope, "indexed": indexed, "unchanged": unchanged,
                "rejected": rejected, "database": str(database)}
    finally: db.close()


def search(database: Path, query: str, scope: str = "all", category: str = "", limit: int = 20) -> dict:
    if scope not in {"staged", "live", "all"}: raise ValueError("scope must be staged, live, or all")
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens: return {"query": query, "scope": scope, "category": category or None,
                           "count": 0, "results": []}
    safe_query = " AND ".join(f'"{token}"' for token in tokens[:32])
    db = connect(database)
    try:
        clauses = ["records_fts MATCH ?"]; values = [safe_query]
        if scope != "all": clauses.append("scope=?"); values.append(scope)
        if category: clauses.append("category=?"); values.append(category)
        values.append(max(1, min(1000, limit)))
        rows = db.execute("SELECT scope,record_id,title,category,bm25(records_fts) AS rank "
            f"FROM records_fts WHERE {' AND '.join(clauses)} ORDER BY rank,scope,record_id LIMIT ?", values)
        results = [{"scope": row[0], "id": row[1], "title": row[2],
                    "category": row[3], "rank": row[4]} for row in rows]
        return {"query": query, "scope": scope, "category": category or None,
                "count": len(results), "results": results}
    finally: db.close()


def load_categories(path: Path | None) -> set[str] | None:
    if path is None: return None
    value = json.loads(path.read_text(encoding="utf-8"))
    categories = value.get("categories") if isinstance(value, dict) else value
    if not isinstance(categories, list) or not all(str(item).strip() for item in categories):
        raise ValueError("category file must contain a non-empty string list")
    return {str(item).strip() for item in categories}


def export_json(database: Path, output: Path) -> dict:
    db = connect(database)
    try:
        rows = db.execute("SELECT scope,record_id,title,category,body FROM records "
                          "ORDER BY scope,category,title,record_id")
        records = [{"scope": row[0], "id": row[1], "title": row[2],
                    "category": row[3], "searchText": row[4]} for row in rows]
    finally: db.close()
    payload = {"schemaVersion": 1, "recordCount": len(records),
               "categories": sorted({row["category"] for row in records}), "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                         encoding="utf-8")
    temporary.replace(output)
    return {"output": str(output), "recordCount": len(records),
            "categoryCount": len(payload["categories"])}


def main() -> int:
    parser = argparse.ArgumentParser(prog="goodies-index")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build"); build.add_argument("--database", type=Path, required=True)
    build.add_argument("--input", type=Path, required=True); build.add_argument("--scope", choices=("staged","live"), required=True)
    build.add_argument("--categories", type=Path)
    find = sub.add_parser("search"); find.add_argument("--database", type=Path, required=True)
    find.add_argument("--query", required=True); find.add_argument("--scope", choices=("staged","live","all"), default="all")
    find.add_argument("--category", default=""); find.add_argument("--limit", type=int, default=20)
    export = sub.add_parser("export"); export.add_argument("--database", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = index_jsonl(args.database.resolve(), args.input.resolve(), args.scope,
                             load_categories(args.categories.resolve() if args.categories else None))
    elif args.command == "search":
        result = search(args.database.resolve(), args.query, args.scope, args.category, args.limit)
    else: result = export_json(args.database.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
