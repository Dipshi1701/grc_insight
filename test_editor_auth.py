"""
Test script for Inbenta Editor API authentication.
Tests fetching content titles using Editor API credentials.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from dotenv import load_dotenv

load_dotenv()

# Load Editor API credentials from .env
EDITOR_API_KEY = os.getenv("INBENTA_EDITOR_API_KEY")
EDITOR_SECRET = os.getenv("INBENTA_EDITOR_API_SECRET")
USER_PERSONAL_SECRET = os.getenv("INBENTA_EDITOR_PERSONAL_SECRET_KEY")
EDITOR_BASE_URL = os.getenv("INBENTA_EDITOR_BASE_URL", "https://chatbot-api-us.inbenta.io/editor/v1")

# Test content IDs
TEST_CONTENT_IDS = [1183, 1, 17, 18]  # Try multiple IDs

print("=" * 80)
print("TESTING INBENTA EDITOR API")
print("=" * 80)
print()

# Validate credentials
if not EDITOR_API_KEY or not EDITOR_SECRET or not USER_PERSONAL_SECRET:
    print("ERROR: Missing credentials in .env file")
    print("Required:")
    print("  - INBENTA_EDITOR_API_KEY")
    print("  - INBENTA_EDITOR_API_SECRET")
    print("  - INBENTA_EDITOR_PERSONAL_SECRET_KEY")
    sys.exit(1)

print("OK - Credentials loaded from .env")
print(f"  API Key: {EDITOR_API_KEY[:20]}...")
print(f"  Secret: {EDITOR_SECRET[:30]}...")
print(f"  User Personal Secret: {USER_PERSONAL_SECRET[:20]}...")
print(f"  Base URL: {EDITOR_BASE_URL}")
print()

# Step 1: Get Bearer token
print("-" * 80)
print("STEP 1: Getting Bearer Token")
print("-" * 80)

try:
    # Build auth URL with query parameters
    auth_url = f"https://api.inbenta.io/v1/auth?secret={EDITOR_SECRET}&user_personal_secret={USER_PERSONAL_SECRET}"
    
    # Request headers
    headers = {
        "x-inbenta-key": EDITOR_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Request body
    payload = {
        "key": EDITOR_API_KEY,
        "secret": EDITOR_SECRET,
        "user_personal_secret": USER_PERSONAL_SECRET
    }
    
    print("Making auth request...")
    response = requests.post(auth_url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        auth_data = response.json()
        token = auth_data.get("accessToken")
        
        if token:
            print(f"OK - Bearer token obtained: {token[:50]}...")
            print()
        else:
            print("ERROR - No accessToken in response")
            print(f"Response: {response.text}")
            sys.exit(1)
    else:
        print(f"ERROR - Failed to get Bearer token (Status: {response.status_code})")
        print(f"Response: {response.text}")
        sys.exit(1)
    
except Exception as e:
    print(f"ERROR - Failed to get Bearer token: {e}")
    sys.exit(1)

# Step 2: Test fetching content
print("-" * 80)
print("STEP 2: Testing Content Fetching")
print("-" * 80)
print()

success_count = 0
not_found_count = 0
error_count = 0

for content_id in TEST_CONTENT_IDS:
    print(f"Testing content ID: {content_id}")
    
    url = f"{EDITOR_BASE_URL}/contents/{content_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "x-inbenta-key": EDITOR_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Success!
            data = response.json()
            content_data = data.get("data", {})
            title = content_data.get("title", "No title")
            
            print(f"  OK - SUCCESS")
            print(f"    Status: {response.status_code}")
            print(f"    Title: {title}")
            print(f"    Content ID: {content_id}")
            
            # Print all available fields for reference
            print(f"    Available fields: {', '.join(content_data.keys())}")
            
            success_count += 1
            
        elif response.status_code == 404:
            # Content not found
            print(f"  NOT FOUND (404)")
            not_found_count += 1
            
        elif response.status_code == 401:
            # Unauthorized
            print(f"  ERROR - UNAUTHORIZED (401)")
            print(f"    Response: {response.text}")
            error_count += 1
            
        elif response.status_code == 403:
            # Forbidden
            print(f"  ERROR - FORBIDDEN (403)")
            print(f"    Response: {response.text}")
            error_count += 1
            
        else:
            # Other error
            print(f"  ERROR ({response.status_code})")
            print(f"    Response: {response.text}")
            error_count += 1
            
    except Exception as e:
        print(f"  ERROR - EXCEPTION: {e}")
        error_count += 1
    
    print()

# Summary
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total tested: {len(TEST_CONTENT_IDS)}")
print(f"OK - Successful: {success_count}")
print(f"WARNING - Not found: {not_found_count}")
print(f"ERROR - Errors: {error_count}")
print()

if success_count > 0:
    print("SUCCESS! Editor API authentication is working!")
    print()
    print("Next steps:")
    print("  1. Create src/api/editor_client.py")
    print("  2. Update src/transform/content_resolver.py")
    print("  3. Integrate into ingestion pipeline")
elif error_count > 0:
    print("WARNING - Authentication failed. Please check:")
    print("  1. Are INBENTA_EDITOR_API_KEY and INBENTA_EDITOR_API_SECRET correct?")
    print("  2. Do these credentials have access to the Editor API?")
    print("  3. Is the Editor API base URL correct?")
else:
    print("INFO - All tested content IDs returned 404 (not found)")
    print("  This might mean the content IDs don't exist.")
    print("  Try with different content IDs from your database.")

print("=" * 80)