import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from config.settings import settings
from utils.logger import logger

class DatabaseHelper:
    """Helper class for SQLite database interactions."""
    def __init__(self, db_path: Path = settings.DATABASE_PATH):
        self.db_path = db_path
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database with row factory enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        """Initialize the SQLite database schema if tables do not exist."""
        logger.info(f"Initializing database at: {self.db_path}")
        with self._get_connection() as conn:
            # Papers Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors TEXT,
                    abstract TEXT,
                    keywords TEXT,
                    doi TEXT,
                    publication_year INTEGER,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL CHECK(status IN ('uploaded', 'indexing', 'completed', 'failed')),
                    error_message TEXT
                );
            """)
            
            # Search History Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Summaries Cache Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT NOT NULL,
                    summary_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE,
                    UNIQUE(paper_id, summary_type)
                );
            """)

            # QA History Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations TEXT,  -- JSON string of references/citations
                    confidence_score REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE SET NULL
                );
            """)
            
            conn.commit()
            logger.info("Database schemas verified/created successfully.")

    # Papers Database CRUD Operations
    def add_paper(self, paper_metadata: Dict[str, Any]) -> str:
        """Insert a new paper record into the database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO papers 
                (id, title, authors, abstract, keywords, doi, publication_year, file_path, file_size, status)
                VALUES (:id, :title, :authors, :abstract, :keywords, :doi, :publication_year, :file_path, :file_size, :status)
                """,
                paper_metadata
            )
            conn.commit()
            return paper_metadata["id"]

    def update_paper_status(self, paper_id: str, status: str, error_message: Optional[str] = None):
        """Update indexing progress status of a paper."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE papers SET status = ?, error_message = ? WHERE id = ?",
                (status, error_message, paper_id)
            )
            conn.commit()

    def update_paper_metadata(self, paper_id: str, title: str, authors: Optional[str], abstract: Optional[str], keywords: Optional[str], doi: Optional[str], pub_year: Optional[int]):
        """Update extracted paper metadata."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE papers SET 
                title = ?, authors = ?, abstract = ?, keywords = ?, doi = ?, publication_year = ?
                WHERE id = ?
                """,
                (title, authors, abstract, keywords, doi, pub_year, paper_id)
            )
            conn.commit()

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single paper by its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_papers(self) -> List[Dict[str, Any]]:
        """Retrieve all papers in the library."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM papers ORDER BY uploaded_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper record from the database."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
            conn.commit()
            return cursor.rowcount > 0

    # Search History
    def add_search_history(self, query: str):
        """Log a search query to search history."""
        with self._get_connection() as conn:
            conn.execute("INSERT INTO search_history (query) VALUES (?)", (query,))
            conn.commit()

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent search queries."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM search_history ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_search_history(self):
        """Clear all search history."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM search_history")
            conn.commit()

    # Summaries Cache Operations
    def add_summary_cache(self, paper_id: str, summary_type: str, content: str):
        """Cache a generated summary."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO summaries_cache (paper_id, summary_type, content)
                VALUES (?, ?, ?)
                """,
                (paper_id, summary_type, content)
            )
            conn.commit()

    def get_summary_cache(self, paper_id: str, summary_type: str) -> Optional[str]:
        """Get a cached summary if it exists."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT content FROM summaries_cache WHERE paper_id = ? AND summary_type = ?",
                (paper_id, summary_type)
            )
            row = cursor.fetchone()
            return row["content"] if row else None

    # QA History Operations
    def add_qa_log(self, paper_id: Optional[str], question: str, answer: str, citations: List[Dict[str, Any]], confidence_score: float):
        """Log a QA interaction."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO qa_history (paper_id, question, answer, citations, confidence_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (paper_id, question, answer, json.dumps(citations), confidence_score)
            )
            conn.commit()

    def get_qa_history(self, paper_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve QA history log."""
        with self._get_connection() as conn:
            if paper_id:
                cursor = conn.execute(
                    "SELECT * FROM qa_history WHERE paper_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (paper_id, limit)
                )
            else:
                cursor = conn.execute("SELECT * FROM qa_history ORDER BY timestamp DESC LIMIT ?", (limit,))
            
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                if d["citations"]:
                    d["citations"] = json.loads(d["citations"])
                results.append(d)
            return results

    # Dashboard Stats & Activity
    def get_dashboard_stats(self) -> Dict[str, int]:
        """Get aggregated counts for the dashboard."""
        with self._get_connection() as conn:
            total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            questions_asked = conn.execute("SELECT COUNT(*) FROM qa_history").fetchone()[0]
            summaries_generated = conn.execute("SELECT COUNT(*) FROM summaries_cache").fetchone()[0]
            # study_sessions = unique QA sessions (grouped by date+paper)
            study_sessions = conn.execute(
                "SELECT COUNT(DISTINCT DATE(timestamp)) FROM qa_history"
            ).fetchone()[0]
            return {
                "total_papers": total_papers,
                "questions_asked": questions_asked,
                "summaries_generated": summaries_generated,
                "study_sessions": study_sessions
            }

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity across uploads, QA, and summaries."""
        with self._get_connection() as conn:
            # Union of recent events from different tables
            cursor = conn.execute("""
                SELECT 'upload' as event_type, 
                       'Uploaded "' || title || '"' as description,
                       uploaded_at as timestamp,
                       id as paper_id
                FROM papers
                UNION ALL
                SELECT 'qa' as event_type,
                       'Asked: "' || SUBSTR(question, 1, 60) || CASE WHEN LENGTH(question) > 60 THEN '...' ELSE '' END || '"' as description,
                       timestamp,
                       paper_id
                FROM qa_history
                UNION ALL
                SELECT 'summary' as event_type,
                       'Generated ' || summary_type || ' summary' as description,
                       created_at as timestamp,
                       paper_id
                FROM summaries_cache
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

# Singleton database helper
db = DatabaseHelper()
