"""Tests for date utilities."""

import pytest
from datetime import datetime
from src.utils.date_utils import (
    get_week_key,
    get_week_range,
    parse_date,
    format_date,
    format_report_date,
    split_date_range
)


class TestDateUtils:
    """Test cases for date utility functions."""
    
    def test_get_week_key(self):
        """Test week key generation."""
        date = datetime(2026, 1, 20)  # A Tuesday in week 4
        week_key = get_week_key(date)
        
        assert week_key == "2026-W04"
    
    def test_get_week_range_from_tuesday(self):
        """Test getting Sunday-Saturday range from a Tuesday."""
        date = datetime(2026, 1, 20)  # Tuesday
        start, end = get_week_range(date)
        
        # Should get Sunday Jan 18 to Saturday Jan 24
        assert start.date() == datetime(2026, 1, 18).date()
        assert end.date() == datetime(2026, 1, 24).date()
        assert start.weekday() == 6  # Sunday
        assert end.weekday() == 5    # Saturday
    
    def test_get_week_range_from_sunday(self):
        """Test getting week range when date is already Sunday."""
        date = datetime(2026, 1, 18)  # Sunday
        start, end = get_week_range(date)
        
        assert start.date() == datetime(2026, 1, 18).date()
        assert end.date() == datetime(2026, 1, 24).date()
    
    def test_parse_date_valid(self):
        """Test parsing valid date string."""
        date = parse_date("2026-01-20")
        
        assert date.year == 2026
        assert date.month == 1
        assert date.day == 20
    
    def test_parse_date_invalid(self):
        """Test parsing invalid date string."""
        with pytest.raises(ValueError):
            parse_date("invalid-date")
    
    def test_format_date(self):
        """Test date formatting."""
        date = datetime(2026, 1, 20)
        formatted = format_date(date)
        
        assert formatted == "2026-01-20"
    
    def test_format_report_date(self):
        """Test report date formatting (DDMMYYYY)."""
        date = datetime(2026, 1, 20)
        formatted = format_report_date(date)
        
        assert formatted == "20012026"
    
    def test_split_date_range_within_limit(self):
        """Test splitting date range when it's within max_days."""
        start = datetime(2026, 1, 18)
        end = datetime(2026, 1, 20)  # 3 days
        
        windows = split_date_range(start, end, max_days=3)
        
        assert len(windows) == 1
        assert windows[0][0] == start
        assert windows[0][1] == end
    
    def test_split_date_range_exceeds_limit(self):
        """Test splitting date range when it exceeds max_days."""
        start = datetime(2026, 1, 18)
        end = datetime(2026, 1, 24)  # 7 days
        
        windows = split_date_range(start, end, max_days=3)
        
        # Should be split into 3 windows: 3 days, 3 days, 1 day
        assert len(windows) == 3
        assert windows[0][0] == datetime(2026, 1, 18)
        assert windows[0][1] == datetime(2026, 1, 20)
        assert windows[1][0] == datetime(2026, 1, 21)
        assert windows[1][1] == datetime(2026, 1, 23)
        assert windows[2][0] == datetime(2026, 1, 24)
        assert windows[2][1] == datetime(2026, 1, 24)
