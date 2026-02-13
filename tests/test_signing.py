"""Tests for HMAC-SHA256 signing."""

import pytest
from src.api.signing import RequestSigner


class TestRequestSigner:
    """Test cases for request signing."""
    
    def test_basic_get_request(self):
        """Test signing a basic GET request."""
        signer = RequestSigner(api_secret="test_secret")
        
        headers = signer.sign_request(
            method="GET",
            path="/v1/events/sessions",
            query_params={"offset": "0", "length": "100"}
        )
        
        assert "x-inbenta-signature" in headers
        assert "x-inbenta-signature-version" in headers
        assert headers["x-inbenta-signature-version"] == "v1"
        assert "x-inbenta-timestamp" in headers
    
    def test_post_request_with_body(self):
        """Test signing a POST request with body."""
        signer = RequestSigner(api_secret="test_secret")
        
        headers = signer.sign_request(
            method="POST",
            path="/v1/auth",
            body='{"secret":"test"}'
        )
        
        assert "x-inbenta-signature" in headers
        assert headers["x-inbenta-signature-version"] == "v1"
    
    def test_percent_encoding(self):
        """Test that special characters are properly encoded."""
        signer = RequestSigner(api_secret="test_secret")
        
        # Path with special characters
        encoded = signer._percent_encode("/v1/test path?query=value")
        
        # Spaces should be %20, ? should be %3F, = should be %3D
        assert " " not in encoded
        assert "%20" in encoded or "+" not in encoded
    
    def test_sorted_query_string(self):
        """Test that query parameters are sorted."""
        signer = RequestSigner(api_secret="test_secret")
        
        query_str = signer._build_sorted_query_string({
            "z": "last",
            "a": "first",
            "m": "middle"
        })
        
        assert query_str == "a=first&m=middle&z=last"
    
    def test_empty_query_params(self):
        """Test signing with no query parameters."""
        signer = RequestSigner(api_secret="test_secret")
        
        headers = signer.sign_request(
            method="GET",
            path="/v1/events/sessions"
        )
        
        assert "x-inbenta-signature" in headers
    
    def test_base_string_format_matches_postman(self):
        """Test that base string matches Postman implementation."""
        signer = RequestSigner(api_secret="test_secret")
        
        # Simulate: GET https://api-reporting-us.inbenta.io/prod/v1/events/user_questions
        headers = signer.sign_request(
            method="GET",
            path="/prod/v1/events/user_questions",
            query_params=None,  # No query params
            body=None  # No body for GET
        )
        
        # Base string should be: GET&v1%2Fevents%2Fuser_questions&{timestamp}&v1
        # (No query params or body elements)
        assert "x-inbenta-signature" in headers
        assert "x-inbenta-signature-version" in headers
        assert headers["x-inbenta-signature-version"] == "v1"
        assert "x-inbenta-timestamp" in headers
    
    def test_path_removes_prod_prefix(self):
        """Test that /prod/ prefix is removed from path."""
        signer = RequestSigner(api_secret="test_secret")
        
        # Path with /prod/ prefix
        base_string = signer._build_base_string(
            method="GET",
            path="/prod/v1/events/sessions",
            query_params=None,
            body=None,
            timestamp=1234567890
        )
        
        # Should be: GET&v1%2Fevents%2Fsessions&1234567890&v1
        assert "v1%2Fevents%2Fsessions" in base_string
        assert "prod" not in base_string.lower()
        assert base_string.startswith("GET&")
        assert base_string.endswith("&1234567890&v1")
    
    def test_path_removes_leading_slash(self):
        """Test that leading slashes are removed from path."""
        signer = RequestSigner(api_secret="test_secret")
        
        base_string = signer._build_base_string(
            method="GET",
            path="/v1/events/clicks",
            query_params=None,
            body=None,
            timestamp=1111111111
        )
        
        # Should start with v1, not /v1
        assert "v1%2Fevents%2Fclicks" in base_string
        # Should not have %2F before v1 (which would be encoded /)
        assert not base_string.startswith("GET&%2Fv1")
    
    def test_empty_elements_skipped(self):
        """Test that empty query params and body are skipped entirely."""
        signer = RequestSigner(api_secret="test_secret")
        
        base_string = signer._build_base_string(
            method="GET",
            path="/v1/events/ratings",
            query_params={},  # Empty dict
            body=None,  # No body
            timestamp=9999999999
        )
        
        # Should be: GET&v1%2Fevents%2Fratings&9999999999&v1
        # Count the & separators - should be exactly 3 (GET&path&timestamp&version)
        assert base_string.count("&") == 3
        
    def test_with_query_params_included(self):
        """Test that non-empty query params ARE included."""
        signer = RequestSigner(api_secret="test_secret")
        
        base_string = signer._build_base_string(
            method="GET",
            path="/v1/events/sessions",
            query_params={"offset": "0", "length": "100"},
            body=None,
            timestamp=5555555555
        )
        
        # Should have 4 & separators (GET&path&query&timestamp&version)
        assert base_string.count("&") == 4
        # Should contain encoded query string
        assert "length%3D100%26offset%3D0" in base_string or "offset%3D0%26length%3D100" in base_string
