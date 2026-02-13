"""HMAC-SHA256 request signing for Inbenta API."""

import hmac
import hashlib
import logging
from datetime import datetime
from urllib.parse import quote, urlencode
from typing import Dict, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RequestSigner:
    """Handles HMAC-SHA256 signing of API requests."""
    
    def __init__(self, api_secret: str):
        """
        Initialize request signer.
        
        Args:
            api_secret: Inbenta API secret for signing
        """
        self.api_secret = api_secret
    
    def sign_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, str]] = None,
        body: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Sign a request and return signature headers.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path starting from /v1 (e.g., '/v1/events/sessions')
            query_params: Query parameters as dictionary
            body: Request body as JSON string
            
        Returns:
            Dictionary with signature headers
        """
        timestamp = int(datetime.now().timestamp())
        
        # Build base string
        base_string = self._build_base_string(
            method=method,
            path=path,
            query_params=query_params,
            body=body,
            timestamp=timestamp
        )
        
        logger.info(f"=== HMAC SIGNING ===")
        logger.info(f"Method: {method}")
        logger.info(f"Path: {path}")
        logger.info(f"Query Params: {query_params}")
        logger.info(f"Body: {body}")
        logger.info(f"Timestamp: {timestamp}")
        logger.info(f"Base String: {base_string}")
        
        # Generate signature
        signature = self._generate_signature(base_string)
        logger.info(f"Signature: {signature}")
        logger.info(f"=== END SIGNING ===")
        
        return {
            "x-inbenta-signature": signature,
            "x-inbenta-signature-version": "v1",
            "x-inbenta-timestamp": str(timestamp)
        }
    
    def _build_base_string(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, str]],
        body: Optional[str],
        timestamp: int
    ) -> str:
        """
        Build the base string for signing according to Inbenta protocol.
        
        Base string format (skip empty elements):
        METHOD&percent_encode(path)&[percent_encode(query)&][percent_encode(body)&]timestamp&v1
        """
        parts = []
        
        # 1. Method (uppercase)
        parts.append(method.upper())
        
        # 2. Path (percent-encoded, from v1 onwards, excluding /prod/)
        if path:
            # Remove /prod/ prefix if present
            clean_path = path
            if '/prod/' in clean_path:
                clean_path = clean_path.split('/prod/')[-1]
            
            # Ensure no leading slash
            clean_path = clean_path.lstrip('/')
            
            # Percent-encode
            parts.append(self._percent_encode(clean_path))
        
        # 3. Query string (only if present and non-empty)
        if query_params:
            sorted_query = self._build_sorted_query_string(query_params)
            if sorted_query:  # Only add if not empty
                parts.append(self._percent_encode(sorted_query))
        
        # 4. Body (only if present and non-empty) - typically skip for GET
        if body:
            parts.append(self._percent_encode(body))
        
        # 5. Timestamp
        parts.append(str(timestamp))
        
        # 6. Version
        parts.append("v1")
        
        return "&".join(parts)
    
    def _build_sorted_query_string(self, params: Dict[str, str]) -> str:
        """
        Build sorted query string per Inbenta protocol.
        
        Per docs and Postman: Sort alphabetically, stringify/decode values, format as key=value.
        
        Args:
            params: Query parameters
            
        Returns:
            Sorted query string (key1=value1&key2=value2) - NOT percent-encoded yet
        """
        if not params:
            return ""
        
        import json
        from urllib.parse import unquote
        
        # Sort by key
        sorted_params = sorted(params.items())
        
        # Build query string elements per Inbenta/Postman protocol
        import json
        
        elements = []
        for key, value in sorted_params:
            # JSON stringify the value to add quotes around strings
            # This matches Postman's behavior: date_from="2026-02-07"
            stringified_value = json.dumps(value, ensure_ascii=False)
            elements.append(f"{key}={stringified_value}")
        
        # Join with &
        return "&".join(elements)
    
    def _percent_encode(self, text: str) -> str:
        """
        Percent-encode text according to RFC 3986 (PHP rawurlencode equivalent).
        
        Args:
            text: Text to encode
            
        Returns:
            Percent-encoded text
        """
        # quote with safe='' encodes everything except unreserved characters
        # This matches PHP's rawurlencode behavior
        return quote(text, safe='')
    
    def _generate_signature(self, base_string: str) -> str:
        """
        Generate HMAC-SHA256 signature.
        
        Args:
            base_string: The base string to sign
            
        Returns:
            Hex-encoded signature
        """
        signature = hmac.new(
            key=self.api_secret.encode('utf-8'),
            msg=base_string.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return signature
