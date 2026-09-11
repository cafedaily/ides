"""SQLite。一个文件，没有服务要起，拷走就是全部数据。"""
import json
import os
import sqlite3

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS ideas(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, seed TEXT DEFAULT '',
  now TEXT DEFAULT '', created INTEGER NOT NULL, updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS grew(
  rowid_ INTEGER PRIMARY KEY AUTOINCREMENT,
  idea_id TEXT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, q TEXT NOT NULL, a TEXT NOT NULL,
  at INTEGER NOT NULL, by TEXT DEFAULT '', with_id TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS grew_idea ON grew(idea_id);
CREATE TABLE IF NOT EXISTS sparks(id TEXT PRIMARY KEY, text TEXT NOT NULL, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cold(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, why TEXT NOT NULL, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_terms(
  doc_id TEXT NOT NULL, term TEXT NOT NULL, w REAL NOT NULL,
  tf REAL NOT NULL, df INTEGER NOT NULL, dims TEXT NOT NULL,
  PRIMARY KEY(doc_id, term));
CREATE INDEX IF NOT EXISTS dt_term ON doc_terms(term);
"""


def connect(path):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    return c


def kv_get(c, k, default=None):
    r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def kv_set(c, k, v):
    c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
              (k, json.dumps(v, ensure_ascii=False)))
