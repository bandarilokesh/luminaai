"""SQLite store for paper metadata, QA history, summary cache, extracted tables, audits and activity.

Vectors live in Qdrant; this database only keeps application records.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT DEFAULT '',
    abstract TEXT DEFAULT '',
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_message TEXT,
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS qa_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_ids TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    citations TEXT NOT NULL,
    retrieval_score REAL DEFAULT 0,
    latency_sec REAL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    summary_type TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (paper_id, summary_type)
);
CREATE TABLE IF NOT EXISTS paper_tables (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    table_index INTEGER NOT NULL,
    page INTEGER NOT NULL,
    caption TEXT NOT NULL,
    markdown TEXT NOT NULL,
    json_data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paper_tables_paper ON paper_tables(paper_id, table_index);
CREATE TABLE IF NOT EXISTS reproducibility_audits (
    paper_id TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    grade TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    paper_id TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- papers ---
    def add_paper(self, paper_id: str, file_name: str, file_path: Path, file_size: int) -> dict[str, Any]:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO papers (id, title, file_name, file_path, file_size, status, uploaded_at) "
                "VALUES (?, ?, ?, ?, ?, 'uploaded', ?)",
                (paper_id, file_name, file_name, str(file_path), file_size, _now()),
            )
        self.log_activity("upload", f"Uploaded {file_name}", paper_id)
        return self.get_paper(paper_id)

    def update_paper(self, paper_id: str, **fields: Any) -> None:
        if not fields:
            return
        columns = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as conn:
            conn.execute(f"UPDATE papers SET {columns} WHERE id = ?", (*fields.values(), paper_id))

    def get_paper(self, paper_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return dict(row) if row else None

    def list_papers(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM papers ORDER BY uploaded_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_paper(self, paper_id: str) -> bool:
        with self._conn() as conn:
            deleted = conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,)).rowcount
            conn.execute("DELETE FROM activity WHERE paper_id = ?", (paper_id,))
        return deleted > 0

    # --- QA history ---
    def add_qa_log(self, paper_ids: list[str], question: str, result: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO qa_logs (paper_ids, question, answer, citations, retrieval_score, latency_sec, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    json.dumps(paper_ids),
                    question,
                    result.get("answer", ""),
                    json.dumps(result.get("citations", [])),
                    result.get("retrieval_score", 0.0),
                    result.get("latency_sec", 0.0),
                    _now(),
                ),
            )
        self.log_activity("qa", f"Asked: {question[:80]}", paper_ids[0] if len(paper_ids) == 1 else None)

    def recent_questions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, question, created_at AS timestamp FROM qa_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- summary cache ---
    def get_summary(self, paper_id: str, summary_type: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT summary_text FROM summaries WHERE paper_id = ? AND summary_type = ?", (paper_id, summary_type)
            ).fetchone()
        return row["summary_text"] if row else None

    def save_summary(self, paper_id: str, summary_type: str, text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO summaries (paper_id, summary_type, summary_text, created_at) VALUES (?, ?, ?, ?)",
                (paper_id, summary_type, text, _now()),
            )

    # --- extracted tables (Stream B) ---
    def replace_paper_tables(self, paper_id: str, tables: list[Any]) -> int:
        """Store a paper's ExtractedTable objects, replacing any from a previous indexing run."""
        now = _now()
        with self._conn() as conn:
            conn.execute("DELETE FROM paper_tables WHERE paper_id = ?", (paper_id,))
            conn.executemany(
                "INSERT INTO paper_tables (id, paper_id, table_index, page, caption, markdown, json_data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (f"{paper_id}:{t.table_index}", paper_id, t.table_index, t.page, t.caption, t.markdown,
                     json.dumps(t.json_data), now)
                    for t in tables
                ],
            )
        return len(tables)

    def get_paper_tables(self, paper_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT table_index, page, caption, markdown, json_data FROM paper_tables WHERE paper_id = ? ORDER BY table_index",
                (paper_id,),
            ).fetchall()
        tables = []
        for r in rows:
            data = json.loads(r["json_data"])
            tables.append({
                "table_index": r["table_index"], "page": r["page"], "caption": r["caption"], "markdown": r["markdown"],
                "headers": data.get("headers", []), "rows": data.get("rows", []),
            })
        return tables

    # --- reproducibility audits ---
    def get_audit(self, paper_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT report_json FROM reproducibility_audits WHERE paper_id = ?", (paper_id,)).fetchone()
        return json.loads(row["report_json"]) if row else None

    def save_audit(self, paper_id: str, report: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reproducibility_audits (paper_id, overall_score, grade, report_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (paper_id, report["overall_score"], report["grade"], json.dumps(report), report.get("created_at") or _now()),
            )

    def delete_audit(self, paper_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM reproducibility_audits WHERE paper_id = ?", (paper_id,))

    # --- activity & stats ---
    def log_activity(self, event_type: str, description: str, paper_id: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO activity (event_type, description, paper_id, created_at) VALUES (?, ?, ?, ?)",
                (event_type, description, paper_id, _now()),
            )

    def recent_activity(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT event_type, description, paper_id, created_at AS timestamp FROM activity ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, int]:
        with self._conn() as conn:
            def count(sql: str) -> int:
                return conn.execute(sql).fetchone()[0]

            return {
                "total_papers": count("SELECT COUNT(*) FROM papers"),
                "questions_asked": count("SELECT COUNT(*) FROM qa_logs"),
                "summaries_generated": count("SELECT COUNT(*) FROM activity WHERE event_type = 'summary'"),
                "study_sessions": count("SELECT COUNT(*) FROM activity WHERE event_type IN ('quiz', 'flashcards')"),
            }


db = Database(settings.DATABASE_PATH)
