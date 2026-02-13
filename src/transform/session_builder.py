"""Core transformation logic to build hierarchical session report rows."""

import logging
import sqlite3
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from src.transform.filters import SourceFilter
from src.transform.content_resolver import ContentResolver
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SessionBuilder:
    """Builds hierarchical session report rows from raw database data."""
    
    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize session builder.
        
        Args:
            conn: Database connection
        """
        self.conn = conn
        self.source_filter = SourceFilter(conn)
        self.content_resolver = ContentResolver(conn)
    
    def build_report_rows(self, week_key: str) -> List[Dict[str, Any]]:
        """
        Build complete hierarchical report structure.
        
        Links user_questions to sessions via event_id → log_ids matching.
        
        Args:
            week_key: Week key to process
            
        Returns:
            List of report row dictionaries with all 12 columns
        """
        import json
        from datetime import datetime
        
        logger.info(f"Building report rows for {week_key}")
        
        # Resolve content titles first
        self.content_resolver.resolve_from_matchings(week_key)
        
        # Get all user questions
        user_questions = self._get_all_user_questions(week_key)
        logger.info(f"Found {len(user_questions)} user questions")
        
        # Get all sessions with log_ids
        sessions = self._get_sessions_with_log_ids(week_key)
        logger.info(f"Found {len(sessions)} sessions")
        
        # Link questions to sessions via event_id → log_ids
        session_questions_map = self._link_questions_to_sessions(user_questions, sessions)
        
        all_rows = []
        
        for session in sessions:
            session_id = session['session_id']
            source = session['source']
            session_date = session['date']
            
            # Get questions for this session
            questions_in_session = session_questions_map.get(session_id, [])
            
            # Skip sessions with no questions
            if not questions_in_session:
                continue
            
            # Parse date/time for session row
            date_str, time_str = self._parse_datetime(session_date)
            
            # Add session row (count = number of questions)
            all_rows.append({
                'row_label': session_id,
                'count': len(questions_in_session),
                'label_type': 'Session',
                'source': source,
                'date': date_str,
                'time': time_str
            })
            
            # Group identical questions and count them
            question_groups = self._group_duplicate_questions(questions_in_session)
            
            for question_text, question_count, event_ids in question_groups:
                # Add question row
                all_rows.append({
                    'row_label': question_text,
                    'count': question_count,
                    'label_type': 'Question',
                    'source': ''
                })
                
                # Get answers (formatted matchings) for this question
                answer_text = self._format_matchings_for_question(event_ids, week_key)
                
                # Add answer row
                all_rows.append({
                    'row_label': answer_text,
                    'count': question_count,
                    'label_type': 'Answer',
                    'source': ''
                })
                
                # Get rating for this question
                rating_text = self._get_rating_for_questions(event_ids, week_key)
                
                # Add rating row (always add, even if empty)
                all_rows.append({
                    'row_label': rating_text,
                    'count': question_count,
                    'label_type': 'Rating',
                    'source': ''
                })
        
        logger.info(f"Built {len(all_rows)} total report rows")
        
        return all_rows
    
    def _get_all_user_questions(self, week_key: str) -> List[Dict[str, Any]]:
        """
        Get all user questions for the week.
        
        Args:
            week_key: Week key
            
        Returns:
            List of user question dictionaries
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT event_id, user_question, date
            FROM raw_user_questions
            WHERE week_key = ?
            ORDER BY date ASC
        """, (week_key,))
        
        questions = []
        for row in cursor.fetchall():
            questions.append({
                'event_id': row[0],
                'user_question': row[1],
                'date': row[2]
            })
        
        return questions
    
    def _get_sessions_with_log_ids(self, week_key: str) -> List[Dict[str, Any]]:
        """
        Get all sessions with their log_ids arrays, excluding filtered sources.
        
        Args:
            week_key: Week key
            
        Returns:
            List of session dictionaries with log_ids
        """
        cursor = self.conn.cursor()
        
        # Get excluded sources
        excluded_sources = self.source_filter.get_excluded_sources(week_key)
        
        # Build query with exclusion
        placeholders = ','.join('?' * len(excluded_sources)) if excluded_sources else ''
        
        if excluded_sources:
            query = f"""
                SELECT session_id, source, date, log_ids, ids_contents
                FROM agg_session_details
                WHERE week_key = ? AND source NOT IN ({placeholders})
                ORDER BY date, session_id
            """
            cursor.execute(query, (week_key, *excluded_sources))
        else:
            query = """
                SELECT session_id, source, date, log_ids, ids_contents
                FROM agg_session_details
                WHERE week_key = ?
                ORDER BY date, session_id
            """
            cursor.execute(query, (week_key,))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'source': row[1],
                'date': row[2],
                'log_ids': row[3],
                'ids_contents': row[4]
            })
        
        return sessions
    
    def _link_questions_to_sessions(
        self, 
        user_questions: List[Dict[str, Any]], 
        sessions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Link user questions to sessions via event_id → log_ids matching.
        
        Args:
            user_questions: List of user question dictionaries
            sessions: List of session dictionaries with log_ids
            
        Returns:
            Dictionary mapping session_id to list of questions
        """
        import json
        
        session_map = defaultdict(list)
        
        for question in user_questions:
            event_id = question['event_id']
            
            # Find the session that contains this event_id in its log_ids
            for session in sessions:
                log_ids_json = session.get('log_ids')
                
                if not log_ids_json:
                    continue
                
                try:
                    log_ids = json.loads(log_ids_json)
                    
                    # Check if event_id is in the log_ids array
                    if event_id in log_ids:
                        session_map[session['session_id']].append(question)
                        break  # Found the session, move to next question
                        
                except (json.JSONDecodeError, TypeError):
                    continue
        
        return session_map
    
    def _group_duplicate_questions(
        self, 
        questions: List[Dict[str, Any]]
    ) -> List[Tuple[str, int, List[str]]]:
        """
        Group consecutive identical questions together.
        
        Args:
            questions: List of question dictionaries
            
        Returns:
            List of (question_text, count, [event_ids]) tuples
        """
        if not questions:
            return []
        
        grouped = []
        current_question = None
        current_count = 0
        current_event_ids = []
        
        for question in questions:
            question_text = question['user_question']
            event_id = question['event_id']
            
            if question_text == current_question:
                # Same question, increment count
                current_count += 1
                current_event_ids.append(event_id)
            else:
                # New question, save previous
                if current_question is not None:
                    grouped.append((current_question, current_count, current_event_ids))
                
                # Start new group
                current_question = question_text
                current_count = 1
                current_event_ids = [event_id]
        
        # Don't forget the last group
        if current_question is not None:
            grouped.append((current_question, current_count, current_event_ids))
        
        return grouped
    
    def _parse_datetime(self, datetime_str: str) -> Tuple[str, str]:
        """
        Parse ISO datetime into separate date and time strings.
        
        Args:
            datetime_str: ISO format datetime string
            
        Returns:
            Tuple of (date_str, time_str)
        """
        from datetime import datetime
        
        if not datetime_str:
            return '', ''
        
        try:
            # Parse ISO format: 2026-01-26T13:32:47+00:00
            dt = datetime.fromisoformat(datetime_str.replace('+00:00', ''))
            
            # Format as MM/DD/YYYY and HH:MM:SS
            date_str = dt.strftime('%m/%d/%Y')
            time_str = dt.strftime('%H:%M:%S')
            
            return date_str, time_str
        except (ValueError, AttributeError):
            return '', ''
    
    def _format_matchings_for_question(self, event_ids: List[str], week_key: str) -> str:
        """
        Format matchings for a question into the Answer row text.
        
        Args:
            event_ids: List of event IDs (from user_questions) for this question
            week_key: Week key
            
        Returns:
            Formatted answer string with all matchings
        """
        if not event_ids:
            return "0"
        
        cursor = self.conn.cursor()
        
        # Get matchings for these event IDs
        placeholders = ','.join('?' * len(event_ids))
        cursor.execute(f"""
            SELECT id_content, is_external
            FROM raw_uq_matchings
            WHERE event_id IN ({placeholders}) AND week_key = ?
            ORDER BY weight DESC
        """, (*event_ids, week_key))
        
        matchings = cursor.fetchall()
        
        # If no matchings, return "0"
        if not matchings:
            return "0"
        
        # Format each matching as bullet points
        formatted_lines = []
        
        for id_content, is_external in matchings:
            # Get content title
            title = self.content_resolver.get_title(id_content)
            
            # Count clicks for this content (check if any event_id had a click)
            click_count = self._get_click_count_for_content(event_ids, id_content, week_key)
            
            # Format: "- Title (ID: 123, External: No, Clicks: 1)"
            external_str = "Yes" if is_external else "No"
            formatted = f"- {title} (ID: {id_content}, External: {external_str}, Clicks: {click_count})"
            
            formatted_lines.append(formatted)
        
        # Join with newlines
        return "\n".join(formatted_lines)
    
    def _get_click_count_for_content(self, event_ids: List[str], id_content: int, week_key: str) -> int:
        """
        Get click count for a specific content.
        
        Clicks are matched via event_id (from user_questions) = log_id (in clicks).
        
        Args:
            event_ids: List of event IDs from user_questions
            id_content: Content ID
            week_key: Week key
            
        Returns:
            Click count (1 if clicked, 0 if not)
        """
        if not event_ids:
            return 0
        
        cursor = self.conn.cursor()
        
        # Check if there's a click for this content with any of these event_ids
        placeholders = ','.join('?' * len(event_ids))
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM raw_clicks
            WHERE log_id IN ({placeholders})
              AND id_content = ?
              AND week_key = ?
        """, (*event_ids, id_content, week_key))
        
        row = cursor.fetchone()
        count = row[0] if row else 0
        
        # Return 1 if clicked, 0 if not (binary)
        return 1 if count > 0 else 0
    
    def _get_rating_for_questions(self, event_ids: List[str], week_key: str) -> str:
        """
        Get rating text for a question.
        
        Ratings are matched via event_id (from user_questions) = log_id (in ratings).
        
        Args:
            event_ids: List of event IDs from user_questions
            week_key: Week key
            
        Returns:
            Formatted rating string (e.g., "Rating: Yes") or empty string
        """
        if not event_ids:
            return ""
        
        cursor = self.conn.cursor()
        
        # Check if there's a rating for any of these event_ids
        placeholders = ','.join('?' * len(event_ids))
        cursor.execute(f"""
            SELECT rating, comment
            FROM raw_ratings
            WHERE log_id IN ({placeholders}) AND week_key = ?
            LIMIT 1
        """, (*event_ids, week_key))
        
        row = cursor.fetchone()
        
        if row and row[0]:
            rating_value = row[0]
            comment = row[1]
            
            # Format: "Rating: Yes" or "Rating: No"
            if comment and comment != "-":
                return f"Rating: {rating_value} - {comment}"
            else:
                return f"Rating: {rating_value}"
        
        return ""
