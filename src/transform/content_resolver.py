"""Content title resolution from IDs."""

import logging
import sqlite3
from typing import Optional, Dict

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ContentResolver:
    """Resolves content IDs to titles."""
    
    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize content resolver.
        
        Args:
            conn: Database connection
        """
        self.conn = conn
        self._cache: Dict[int, str] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load all existing content titles into cache."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id_content, title FROM content_lookup")
        
        for row in cursor.fetchall():
            self._cache[row[0]] = row[1]
        
        logger.debug(f"Loaded {len(self._cache)} content titles into cache")
    
    def get_title(self, id_content: int) -> str:
        """
        Get title for a content ID.
        
        Args:
            id_content: Content ID
            
        Returns:
            Content title or fallback string
        """
        if id_content in self._cache:
            return self._cache[id_content]
        
        # Try to fetch from database
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT title FROM content_lookup WHERE id_content = ?
        """, (id_content,))
        
        row = cursor.fetchone()
        if row:
            title = row[0]
            self._cache[id_content] = title
            return title
        
        # Fallback: return placeholder
        # In production, this would call the Knowledge API
        fallback = f"Content {id_content}"
        logger.debug(f"No title found for content {id_content}, using fallback: {fallback}")
        
        return fallback
    
    def resolve_from_matchings(self, week_key: str):
        """
        Extract content titles from user question matchings data.
        This pre-populates the cache from API data.
        
        Args:
            week_key: Week key to process
        """
        cursor = self.conn.cursor()
        
        # Note: This assumes the API includes title information
        # If not available in matchings, we'd need to call Knowledge API
        # For now, we'll use the content ID as placeholder
        
        cursor.execute("""
            SELECT DISTINCT id_content FROM raw_uq_matchings
            WHERE week_key = ?
        """, (week_key,))
        
        content_ids = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(content_ids)} unique content IDs to resolve")
        
        # In a real implementation, we would:
        # 1. Check if title exists in raw API data
        # 2. If not, batch call Knowledge API: GET /v1/contents/{id}
        # 3. Cache results in content_lookup table
        
        # For now, we'll insert placeholder titles
        for id_content in content_ids:
            if id_content not in self._cache:
                # This is where we'd call Knowledge API
                title = f"Content {id_content}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO content_lookup (id_content, title, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (id_content, title))
                
                self._cache[id_content] = title
        
        self.conn.commit()
        
        logger.info(f"Resolved {len(content_ids)} content titles")
