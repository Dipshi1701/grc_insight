"""Repository for bulk database operations."""

import sqlite3
import logging
from typing import List, Dict, Any

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class Repository:
    """Handles bulk insert and query operations."""
    
    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize repository with a database connection.
        
        Args:
            conn: SQLite connection object
        """
        self.conn = conn
        self.cursor = conn.cursor()
    
    def bulk_insert_event_sources(self, sources: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert event sources.
        
        Args:
            sources: List of source dictionaries
            week_key: Week key for this data
        """
        if not sources:
            return
        
        data = [
            (src.get('id'), src.get('name'), src.get('is_excluded', False), week_key)
            for src in sources
        ]
        
        self.cursor.executemany("""
            INSERT OR REPLACE INTO event_sources (id, name, is_excluded, week_key)
            VALUES (?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} event sources")
    
    def bulk_insert_session_data_keys(self, keys: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert session data keys.
        
        Args:
            keys: List of key dictionaries
            week_key: Week key for this data
        """
        if not keys:
            return
        
        data = [
            (key.get('id'), key.get('key_name'), week_key)
            for key in keys
        ]
        
        self.cursor.executemany("""
            INSERT OR REPLACE INTO session_data_keys (id, key_name, week_key)
            VALUES (?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} session data keys")
    
    def bulk_insert_user_questions(self, questions: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert user questions.
        
        Args:
            questions: List of question dictionaries
            week_key: Week key for this data
        """
        if not questions:
            return
        
        data = [
            (
                q.get('event_id'),
                q.get('user_question'),
                q.get('date'),
                q.get('session_id'),
                q.get('log_id'),
                q.get('source'),
                week_key
            )
            for q in questions
        ]
        
        self.cursor.executemany("""
            INSERT OR REPLACE INTO raw_user_questions 
            (event_id, user_question, date, session_id, log_id, source, week_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} user questions")
    
    def bulk_insert_uq_matchings(self, matchings: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert user question matchings.
        
        Args:
            matchings: List of matching dictionaries
            week_key: Week key for this data
        """
        if not matchings:
            return
        
        data = [
            (
                m.get('event_id'),
                m.get('id_content'),
                m.get('weight'),
                m.get('is_external', False),
                week_key
            )
            for m in matchings
        ]
        
        self.cursor.executemany("""
            INSERT INTO raw_uq_matchings 
            (event_id, id_content, weight, is_external, week_key)
            VALUES (?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} question matchings")
    
    def bulk_insert_sessions(self, sessions: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert session events.
        
        Args:
            sessions: List of session event dictionaries
            week_key: Week key for this data
        """
        if not sessions:
            return
        
        data = [
            (
                s.get('event_id'),
                s.get('session_id'),
                s.get('key'),
                s.get('value'),
                s.get('user_question'),
                s.get('date'),
                s.get('log_id'),
                week_key
            )
            for s in sessions
        ]
        
        self.cursor.executemany("""
            INSERT INTO raw_sessions 
            (event_id, session_id, key, value, user_question, date, log_id, week_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} session events")
    
    def bulk_insert_clicks(self, clicks: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert click events.
        
        Args:
            clicks: List of click dictionaries
            week_key: Week key for this data
        """
        if not clicks:
            return
        
        data = [
            (
                c.get('event_id'),
                c.get('session_id'),
                c.get('id_content'),
                c.get('click_type'),
                c.get('log_id'),
                c.get('date'),
                week_key
            )
            for c in clicks
        ]
        
        self.cursor.executemany("""
            INSERT INTO raw_clicks 
            (event_id, session_id, id_content, click_type, log_id, date, week_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} click events")
    
    def bulk_insert_ratings(self, ratings: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert rating events.
        
        Args:
            ratings: List of rating dictionaries
            week_key: Week key for this data
        """
        if not ratings:
            return
        
        data = [
            (
                r.get('event_id'),
                r.get('session_id'),
                r.get('rating'),
                r.get('comment'),
                r.get('log_id'),
                r.get('date'),
                week_key
            )
            for r in ratings
        ]
        
        self.cursor.executemany("""
            INSERT INTO raw_ratings 
            (event_id, session_id, rating, comment, log_id, date, week_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} rating events")
    
    def bulk_insert_session_details(self, details: List[Dict[str, Any]], week_key: str):
        """
        Bulk insert aggregated session details.
        
        Args:
            details: List of session detail dictionaries
            week_key: Week key for this data
        """
        if not details:
            return
        
        data = [
            (
                d.get('session_id'),
                d.get('source'),
                d.get('duration'),
                d.get('environment'),
                d.get('date'),
                d.get('log_ids'),
                d.get('ids_contents'),
                d.get('data_keys'),
                week_key
            )
            for d in details
        ]
        
        self.cursor.executemany("""
            INSERT OR REPLACE INTO agg_session_details 
            (session_id, source, duration, environment, date, log_ids, ids_contents, data_keys, week_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        logger.info(f"Inserted {len(data)} session details")
    
    def upsert_content_lookup(self, id_content: int, title: str):
        """
        Insert or update a content title lookup.
        
        Args:
            id_content: Content ID
            title: Content title
        """
        self.cursor.execute("""
            INSERT OR REPLACE INTO content_lookup (id_content, title, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (id_content, title))
    
    def get_content_title(self, id_content: int) -> str | None:
        """
        Get content title by ID.
        
        Args:
            id_content: Content ID
            
        Returns:
            Content title or None if not found
        """
        self.cursor.execute("""
            SELECT title FROM content_lookup WHERE id_content = ?
        """, (id_content,))
        
        row = self.cursor.fetchone()
        return row[0] if row else None
    
    def get_excluded_sources(self, week_key: str) -> List[str]:
        """
        Get list of excluded source names for a week.
        
        Args:
            week_key: Week key
            
        Returns:
            List of excluded source names
        """
        self.cursor.execute("""
            SELECT name FROM event_sources 
            WHERE week_key = ? AND is_excluded = 1
        """, (week_key,))
        
        return [row[0] for row in self.cursor.fetchall()]
    
    def record_ingestion_run(self, week_key: str, status: str, start_time: str, 
                            end_time: str = None, record_counts: str = None, 
                            error_message: str = None):
        """
        Record an ingestion run.
        
        Args:
            week_key: Week key
            status: Status (started, completed, failed)
            start_time: Start timestamp
            end_time: End timestamp
            record_counts: JSON string of record counts
            error_message: Error message if failed
        """
        self.cursor.execute("""
            INSERT INTO ingestion_runs 
            (week_key, status, start_time, end_time, record_counts, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (week_key, status, start_time, end_time, record_counts, error_message))
        
        logger.info(f"Recorded ingestion run: {week_key} - {status}")
