"""Inbenta Reporting API client with pagination and rate limiting."""

import requests
import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.api.auth import InbentaAuth
from src.api.signing import RequestSigner
from src.utils.logging_config import get_logger
from src.utils.date_utils import split_date_range, split_into_single_days

logger = get_logger(__name__)


class InbentaReportingClient:
    """Client for Inbenta Reporting API with pagination, rate limiting, and retry logic."""
    
    def __init__(
        self,
        base_url: str,
        auth: InbentaAuth,
        signer: RequestSigner,
        rate_limit: int = 800
    ):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL for reporting API
            auth: Authentication handler
            signer: Request signer
            rate_limit: Requests per minute limit (default: 800)
        """
        # Get dynamic base URL from auth response, fallback to provided base_url
        self.auth = auth
        try:
            self.base_url = auth.get_reporting_base_url().rstrip('/')
            logger.info(f"Using dynamic reporting base URL from auth: {self.base_url}")
        except Exception as e:
            self.base_url = base_url.rstrip('/')
            logger.warning(f"Could not get dynamic base URL from auth, using provided: {self.base_url}")
        
        self.signer = signer
        self.rate_limit = rate_limit
        self.min_request_interval = 60.0 / rate_limit  # seconds between requests
        self.last_request_time = 0
    
    def _rate_limit_sleep(self):
        """Sleep to enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    @retry(
        retry=retry_if_exception_type((requests.HTTPError, requests.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a signed API request with rate limiting and retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/v1/events/sessions')
            params: Query parameters
            body: Request body
            
        Returns:
            Response JSON data
            
        Raises:
            requests.HTTPError: If request fails after retries
        """
        self._rate_limit_sleep()
        
        # Build full URL
        url = f"{self.base_url}{endpoint}"
        
        # Get auth headers
        headers = self.auth.get_auth_headers()
        headers["Content-Type"] = "application/json"
        headers["x-inbenta-key"] = self.auth.api_key
        
        # Prepare body
        body_str = json.dumps(body) if body else None
        
        # Sign request
        signature_headers = self.signer.sign_request(
            method=method,
            path=endpoint,
            query_params=params,
            body=body_str
        )
        headers.update(signature_headers)
        
        # Make request
        logger.info(f"")
        logger.info(f"=== API REQUEST ===")
        logger.info(f"{method} {url}")
        if params:
            logger.info(f"Query Params: {params}")
        logger.info(f"Headers:")
        for key, value in headers.items():
            if key == 'Authorization':
                logger.info(f"  {key}: Bearer {value[7:50]}...")  # Truncate token
            else:
                logger.info(f"  {key}: {value}")
        logger.debug(f"{method} {endpoint} with params={params}")
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=body_str,
            timeout=60
        )
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.warning("Rate limit hit (429), retrying...")
            raise requests.HTTPError("Rate limit exceeded", response=response)
        
        # Handle server errors (will trigger retry)
        if response.status_code in [500, 502, 503, 504]:
            logger.warning(f"Server error {response.status_code}, retrying...")
            raise requests.HTTPError(f"Server error {response.status_code}", response=response)
        
        response.raise_for_status()
        
        logger.info(f"SUCCESS: {response.status_code} {response.reason}")
        logger.info(f"Response size: {len(response.content)} bytes")
        logger.info(f"=== END REQUEST ===")
        logger.info(f"")
        
        return response.json()
    
    def _simple_fetch(
        self,
        endpoint: str,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from an endpoint without pagination.
        
        The Inbenta API returns all results in a single call.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            List of all records
        """
        logger.info(f"Fetching {endpoint}")
        
        response = self._make_request("GET", endpoint, params=params)
        
        records = response.get("results", [])
        total_count = response.get("total", len(records))
        
        logger.info(f"Fetched {len(records)} records (total: {total_count})")
        
        return records
    
    def _paginated_fetch(
        self,
        endpoint: str,
        params: Dict[str, Any],
        max_per_page: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from endpoint.
        
        NOTE: Inbenta API does not support offset/length pagination.
        Returns 403 Forbidden when these parameters are included.
        This method now just calls _simple_fetch for compatibility.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            max_per_page: Maximum records per page (ignored)
            
        Returns:
            List of all records
        """
        # Inbenta API returns 403 Forbidden when using offset/length
        # Use simple fetch instead
        return self._simple_fetch(endpoint, params)
    
    def _log_date_coverage(
        self,
        records: List[Dict[str, Any]],
        date_from: datetime,
        date_to: datetime,
        record_type: str
    ):
        """
        Log date coverage to verify all dates have data.
        
        Args:
            records: Fetched records
            date_from: Expected start date
            date_to: Expected end date
            record_type: Type of record (for logging)
        """
        if not records:
            logger.warning(f"No {record_type} records fetched!")
            return
        
        from collections import defaultdict
        
        # Count records by date
        date_counts = defaultdict(int)
        for record in records:
            record_date = record.get('date', '')
            if record_date:
                # Extract just the date part (YYYY-MM-DD)
                date_only = record_date[:10]
                date_counts[date_only] += 1
        
        # Sort dates
        sorted_dates = sorted(date_counts.keys())
        
        if sorted_dates:
            logger.info(f"Date coverage for {record_type}: {len(sorted_dates)} unique dates")
            logger.info(f"  First date: {sorted_dates[0]}")
            logger.info(f"  Last date: {sorted_dates[-1]}")
            logger.info(f"  Records per date:")
            for date in sorted_dates:
                logger.info(f"    {date}: {date_counts[date]:,} records")
    
    def get_event_sources(self) -> List[Dict[str, Any]]:
        """
        Fetch event sources.
        
        Returns:
            List of event source dictionaries
        """
        logger.info("Fetching event sources")
        endpoint = "/v1/aggregates/event_sources"
        response = self._make_request("GET", endpoint)
        return response.get("results", [])
    
    def get_session_data_keys(self) -> List[Dict[str, Any]]:
        """
        Fetch session data keys.
        
        Returns:
            List of session data key dictionaries
        """
        logger.info("Fetching session data keys")
        endpoint = "/v1/aggregates/session_data_keys"
        response = self._make_request("GET", endpoint)
        return response.get("results", [])
    
    def get_session_details(
        self,
        date_from: datetime,
        date_to: datetime,
        # environment: str = "production",
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch aggregated session details day-by-day (API limitation workaround).
        
        Args:
            date_from: Start date
            date_to: End date
            environment: Environment filter (default: production)
            sources: List of allowed sources
            
        Returns:
            List of session detail dictionaries
        """
        logger.info(f"Fetching session details from {date_from} to {date_to}")
        logger.info("Using day-by-day fetching due to API limitations")
        
        endpoint = "/v1/aggregates/session_details"
        
        # Split into individual days
        days = split_into_single_days(date_from, date_to)
        total_days = len(days)
        
        all_sessions = []
        for day_num, (day_start, day_end) in enumerate(days, 1):
            logger.info(f"Fetching day {day_num}/{total_days}: {day_start.date()}")
            
            params = {
                "date_from": day_start.strftime("%Y-%m-%d"),
                "date_to": day_end.strftime("%Y-%m-%d"),
                # "environment": environment
            }
            
            if sources:
                params["source"] = json.dumps(sources)
            
            sessions = self._simple_fetch(endpoint, params)
            all_sessions.extend(sessions)
            
            logger.info(f"  Day {day_start.date()}: {len(sessions)} session details")
        
        logger.info(f"Total session details fetched: {len(all_sessions)}")
        
        # Log date coverage
        self._log_date_coverage(all_sessions, date_from, date_to, "session_details")
        
        return all_sessions
    
    def get_user_questions(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL user questions events day-by-day (API limitation workaround).
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of ALL user question dictionaries
        """
        logger.info(f"Fetching user questions from {date_from} to {date_to}")
        logger.info("Using day-by-day fetching due to API limitations")
        
        endpoint = "/v1/events/user_questions"
        
        # Split into individual days
        days = split_into_single_days(date_from, date_to)
        total_days = len(days)
        
        all_questions = []
        for day_num, (day_start, day_end) in enumerate(days, 1):
            logger.info(f"Fetching day {day_num}/{total_days}: {day_start.date()}")
            
            params = {
                "date_from": day_start.strftime("%Y-%m-%d"),
                "date_to": day_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["source"] = json.dumps(sources)
            
            questions = self._simple_fetch(endpoint, params)
            all_questions.extend(questions)
            
            logger.info(f"  Day {day_start.date()}: {len(questions)} questions")
        
        logger.info(f"Total user questions fetched: {len(all_questions)}")
        
        # Log date coverage
        self._log_date_coverage(all_questions, date_from, date_to, "user_questions")
        
        return all_questions
    
    def get_sessions(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL session events day-by-day (API limitation workaround).
        
        The Inbenta API has inconsistent behavior with multi-day ranges.
        Fetching one day at a time ensures complete data coverage.
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of ALL session event dictionaries
        """
        logger.info(f"Fetching session events from {date_from} to {date_to}")
        logger.info("Using day-by-day fetching due to API limitations")
        
        endpoint = "/v1/events/sessions"
        
        # Split into individual days (API doesn't handle multi-day ranges well)
        days = split_into_single_days(date_from, date_to)
        total_days = len(days)
        
        all_sessions = []
        for day_num, (day_start, day_end) in enumerate(days, 1):
            logger.info(f"Fetching day {day_num}/{total_days}: {day_start.date()}")
            
            params = {
                "date_from": day_start.strftime("%Y-%m-%d"),
                "date_to": day_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["source"] = json.dumps(sources)
            
            # Use simple fetch (no pagination - API doesn't support it)
            sessions = self._simple_fetch(endpoint, params)
            all_sessions.extend(sessions)
            
            logger.info(f"  Day {day_start.date()}: {len(sessions)} sessions")
        
        logger.info(f"Total sessions fetched: {len(all_sessions)}")
        
        # Log date coverage
        self._log_date_coverage(all_sessions, date_from, date_to, "sessions")
        
        return all_sessions
    
    def get_clicks(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL click events day-by-day (API limitation workaround).
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of ALL click event dictionaries
        """
        logger.info(f"Fetching click events from {date_from} to {date_to}")
        logger.info("Using day-by-day fetching due to API limitations")
        
        endpoint = "/v1/events/clicks"
        
        # Split into individual days
        days = split_into_single_days(date_from, date_to)
        total_days = len(days)
        
        all_clicks = []
        for day_num, (day_start, day_end) in enumerate(days, 1):
            logger.info(f"Fetching day {day_num}/{total_days}: {day_start.date()}")
            
            params = {
                "date_from": day_start.strftime("%Y-%m-%d"),
                "date_to": day_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["source"] = json.dumps(sources)
            
            clicks = self._simple_fetch(endpoint, params)
            all_clicks.extend(clicks)
            
            logger.info(f"  Day {day_start.date()}: {len(clicks)} clicks")
        
        logger.info(f"Total clicks fetched: {len(all_clicks)}")
        
        # Log date coverage
        self._log_date_coverage(all_clicks, date_from, date_to, "clicks")
        
        return all_clicks
    
    def get_ratings(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch ALL rating events day-by-day (API limitation workaround).
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of ALL rating event dictionaries
        """
        logger.info(f"Fetching rating events from {date_from} to {date_to}")
        logger.info("Using day-by-day fetching due to API limitations")
        
        endpoint = "/v1/events/ratings"
        
        # Split into individual days
        days = split_into_single_days(date_from, date_to)
        total_days = len(days)
        
        all_ratings = []
        for day_num, (day_start, day_end) in enumerate(days, 1):
            logger.info(f"Fetching day {day_num}/{total_days}: {day_start.date()}")
            
            params = {
                "date_from": day_start.strftime("%Y-%m-%d"),
                "date_to": day_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["source"] = json.dumps(sources)
            
            ratings = self._simple_fetch(endpoint, params)
            all_ratings.extend(ratings)
            
            logger.info(f"  Day {day_start.date()}: {len(ratings)} ratings")
        
        logger.info(f"Total ratings fetched: {len(all_ratings)}")
        
        # Log date coverage
        self._log_date_coverage(all_ratings, date_from, date_to, "ratings")
        
        return all_ratings
