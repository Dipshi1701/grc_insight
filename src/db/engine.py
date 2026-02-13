"""Database engine and connection management."""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from src.db.schema import ALL_TABLES, CREATE_INDEXES
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseEngine:
    """Manages SQLite database connection and schema."""
    
    def __init__(self, db_path: str):
        """
        Initialize database engine.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """Create database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Enable WAL mode for better concurrency on Windows
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Set busy timeout to 30 seconds
        conn.execute("PRAGMA busy_timeout=30000")
        
        return conn
    
    @contextmanager
    def get_connection_context(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.
        Automatically commits on success, rolls back on error.
        
        Yields:
            SQLite connection object
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed, rolling back: {e}")
            raise
        finally:
            conn.close()
    
    def initialize_schema(self):
        """Create all tables and indexes if they don't exist."""
        logger.info("Initializing database schema")
        
        with self.get_connection_context() as conn:
            cursor = conn.cursor()
            
            # Create tables
            for i, create_stmt in enumerate(ALL_TABLES, 1):
                logger.debug(f"Creating table {i}/{len(ALL_TABLES)}")
                cursor.execute(create_stmt)
            
            # Create indexes
            for idx_stmt in CREATE_INDEXES:
                cursor.execute(idx_stmt)
            
            logger.info(f"Schema initialized: {len(ALL_TABLES)} tables, {len(CREATE_INDEXES)} indexes")
    
    def clear_week_data(self, week_key: str):
        """
        Delete all data for a specific week (for idempotent re-ingestion).
        
        Args:
            week_key: Week key to clear (e.g., '2026-W04')
        """
        logger.info(f"Clearing data for week {week_key}")
        
        tables_with_week_key = [
            "event_sources",
            "session_data_keys",
            "raw_user_questions",
            "raw_uq_matchings",
            "raw_sessions",
            "raw_clicks",
            "raw_ratings",
            "agg_session_details",
        ]
        
        with self.get_connection_context() as conn:
            cursor = conn.cursor()
            
            for table in tables_with_week_key:
                cursor.execute(f"DELETE FROM {table} WHERE week_key = ?", (week_key,))
                deleted = cursor.rowcount
                logger.debug(f"Deleted {deleted} rows from {table}")
        
        logger.info(f"Week {week_key} data cleared")
    
    def get_available_weeks(self) -> list[str]:
        """
        Get list of available week keys in the database.
        
        Returns:
            List of week keys (e.g., ['2026-W04', '2026-W05'])
        """
        with self.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT week_key 
                FROM agg_session_details 
                ORDER BY week_key DESC
            """)
            return [row[0] for row in cursor.fetchall()]
