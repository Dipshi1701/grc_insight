"""Date and time utilities for the GRC pipeline."""

from datetime import datetime, timedelta
from typing import Tuple


def get_week_key(date: datetime) -> str:
    """
    Get the ISO week key for a given date (e.g., '2026-W04').
    
    Args:
        date: Date to get week key for
        
    Returns:
        Week key in format YYYY-Wnn (e.g., '2026-W04')
    """
    iso_year, iso_week, _ = date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_week_range(date: datetime) -> Tuple[datetime, datetime]:
    """
    Get the Sunday-Saturday week range for a given date.
    
    Args:
        date: Any date within the week
        
    Returns:
        Tuple of (week_start, week_end) as datetime objects
    """
    # Get the day of week (0=Monday, 6=Sunday)
    day_of_week = date.weekday()
    
    # Calculate days to subtract to get to Sunday
    # If it's Sunday (weekday=6), we're already at the start
    # Otherwise, we need to go back (weekday + 1) days
    if day_of_week == 6:  # Sunday
        week_start = date
    else:
        days_to_sunday = (day_of_week + 1) % 7
        week_start = date - timedelta(days=days_to_sunday)
    
    # Saturday is 6 days after Sunday
    week_end = week_start + timedelta(days=6)
    
    # Set to start and end of day
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return week_start, week_end


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If date string is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD") from e


def format_date(date: datetime, format_str: str = "%Y-%m-%d") -> str:
    """
    Format a datetime object as a string.
    
    Args:
        date: Datetime to format
        format_str: Format string (default: YYYY-MM-DD)
        
    Returns:
        Formatted date string
    """
    return date.strftime(format_str)


def format_report_date(date: datetime) -> str:
    """
    Format date for report filename (DDMMYYYY).
    
    Args:
        date: Date to format
        
    Returns:
        Date string in DDMMYYYY format
    """
    return date.strftime("%d%m%Y")


def split_date_range(start_date: datetime, end_date: datetime, max_days: int = 3) -> list[Tuple[datetime, datetime]]:
    """
    Split a date range into smaller windows of max_days.
    This is needed to avoid API timeouts on large date ranges.
    
    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum days per window (default: 3)
        
    Returns:
        List of (window_start, window_end) tuples
    """
    windows = []
    current_start = start_date
    
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=max_days - 1), end_date)
        windows.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    
    return windows


def split_into_single_days(start_date: datetime, end_date: datetime) -> list[Tuple[datetime, datetime]]:
    """
    Split date range into individual days for day-by-day API calls.
    
    This is needed because the Inbenta API has inconsistent behavior with multi-day ranges.
    When querying a date range, it may only return data for some dates.
    Querying one day at a time ensures complete data coverage.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        List of (day_start, day_end) tuples where day_start == day_end
        
    Example:
        Input: 2026-01-18 to 2026-01-20
        Output: [(2026-01-18, 2026-01-18), 
                 (2026-01-19, 2026-01-19),
                 (2026-01-20, 2026-01-20)]
    """
    days = []
    current = start_date
    
    while current <= end_date:
        days.append((current, current))
        current = current + timedelta(days=1)
    
    return days
