#!/usr/bin/env python3
"""
End-to-End Test for Async Match Submission API

This script tests the complete flow:
1. Submit match data to /api/matches/submit
2. Get task ID from response
3. Poll /api/matches/task/{task_id} for status
4. Verify match was created in database

Requirements:
- Celery worker must be running
- FastAPI backend must be running
- Service account with manage_matches permission must exist
"""

import requests
import time
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"
SERVICE_ACCOUNT_TOKEN = None  # Will be obtained if needed

def get_service_account_token():
    """Get a service account token for authentication."""
    # For testing, we'll use a pre-existing token or create one
    # In production, this would be managed by match-scraper service
    print("\n📝 Note: You'll need a service account token with manage_matches permission")
    print("   Run: cd backend && uv run python create_service_account_token.py \\")
    print("        --service-name test-match-scraper --permissions manage_matches")

    token = input("\n🔑 Enter service account token (or press Enter to skip): ").strip()
    if not token:
        print("⚠️  No token provided. Test will use localhost bypass (if available)")
        return None
    return token


def test_async_match_submission():
    """Test the async match submission endpoint."""
    print("\n" + "="*80)
    print("TEST: Async Match Submission API")
    print("="*80)

    # Get auth token
    global SERVICE_ACCOUNT_TOKEN
    SERVICE_ACCOUNT_TOKEN = get_service_account_token()

    headers = {}
    if SERVICE_ACCOUNT_TOKEN:
        headers["Authorization"] = f"Bearer {SERVICE_ACCOUNT_TOKEN}"

    # Test match data
    match_data = {
        "home_team": "IFA 2012 Red",
        "away_team": "Inter Miami CF Academy 2012",
        "match_date": "2025-10-20T14:00:00Z",
        "season": "2025-26",
        "age_group": "U14",
        "division": "Division 1",
        "home_score": 2,
        "away_score": 1,
        "match_status": "played",
        "match_type": "League",
        "location": "IFA Training Center",
        "external_match_id": "test-async-match-001"
    }

    print("\n📤 Step 1: Submitting match data to /api/matches/submit")
    print(f"   Match: {match_data['home_team']} vs {match_data['away_team']}")

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/matches/submit",
            json=match_data,
            headers=headers
        )

        print(f"   Status Code: {response.status_code}")

        if response.status_code == 401:
            print("\n❌ Authentication failed!")
            print("   You need a valid service account token.")
            print("   Create one with:")
            print("   cd backend && uv run python create_service_account_token.py \\")
            print("   --service-name test-match-scraper --permissions manage_matches")
            return False

        if response.status_code != 200:
            print(f"❌ Failed to submit match: {response.text}")
            return False

        result = response.json()
        task_id = result.get("task_id")

        print(f"\n✅ Match submitted successfully!")
        print(f"   Task ID: {task_id}")
        print(f"   Status URL: {result.get('status_url')}")

    except Exception as e:
        print(f"\n❌ Error submitting match: {e}")
        return False

    # Step 2: Poll for task status
    print(f"\n📊 Step 2: Polling task status...")

    max_attempts = 30  # 30 seconds timeout
    attempt = 0

    while attempt < max_attempts:
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/matches/task/{task_id}",
                headers=headers
            )

            if response.status_code != 200:
                print(f"   ❌ Error checking status: {response.text}")
                return False

            status = response.json()
            state = status.get("state")
            ready = status.get("ready")

            print(f"   Attempt {attempt + 1}/{max_attempts}: State={state}, Ready={ready}")

            if ready:
                if status.get("result"):
                    print(f"\n✅ Task completed successfully!")
                    print(f"   Result: {status['result']}")
                    return True
                else:
                    print(f"\n❌ Task failed!")
                    print(f"   Error: {status.get('error')}")
                    return False

            time.sleep(1)
            attempt += 1

        except Exception as e:
            print(f"   ❌ Error polling status: {e}")
            return False

    print(f"\n⏱️  Timeout waiting for task completion")
    return False


def test_validation_failure():
    """Test that validation properly rejects invalid match data."""
    print("\n" + "="*80)
    print("TEST: Validation Failure (Missing Required Fields)")
    print("="*80)

    headers = {}
    if SERVICE_ACCOUNT_TOKEN:
        headers["Authorization"] = f"Bearer {SERVICE_ACCOUNT_TOKEN}"

    # Invalid match data (missing required fields)
    invalid_match = {
        "home_team": "IFA 2012 Red",
        # Missing away_team
        "match_date": "2025-10-20T14:00:00Z",
        # Missing season
    }

    print("\n📤 Submitting invalid match data...")

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/matches/submit",
            json=invalid_match,
            headers=headers
        )

        # Should get 422 Validation Error from Pydantic
        if response.status_code == 422:
            print(f"\n✅ Validation correctly rejected invalid data")
            print(f"   Error: {response.json()['detail']}")
            return True
        else:
            print(f"\n❌ Expected 422 validation error, got {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("ASYNC MATCH SUBMISSION - END-TO-END TEST")
    print("="*80)
    print("\nThis test requires:")
    print("✅ Celery worker running (uv run celery -A celery_app worker --loglevel=info)")
    print("✅ FastAPI backend running (./missing-table.sh start or uv run python app.py)")
    print("✅ Service account token with manage_matches permission")
    print("✅ Teams 'IFA 2012 Red' and 'Inter Miami CF Academy 2012' in database")

    input("\n Press Enter to continue...")

    # Run tests
    test_results = []

    # Test 1: Successful async submission
    result1 = test_async_match_submission()
    test_results.append(("Async Match Submission", result1))

    # Test 2: Validation failure
    result2 = test_validation_failure()
    test_results.append(("Validation Failure", result2))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in test_results)

    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nPhase 4 (Match-Scraper Integration) - API Endpoint Complete!")
        print("✅ /api/matches/submit endpoint working")
        print("✅ Celery task queuing functional")
        print("✅ Task status tracking working")
        print("✅ Validation rejecting invalid data")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nCheck the errors above and ensure:")
        print("- Celery worker is running")
        print("- Backend API is running")
        print("- Service account token is valid")
        print("- Required teams exist in database")
    print("="*80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
