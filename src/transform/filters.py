"""Filtering logic for sources and data."""

import logging
from typing import List
import sqlite3

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SourceFilter:
    """Handles source filtering logic."""
    
    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize source filter.
        
        Args:
            conn: Database connection
        """
        self.conn = conn
    
    def get_allowed_sources(self, week_key: str) -> List[str]:
        """
        Get list of allowed (non-excluded) source names.
        
        Args:
            week_key: Week key
            
        Returns:
            List of allowed source names
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM event_sources
            WHERE week_key = ? AND is_excluded = 0
        """, (week_key,))
        
        sources = [row[0] for row in cursor.fetchall()]
        logger.debug(f"Found {len(sources)} allowed sources for {week_key}")
        
        return sources
    
    def get_excluded_sources(self, week_key: str) -> List[str]:
        """
        Get list of excluded source names.
        
        Args:
            week_key: Week key
            
        Returns:
            List of excluded source names
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM event_sources
            WHERE week_key = ? AND is_excluded = 1
        """, (week_key,))
        
        sources = [row[0] for row in cursor.fetchall()]
        logger.debug(f"Found {len(sources)} excluded sources for {week_key}")
        
        return sources
