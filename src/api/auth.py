"""Authentication module for Inbenta API."""

import os
import requests
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.utils.logging_config import get_logger

# Disable proxy to avoid connection issues
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

logger = get_logger(__name__)


class InbentaAuth:
    """Handles authentication with Inbenta API including token caching."""
    
    def __init__(self, auth_url: str, api_key: str, api_secret: str, refresh_buffer: int = 120):
        """
        Initialize authentication handler.
        
        Args:
            auth_url: Authentication endpoint URL
            api_key: Inbenta API key
            api_secret: Inbenta API secret
            refresh_buffer: Seconds before expiry to refresh token (default: 120)
        """
        self.auth_url = auth_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.refresh_buffer = refresh_buffer
        
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._reporting_base_url: Optional[str] = None
    
    def get_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
            
        Raises:
            requests.HTTPError: If authentication fails
        """
        if self._needs_refresh():
            self._refresh_token()
        
        return self._access_token
    
    def _needs_refresh(self) -> bool:
        """
        Check if token needs to be refreshed.
        
        Returns:
            True if token is missing or expiring soon
        """
        if self._access_token is None or self._token_expiry is None:
            return True
        
        # Refresh if within buffer time of expiry
        time_until_expiry = (self._token_expiry - datetime.now()).total_seconds()
        return time_until_expiry <= self.refresh_buffer
    
    def _refresh_token(self):
        """
        Refresh the access token by calling the auth endpoint.
        
        Raises:
            requests.HTTPError: If authentication fails
        """
        logger.info("Refreshing authentication token")
        
        headers = {
            "x-inbenta-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        body = {
            "secret": self.api_secret
        }
        
        try:
            response = requests.post(
                self.auth_url,
                headers=headers,
                json=body,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            self._access_token = data.get("accessToken")
            expiration_seconds = data.get("expiration", 1200)  # Default 20 minutes
            self._token_expiry = datetime.now() + timedelta(seconds=expiration_seconds)
            
            # Extract reporting base URL from apis object
            apis = data.get("apis", {})
            self._reporting_base_url = apis.get("reporting")
            
            logger.info(f"=== AUTH SUCCESS ===")
            logger.info(f"Token refreshed successfully, expires in {expiration_seconds}s")
            logger.info(f"Access Token: {self._access_token}")
            logger.info(f"Reporting base URL: {self._reporting_base_url}")
            logger.info(f"Full auth response: {json.dumps(data, indent=2)}")
            logger.info(f"=== END AUTH ===")
            
        except requests.HTTPError as e:
            logger.error(f"Authentication failed: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get headers with valid authentication token.
        
        Returns:
            Dictionary with Authorization header
        """
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}"
        }
    
    def get_reporting_base_url(self) -> str:
        """
        Get the reporting API base URL from auth response.
        
        Returns:
            Reporting base URL (e.g., 'https://api-reporting-us.inbenta.io/prod')
        """
        if self._reporting_base_url is None:
            # Trigger auth if not done yet
            self.get_token()
        
        return self._reporting_base_url
    
    def invalidate(self):
        """Invalidate the current token (force refresh on next request)."""
        logger.info("Invalidating authentication token")
        self._access_token = None
        self._token_expiry = None
        self._reporting_base_url = None
