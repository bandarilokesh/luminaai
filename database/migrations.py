import sqlite3
from pathlib import Path
from config.settings import settings
from utils.logger import logger

def run_migrations(db_path: Path = settings.DATABASE_PATH):
    """Run schema migrations for Phase 2 and 3."""
    logger.info(f"Running database migrations on {db_path}...")
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Update qa_history table with new verification columns
        cursor.execute("PRAGMA table_info(qa_history)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "faithfulness_score" not in columns:
            cursor.execute("ALTER TABLE qa_history ADD COLUMN faithfulness_score REAL")
            logger.info("Added 'faithfulness_score' to 'qa_history'")
            
        if "verification_json" not in columns:
            cursor.execute("ALTER TABLE qa_history ADD COLUMN verification_json TEXT")
            logger.info("Added 'verification_json' to 'qa_history'")
            
        # 2. Create chunks table for hierarchical chunking (Phase 3 prep)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                paper_id TEXT,
                level INTEGER,
                parent_chunk_id TEXT,
                text_content TEXT,
                page INTEGER,
                section TEXT,
                subsection TEXT,
                heading TEXT,
                element_type TEXT,
                tokens INTEGER,
                reading_order INTEGER,
                bbox_json TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE
            )
        """)
        
        # 3. Create structured_knowledge table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS structured_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT,
                entity_type TEXT,
                entity_name TEXT,
                entity_value TEXT,
                metadata_json TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE
            )
        """)
        
        # 4. Create knowledge_graph tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_type TEXT,
                node_name TEXT,
                paper_id TEXT,
                attributes_json TEXT,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_node_id INTEGER,
                target_node_id INTEGER,
                edge_type TEXT,
                metadata_json TEXT,
                FOREIGN KEY (source_node_id) REFERENCES knowledge_graph_nodes (id) ON DELETE CASCADE,
                FOREIGN KEY (target_node_id) REFERENCES knowledge_graph_nodes (id) ON DELETE CASCADE
            )
        """)
        
        # 5. Create annotations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT,
                chunk_id TEXT,
                note_text TEXT,
                highlight_text TEXT,
                tag TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE,
                FOREIGN KEY (chunk_id) REFERENCES chunks (chunk_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        logger.info("Database migrations completed successfully.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migrations()
