"""Tests for data extractors."""

import pytest
from src.ingestion.extractors import Extractors


class TestExtractors:
    """Test cases for API response extractors."""
    
    def test_extract_event_sources_with_exclusions(self):
        """Test extracting sources with exclusion logic."""
        sources = [
            {"id": 1, "name": "Production_Source"},
            {"id": 2, "name": "dev_test_source"},
            {"id": 3, "name": "GSK_MEDICAL_bot"},
            {"id": 4, "name": "Valid_Source"}
        ]
        
        excluded_patterns = ["dev", "GSK_MEDICAL"]
        
        result = Extractors.extract_event_sources(sources, excluded_patterns)
        
        assert len(result) == 4
        assert result[0]["is_excluded"] == False  # Production_Source
        assert result[1]["is_excluded"] == True   # dev_test_source
        assert result[2]["is_excluded"] == True   # GSK_MEDICAL_bot
        assert result[3]["is_excluded"] == False  # Valid_Source
    
    def test_extract_event_sources_case_insensitive(self):
        """Test that exclusion matching is case-insensitive."""
        sources = [
            {"id": 1, "name": "DEV_Source"},
            {"id": 2, "name": "Dev_Source"},
            {"id": 3, "name": "dev_source"}
        ]
        
        excluded_patterns = ["dev"]
        
        result = Extractors.extract_event_sources(sources, excluded_patterns)
        
        # All should be excluded regardless of case
        assert all(s["is_excluded"] for s in result)
    
    def test_extract_session_data_keys(self):
        """Test extracting session data keys."""
        keys = [
            {"id": 1, "name": "SEARCH"},
            {"id": 2, "name": "CLICK"},
            {"id": 3, "name": "RATING"}
        ]
        
        result = Extractors.extract_session_data_keys(keys)
        
        assert len(result) == 3
        assert result[0]["key_name"] == "SEARCH"
    
    def test_extract_user_questions_with_matchings(self):
        """Test extracting questions and flattening matchings."""
        questions = [
            {
                "id": "q1",
                "user_question": "What is the copay?",
                "date": "2026-01-18T10:00:00",
                "session_id": "session1",
                "log_id": "log1",
                "source": 1,
                "matchings": [
                    {"id_content": 100, "weight": 0.9, "external": False},
                    {"id_content": 101, "weight": 0.8, "external": True}
                ]
            }
        ]
        
        questions_result, matchings_result = Extractors.extract_user_questions(questions)
        
        assert len(questions_result) == 1
        assert questions_result[0]["event_id"] == "q1"
        assert questions_result[0]["user_question"] == "What is the copay?"
        
        assert len(matchings_result) == 2
        assert matchings_result[0]["id_content"] == 100
        assert matchings_result[0]["is_external"] == False
        assert matchings_result[1]["id_content"] == 101
        assert matchings_result[1]["is_external"] == True
    
    def test_extract_sessions(self):
        """Test extracting session events."""
        sessions = [
            {
                "id": "e1",
                "session_id": "session1",
                "key": "SEARCH",
                "value": None,
                "user_question": "test question",
                "date": "2026-01-18T10:00:00",
                "log_id": "log1"
            }
        ]
        
        result = Extractors.extract_sessions(sessions)
        
        assert len(result) == 1
        assert result[0]["event_id"] == "e1"
        assert result[0]["key"] == "SEARCH"
    
    def test_extract_clicks(self):
        """Test extracting click events."""
        clicks = [
            {
                "id": "c1",
                "session_id": "session1",
                "id_content": 100,
                "click_type": "answer",
                "log_id": "log1",
                "date": "2026-01-18T10:00:00"
            }
        ]
        
        result = Extractors.extract_clicks(clicks)
        
        assert len(result) == 1
        assert result[0]["id_content"] == 100
    
    def test_extract_ratings(self):
        """Test extracting rating events."""
        ratings = [
            {
                "id": "r1",
                "session_id": "session1",
                "rating": "Yes",
                "comment": "Helpful",
                "log_id": "log1",
                "date": "2026-01-18T10:00:00"
            }
        ]
        
        result = Extractors.extract_ratings(ratings)
        
        assert len(result) == 1
        assert result[0]["rating"] == "Yes"
    
    def test_extract_session_details(self):
        """Test extracting session details."""
        details = [
            {
                "session_id": "session1",
                "source": "TrelegryHCP",
                "duration": 120,
                "environment": "production",
                "date": "2026-01-18"
            }
        ]
        
        result = Extractors.extract_session_details(details)
        
        assert len(result) == 1
        assert result[0]["source"] == "TrelegryHCP"
        assert result[0]["duration"] == 120
