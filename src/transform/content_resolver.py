"""Content title resolution from IDs."""

import logging
import sqlite3
from typing import Optional, Dict

from src.api.editor_client import InbentaEditorClient
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ContentResolver:
    """Resolves content IDs to titles."""
    
    def __init__(self, conn: sqlite3.Connection, editor_client: Optional[InbentaEditorClient] = None):
        """
        Initialize content resolver.
        
        Args:
            conn: Database connection
            editor_client: Optional Editor API client for fetching content details
        """
        self.conn = conn
        self.editor_client = editor_client
        self._cache: Dict[int, str] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load all existing content titles into cache."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id_content, title FROM content_lookup")
        
        for row in cursor.fetchall():
            self._cache[row[0]] = row[1]
        
        logger.debug(f"Loaded {len(self._cache)} content entries into cache")
    
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
        fallback = f"Content {id_content}"
        logger.debug(f"No title found for content {id_content}, using fallback: {fallback}")
        
        return fallback
    
    def resolve_from_matchings(self, week_key: str):
        """
        Fetch content titles from Editor API for user question matchings data.
        This pre-populates the cache with real content titles.
        
        Args:
            week_key: Week key to process
        """
        cursor = self.conn.cursor()
        
        # Get all unique content IDs for this week
        cursor.execute("""
            SELECT DISTINCT id_content FROM raw_uq_matchings
            WHERE week_key = ?
        """, (week_key,))
        
        content_ids = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(content_ids)} unique content IDs to resolve")
        
        # Check which IDs have placeholder titles (start with "Content ")
        content_ids_to_fetch = []
        for cid in content_ids:
            if cid in self._cache:
                # Check if it's a placeholder
                if self._cache[cid].startswith("Content "):
                    content_ids_to_fetch.append(cid)
            else:
                # Not in cache, need to fetch
                content_ids_to_fetch.append(cid)
        
        if not content_ids_to_fetch:
            logger.info("All content IDs already have real titles in cache")
            return
        
        logger.info(f"Need to fetch {len(content_ids_to_fetch)} content titles (new or placeholders)")
        
        # If Editor client is available, fetch real data
        if self.editor_client:
            logger.info("Fetching content titles from Editor API")
            content_data_map = self.editor_client.get_contents_batch(content_ids_to_fetch)
            
            # Store fetched content in database
            for id_content, content_data in content_data_map.items():
                title = content_data.get('title', f"Content {id_content}")
                
                cursor.execute("""
                    INSERT OR REPLACE INTO content_lookup (id_content, title, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (id_content, title))
                
                self._cache[id_content] = title
                
                logger.debug(f"Cached content {id_content}: {title}")
            
            # For content that wasn't found, insert placeholder
            fetched_ids = set(content_data_map.keys())
            not_found_ids = set(content_ids_to_fetch) - fetched_ids
            
            for id_content in not_found_ids:
                title = f"Content {id_content} (not found)"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO content_lookup (id_content, title, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (id_content, title))
                
                self._cache[id_content] = title
                
                logger.warning(f"Content {id_content} not found in Editor API, using placeholder")
        
        else:
            # No Editor client - use placeholders
            logger.warning("No Editor API client available, using placeholder titles")
            
            for id_content in content_ids_to_fetch:
                title = f"Content {id_content}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO content_lookup (id_content, title, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (id_content, title))
                
                self._cache[id_content] = title
        
        self.conn.commit()
        
        logger.info(f"Resolved {len(content_ids)} content entries")
