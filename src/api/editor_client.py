"""Inbenta Editor API client for fetching content details."""

import os
import requests
import logging
import time
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.utils.logging_config import get_logger

# Disable proxy to avoid connection issues
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

logger = get_logger(__name__)


class EditorAuth:
    """Handles Editor API authentication with user personal secret."""
    
    def __init__(
        self,
        auth_url: str,
        api_key: str,
        api_secret: str,
        user_personal_secret: str
    ):
        """
        Initialize Editor API authentication handler.
        
        Args:
            auth_url: Authentication endpoint URL
            api_key: Inbenta Editor API key
            api_secret: Inbenta Editor API secret
            user_personal_secret: User personal secret key
        """
        self.auth_url = auth_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_personal_secret = user_personal_secret
        self._access_token: Optional[str] = None
    
    def get_token(self) -> str:
        """
        Get a valid access token.
        
        Returns:
            Valid access token
            
        Raises:
            requests.HTTPError: If authentication fails
        """
        if self._access_token is None:
            self._authenticate()
        
        return self._access_token
    
    def _authenticate(self):
        """
        Authenticate with Editor API using the special format.
        
        Raises:
            requests.HTTPError: If authentication fails
        """
        logger.info("Authenticating with Editor API")
        
        # Build auth URL with query parameters
        auth_url = f"{self.auth_url}?secret={self.api_secret}&user_personal_secret={self.user_personal_secret}"
        
        # Request headers
        headers = {
            "x-inbenta-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Request body
        payload = {
            "key": self.api_key,
            "secret": self.api_secret,
            "user_personal_secret": self.user_personal_secret
        }
        
        try:
            response = requests.post(auth_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            auth_data = response.json()
            self._access_token = auth_data.get("accessToken")
            
            if not self._access_token:
                raise ValueError("No accessToken in authentication response")
            
            logger.info(f"Editor API authentication successful")
            logger.debug(f"Access token: {self._access_token[:50]}...")
            
        except requests.HTTPError as e:
            logger.error(f"Editor API authentication failed: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Editor API authentication: {e}")
            raise
    
    def invalidate(self):
        """Invalidate the current token (force re-authentication on next request)."""
        logger.info("Invalidating Editor API token")
        self._access_token = None


class InbentaEditorClient:
    """Client for Inbenta Editor API to fetch content details."""
    
    def __init__(
        self,
        base_url: str,
        auth: EditorAuth,
        rate_limit: int = 100
    ):
        """
        Initialize Editor API client.
        
        Args:
            base_url: Base URL for Editor API
            auth: Editor authentication handler
            rate_limit: Requests per minute limit (default: 100)
        """
        self.base_url = base_url.rstrip('/')
        self.auth = auth
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
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Make an Editor API request with rate limiting and retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/contents/123')
            
        Returns:
            Response JSON data
            
        Raises:
            requests.HTTPError: If request fails after retries
        """
        self._rate_limit_sleep()
        
        # Build full URL
        url = f"{self.base_url}{endpoint}"
        
        # Get auth headers
        token = self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-inbenta-key": self.auth.api_key,
            "Content-Type": "application/json"
        }
        
        # Make request
        logger.debug(f"{method} {url}")
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=30
        )
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.warning("Rate limit hit (429), retrying...")
            raise requests.HTTPError("Rate limit exceeded", response=response)
        
        # Handle authentication errors - invalidate token and retry
        if response.status_code == 401:
            logger.warning("Authentication failed (401), invalidating token and retrying...")
            self.auth.invalidate()
            raise requests.HTTPError("Authentication failed", response=response)
        
        # Handle server errors (will trigger retry)
        if response.status_code in [500, 502, 503, 504]:
            logger.warning(f"Server error {response.status_code}, retrying...")
            raise requests.HTTPError(f"Server error {response.status_code}", response=response)
        
        response.raise_for_status()
        
        logger.debug(f"SUCCESS: {response.status_code}")
        
        return response.json()
    
    def get_content(self, content_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch content details by ID.
        
        Args:
            content_id: Content ID
            
        Returns:
            Content data dictionary with 'title', 'description', etc., or None if not found
        """
        endpoint = f"/contents/{content_id}"
        
        try:
            response = self._make_request("GET", endpoint)
            content_data = response.get("data", {})
            
            logger.debug(f"Fetched content {content_id}: {content_data.get('title', 'No title')}")
            
            return content_data
            
        except requests.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.warning(f"Content {content_id} not found (404)")
                return None
            else:
                logger.error(f"Failed to fetch content {content_id}: {e}")
                raise
    
    def get_contents_batch(self, content_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Fetch multiple content details.
        
        Args:
            content_ids: List of content IDs
            
        Returns:
            Dictionary mapping content_id -> content_data
        """
        results = {}
        
        logger.info(f"Fetching {len(content_ids)} content details from Editor API")
        
        for i, content_id in enumerate(content_ids, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(content_ids)} contents fetched")
            
            try:
                content_data = self.get_content(content_id)
                if content_data:
                    results[content_id] = content_data
            except Exception as e:
                logger.error(f"Error fetching content {content_id}: {e}")
                # Continue with next content
        
        logger.info(f"Successfully fetched {len(results)}/{len(content_ids)} contents")
        
        return results
