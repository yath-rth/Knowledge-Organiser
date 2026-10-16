#!/usr/bin/env python3
"""
Test script for the Email Processing API.
Run this after deploying to verify all endpoints work correctly.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://localhost:5000/api"


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_endpoint(name, url, params=None):
    """Test a single endpoint and print results."""
    print(f"Testing: {name}")
    print(f"URL: {url}")
    if params:
        print(f"Params: {params}")

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:500]}...")
            print("✓ Success")
            return True
        else:
            print(f"✗ Failed: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Connection Error - Is the API running?")
        return False
    except requests.exceptions.Timeout:
        print("✗ Timeout - API took too long to respond")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    finally:
        print()


def main():
    """Run all API tests."""
    print_section("Email Processing API Test Suite")
    print(f"Base URL: {API_BASE_URL}")
    print(f"Test Time: {datetime.now().isoformat()}\n")

    results = []

    # Test 1: Health Check
    print_section("1. Health Check")
    results.append(test_endpoint(
        "Health Check",
        f"{API_BASE_URL}/health"
    ))

    # Test 2: Get Stats
    print_section("2. Database Statistics")
    results.append(test_endpoint(
        "Get Statistics",
        f"{API_BASE_URL}/stats"
    ))

    # Test 3: Get Recent Emails
    print_section("3. Get Recent Emails")
    results.append(test_endpoint(
        "Get Recent Emails (limit 5)",
        f"{API_BASE_URL}/emails",
        params={"limit": 5}
    ))

    # Test 4: Get High Priority Emails
    print_section("4. Filter by Priority")
    results.append(test_endpoint(
        "Get HIGH Priority Emails",
        f"{API_BASE_URL}/emails/priority/HIGH",
        params={"limit": 5}
    ))

    # Test 5: Get EXTRA_HIGH Priority Emails
    results.append(test_endpoint(
        "Get EXTRA_HIGH Priority Emails",
        f"{API_BASE_URL}/emails/priority/EXTRA_HIGH"
    ))

    # Test 6: Get by Category
    print_section("5. Filter by Category")
    results.append(test_endpoint(
        "Get Internship Emails",
        f"{API_BASE_URL}/emails/category/internship"
    ))

    # Test 7: Sync Endpoint
    print_section("6. Sync Endpoint")
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    results.append(test_endpoint(
        "Sync Emails (since yesterday)",
        f"{API_BASE_URL}/emails/sync",
        params={"last_sync": yesterday}
    ))

    # Test 8: Heartbeat
    print_section("7. System Heartbeat")
    results.append(test_endpoint(
        "Get Recent Heartbeats",
        f"{API_BASE_URL}/heartbeat",
        params={"limit": 5}
    ))

    # Test 9: Filter with 'since' parameter
    print_section("8. Time-based Filtering")
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    results.append(test_endpoint(
        "Get Emails Since 1 Hour Ago",
        f"{API_BASE_URL}/emails",
        params={"since": one_hour_ago, "limit": 10}
    ))

    # Test 10: Invalid Endpoints (should return 404)
    print_section("9. Error Handling")
    results.append(not test_endpoint(
        "Invalid Endpoint (should fail)",
        f"{API_BASE_URL}/invalid"
    ))

    # Summary
    print_section("Test Summary")
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"Passed: {passed}/{total} ({percentage:.1f}%)")

    if passed == total:
        print("\n✓ All tests passed! API is working correctly.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit(main())
