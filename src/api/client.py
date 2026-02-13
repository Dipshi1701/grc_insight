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
from src.utils.date_utils import split_date_range

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
        Fetch all pages of data from a paginated endpoint.
        
        NOTE: Inbenta API currently does not support offset/length pagination.
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
        Fetch aggregated session details with date windowing.
        
        Args:
            date_from: Start date
            date_to: End date
            environment: Environment filter (default: production)
            sources: List of allowed sources
            
        Returns:
            List of session detail dictionaries
        """
        logger.info(f"Fetching session details from {date_from} to {date_to}")
        
        endpoint = "/v1/aggregates/session_details"
        
        # Split into 3-day windows to avoid timeouts
        windows = split_date_range(date_from, date_to, max_days=3)
        
        all_sessions = []
        for window_start, window_end in windows:
            params = {
                "date_from": window_start.strftime("%Y-%m-%d"),
                "date_to": window_end.strftime("%Y-%m-%d"),
                # "environment": environment
            }
            
            if sources:
                params["sources"] = json.dumps(sources)
            
            sessions = self._paginated_fetch(endpoint, params)
            all_sessions.extend(sessions)
            
            logger.info(f"Window {window_start.date()} to {window_end.date()}: {len(sessions)} sessions")
        
        return all_sessions
    
    def get_user_questions(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch user questions events with date windowing.
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of user question dictionaries
        """
        logger.info(f"Fetching user questions from {date_from} to {date_to}")
        
        endpoint = "/v1/events/user_questions"
        
        windows = split_date_range(date_from, date_to, max_days=3)
        
        all_questions = []
        for window_start, window_end in windows:
            params = {
                "date_from": window_start.strftime("%Y-%m-%d"),
                "date_to": window_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["sources"] = json.dumps(sources)
            
            questions = self._paginated_fetch(endpoint, params)
            all_questions.extend(questions)
            
            logger.info(f"Window {window_start.date()} to {window_end.date()}: {len(questions)} questions")
        
        return all_questions
    
    def get_sessions(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch session events with date windowing.
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of session event dictionaries
        """
        logger.info(f"Fetching session events from {date_from} to {date_to}")
        
        endpoint = "/v1/events/sessions"
        
        windows = split_date_range(date_from, date_to, max_days=3)
        
        all_sessions = []
        for window_start, window_end in windows:
            params = {
                "date_from": window_start.strftime("%Y-%m-%d"),
                "date_to": window_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["sources"] = json.dumps(sources)
            
            sessions = self._paginated_fetch(endpoint, params)
            all_sessions.extend(sessions)
            
            logger.info(f"Window {window_start.date()} to {window_end.date()}: {len(sessions)} events")
        
        return all_sessions
    
    def get_clicks(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch click events with date windowing.
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of click event dictionaries
        """
        logger.info(f"Fetching click events from {date_from} to {date_to}")
        
        endpoint = "/v1/events/clicks"
        
        windows = split_date_range(date_from, date_to, max_days=3)
        
        all_clicks = []
        for window_start, window_end in windows:
            params = {
                "date_from": window_start.strftime("%Y-%m-%d"),
                "date_to": window_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["sources"] = json.dumps(sources)
            
            clicks = self._paginated_fetch(endpoint, params)
            all_clicks.extend(clicks)
            
            logger.info(f"Window {window_start.date()} to {window_end.date()}: {len(clicks)} clicks")
        
        return all_clicks
    
    def get_ratings(
        self,
        date_from: datetime,
        date_to: datetime,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch rating events with date windowing.
        
        Args:
            date_from: Start date
            date_to: End date
            sources: List of allowed sources
            
        Returns:
            List of rating event dictionaries
        """
        logger.info(f"Fetching rating events from {date_from} to {date_to}")
        
        endpoint = "/v1/events/ratings"
        
        windows = split_date_range(date_from, date_to, max_days=3)
        
        all_ratings = []
        for window_start, window_end in windows:
            params = {
                "date_from": window_start.strftime("%Y-%m-%d"),
                "date_to": window_end.strftime("%Y-%m-%d")
            }
            
            if sources:
                params["sources"] = json.dumps(sources)
            
            ratings = self._paginated_fetch(endpoint, params)
            all_ratings.extend(ratings)
            
            logger.info(f"Window {window_start.date()} to {window_end.date()}: {len(ratings)} ratings")
        
        return all_ratings
