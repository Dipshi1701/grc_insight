"""Extractors for normalizing API responses into database rows."""

import logging
from typing import List, Dict, Any

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class Extractors:
    """Normalizes API responses into flat database row dictionaries."""
    
    @staticmethod
    def extract_event_sources(sources: List[Dict[str, Any]], excluded_patterns: List[str]) -> List[Dict[str, Any]]:
        """
        Extract and mark excluded event sources.
        
        Args:
            sources: Raw API response sources
            excluded_patterns: List of patterns to match for exclusion (case-insensitive)
            
        Returns:
            List of normalized source dictionaries
        """
        normalized = []
        
        for source in sources:
            source_name = source.get('name', '')
            
            # Check if source should be excluded (case-insensitive substring match)
            is_excluded = any(
                pattern.lower() in source_name.lower()
                for pattern in excluded_patterns
            )
            
            normalized.append({
                'id': source.get('id'),
                'name': source_name,
                'is_excluded': is_excluded
            })
        
        logger.debug(f"Extracted {len(normalized)} sources, {sum(s['is_excluded'] for s in normalized)} excluded")
        
        return normalized
    
    @staticmethod
    def extract_session_data_keys(keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract session data keys.
        
        Args:
            keys: Raw API response keys
            
        Returns:
            List of normalized key dictionaries
        """
        normalized = []
        
        for key in keys:
            normalized.append({
                'id': key.get('id'),
                'key_name': key.get('name')
            })
        
        logger.debug(f"Extracted {len(normalized)} session data keys")
        
        return normalized
    
    @staticmethod
    def extract_user_questions(questions: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract user questions and their matchings.
        
        Args:
            questions: Raw API response questions
            
        Returns:
            Tuple of (questions_list, matchings_list)
        """
        questions_normalized = []
        matchings_normalized = []
        
        for idx, question in enumerate(questions):
            # API response has event_id as the primary identifier
            event_id = question.get('event_id')
            
            if not event_id:
                # Fallback: generate a unique ID if missing
                date_str = question.get('date', '')
                event_id = f"{date_str}_{idx}" if date_str else f"question_{idx}"
            
            # Extract question - note: session_id doesn't exist in user_questions API
            questions_normalized.append({
                'event_id': event_id,
                'user_question': question.get('user_question'),
                'date': question.get('date'),
                'session_id': None,  # Not provided in user_questions endpoint
                'log_id': question.get('log_id'),
                'source': question.get('source')
            })
            
            # Extract matchings (flatten array into child rows)
            matchings = question.get('matchings') or []
            for matching in matchings:
                matchings_normalized.append({
                    'event_id': event_id,
                    'id_content': matching.get('id_content'),
                    'weight': matching.get('weight'),
                    'is_external': matching.get('external', False)
                })
        
        logger.debug(f"Extracted {len(questions_normalized)} questions with {len(matchings_normalized)} matchings")
        
        return questions_normalized, matchings_normalized
    
    @staticmethod
    def extract_sessions(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract session events.
        
        Args:
            sessions: Raw API response session events
            
        Returns:
            List of normalized session event dictionaries
        """
        normalized = []
        
        for idx, session in enumerate(sessions):
            # API response has event_id as the primary identifier
            event_id = session.get('event_id')
            
            if not event_id:
                # Fallback: generate a unique ID if missing
                date_str = session.get('date', '')
                event_id = f"{date_str}_{idx}" if date_str else f"session_{idx}"
            
            normalized.append({
                'event_id': event_id,
                'session_id': session.get('session_id'),
                'key': session.get('key'),
                'value': session.get('value'),
                'user_question': session.get('user_question'),
                'date': session.get('date'),
                'log_id': session.get('log_id')
            })
        
        logger.debug(f"Extracted {len(normalized)} session events")
        
        return normalized
    
    @staticmethod
    def extract_clicks(clicks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract click events.
        
        Args:
            clicks: Raw API response click events
            
        Returns:
            List of normalized click event dictionaries
        """
        normalized = []
        
        for idx, click in enumerate(clicks):
            # API response has event_id as the primary identifier
            event_id = click.get('event_id')
            
            if not event_id:
                # Fallback: generate a unique ID if missing
                date_str = click.get('date', '')
                event_id = f"{date_str}_{idx}" if date_str else f"click_{idx}"
            
            normalized.append({
                'event_id': event_id,
                'session_id': click.get('session_id'),
                'id_content': click.get('id_content'),
                'click_type': click.get('click_type'),
                'log_id': click.get('log_id'),
                'date': click.get('date')
            })
        
        logger.debug(f"Extracted {len(normalized)} click events")
        
        return normalized
    
    @staticmethod
    def extract_ratings(ratings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract rating events.
        
        Args:
            ratings: Raw API response rating events
            
        Returns:
            List of normalized rating event dictionaries
        """
        normalized = []
        
        for idx, rating in enumerate(ratings):
            # API response has event_id as the primary identifier
            event_id = rating.get('event_id')
            
            if not event_id:
                # Fallback: generate a unique ID if missing
                date_str = rating.get('date', '')
                event_id = f"{date_str}_{idx}" if date_str else f"rating_{idx}"
            
            normalized.append({
                'event_id': event_id,
                'session_id': rating.get('session_id'),
                'rating': rating.get('rating'),
                'comment': rating.get('comment'),
                'log_id': rating.get('log_id'),
                'date': rating.get('date')
            })
        
        logger.debug(f"Extracted {len(normalized)} rating events")
        
        return normalized
    
    @staticmethod
    def extract_session_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract aggregated session details.
        
        Args:
            details: Raw API response session details
            
        Returns:
            List of normalized session detail dictionaries
        """
        import json
        
        normalized = []
        
        for detail in details:
            # Convert arrays to JSON strings for storage
            log_ids = detail.get('log_ids', [])
            ids_contents = detail.get('ids_contents', [])
            
            normalized.append({
                'session_id': detail.get('session_id'),
                'source': detail.get('source'),
                'duration': detail.get('duration'),
                'environment': detail.get('environment'),
                'date': detail.get('date'),
                'log_ids': json.dumps(log_ids) if log_ids else None,
                'ids_contents': json.dumps(ids_contents) if ids_contents else None
            })
        
        logger.debug(f"Extracted {len(normalized)} session details")
        
        return normalized
