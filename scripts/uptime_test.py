#!/usr/bin/env python3
"""
Comprehensive uptime test for Missing Table application
Tests database -> backend -> frontend connectivity
"""

import requests
import psycopg2
import subprocess
import json
import time
import sys
import asyncio
from typing import Dict, Any, Tuple
from datetime import datetime

# Import the login test
try:
    from login_uptime_test import LoginUptimeTest
    LOGIN_TEST_AVAILABLE = True
except ImportError:
    LOGIN_TEST_AVAILABLE = False
    print("⚠️  Login test not available (playwright not installed)")

# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:8080"
SUPABASE_DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message: str, color: str = Colors.NC):
    """Print colored message"""
    print(f"{color}{message}{Colors.NC}")

def test_with_retry(name: str, test_func, retries: int = 3, delay: int = 2) -> bool:
    """Test function with retries"""
    for i in range(1, retries + 1):
        print(f"Testing {name} (attempt {i}/{retries})... ", end="", flush=True)
        try:
            result = test_func()
            if result:
                print_colored("✓ PASS", Colors.GREEN)
                return True
            else:
                raise Exception("Test returned False")
        except Exception as e:
            if i < retries:
                print_colored("✗ RETRY", Colors.YELLOW)
                time.sleep(delay)
            else:
                print_colored(f"✗ FAIL: {str(e)}", Colors.RED)
                return False
    return False

def test_supabase_status() -> bool:
    """Test Supabase status"""
    result = subprocess.run(["npx", "supabase", "status"], 
                          capture_output=True, text=True)
    return result.returncode == 0

def test_database_connection() -> bool:
    """Test direct database connection"""
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] == 1
    except Exception:
        return False

def test_http_endpoint(url: str, timeout: int = 10) -> bool:
    """Test HTTP endpoint"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False

def test_backend_health() -> bool:
    """Test backend health endpoint"""
    return test_http_endpoint(f"{BACKEND_URL}/health")

def test_backend_data_endpoint(endpoint: str) -> bool:
    """Test backend data endpoint"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/{endpoint}", timeout=10)
        return response.status_code == 200
    except Exception:
        return False

def get_database_counts() -> Tuple[int, int]:
    """Get team and game counts from database"""
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM teams")
        teams_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM games")
        games_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        return teams_count, games_count
    except Exception:
        return 0, 0

def get_backend_data_count(endpoint: str) -> int:
    """Get count of data from backend endpoint"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/{endpoint}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return len(data) if isinstance(data, list) else 0
        return 0
    except Exception:
        return 0

def test_k8s_pods() -> bool:
    """Test Kubernetes pods are running"""
    try:
        result = subprocess.run([
            "kubectl", "get", "pods", "-n", "missing-table", 
            "--no-headers", "-o", "custom-columns=STATUS:.status.phase"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return False
            
        statuses = result.stdout.strip().split('\n')
        return all(status.strip() == "Running" for status in statuses if status.strip())
    except Exception:
        return False

def test_k8s_services() -> bool:
    """Test Kubernetes services are available"""
    try:
        result = subprocess.run([
            "kubectl", "get", "services", "-n", "missing-table", "--no-headers"
        ], capture_output=True, text=True)
        
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception:
        return False

def test_auth_endpoint() -> Tuple[bool, str]:
    """Test authentication endpoint"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/auth/me", 
                              headers={"Content-Type": "application/json"}, 
                              timeout=10)
        return True, f"Status: {response.status_code}"
    except Exception as e:
        return False, str(e)

async def test_login_functionality() -> Tuple[bool, str]:
    """Test complete login functionality using playwright"""
    if not LOGIN_TEST_AVAILABLE:
        return False, "Playwright not available"
    
    try:
        print("    Running login test with playwright...")
        login_test = LoginUptimeTest()
        success = await login_test.run_tests()
        return success, "Login flow completed" if success else "Login flow failed"
    except Exception as e:
        return False, f"Login test error: {str(e)}"

async def main():
    """Main test function"""
    print_colored("🔍 Missing Table Uptime Test", Colors.BLUE)
    print("=========================================")
    print(f"Started at: {datetime.now()}")
    print()

    test_results = {}

    # Test 1: Local Supabase Database
    print_colored("1. Testing Local Supabase Database", Colors.BLUE)
    test_results['supabase_status'] = test_with_retry("Supabase Status", test_supabase_status)
    test_results['db_connection'] = test_with_retry("Database Connection", test_database_connection)

    # Test 2: Backend API Health
    print_colored("\n2. Testing Backend API", Colors.BLUE)
    test_results['backend_health'] = test_with_retry("Backend Health", test_backend_health)
    test_results['backend_table'] = test_with_retry("Backend Table Endpoint", 
                                                   lambda: test_backend_data_endpoint("table"))
    test_results['backend_games'] = test_with_retry("Backend Games Endpoint", 
                                                   lambda: test_backend_data_endpoint("games"))
    test_results['backend_teams'] = test_with_retry("Backend Teams Endpoint", 
                                                   lambda: test_backend_data_endpoint("teams"))

    # Test 3: Frontend Accessibility
    print_colored("\n3. Testing Frontend", Colors.BLUE)
    test_results['frontend_home'] = test_with_retry("Frontend Homepage", 
                                                   lambda: test_http_endpoint(FRONTEND_URL))

    # Test 4: End-to-End Data Flow
    print_colored("\n4. Testing End-to-End Data Flow", Colors.BLUE)
    print("Checking database data... ", end="", flush=True)
    teams_count, games_count = get_database_counts()
    print_colored(f"Teams in DB: {teams_count}, Games in DB: {games_count}", Colors.BLUE)

    if teams_count > 0 and games_count > 0:
        print_colored("✓ Database has data", Colors.GREEN)
        
        # Test if backend returns the data
        print("Testing backend data retrieval... ", end="", flush=True)
        backend_teams = get_backend_data_count("table")
        if backend_teams > 0:
            print_colored(f"✓ Backend returns {backend_teams} teams", Colors.GREEN)
            test_results['data_flow'] = True
        else:
            print_colored("✗ Backend returns empty data", Colors.RED)
            # Show actual response for debugging
            try:
                response = requests.get(f"{BACKEND_URL}/api/table", timeout=10)
                print(f"Backend response: {response.text}")
            except Exception as e:
                print(f"Error getting backend response: {e}")
            test_results['data_flow'] = False
    else:
        print_colored("⚠ Database appears empty - this may be expected for fresh setup", Colors.YELLOW)
        test_results['data_flow'] = None

    # Test 5: Kubernetes Health
    print_colored("\n5. Testing Kubernetes Deployment", Colors.BLUE)
    test_results['k8s_pods'] = test_with_retry("K8s Pods Running", test_k8s_pods)
    test_results['k8s_services'] = test_with_retry("K8s Services Available", test_k8s_services)

    # Test 6: Authentication Flow
    print_colored("\n6. Testing Authentication", Colors.BLUE)
    auth_success, auth_message = test_auth_endpoint()
    if auth_success:
        print_colored(f"✓ Auth endpoint accessible - {auth_message}", Colors.GREEN)
        test_results['auth'] = True
    else:
        print_colored(f"✗ Auth endpoint failed - {auth_message}", Colors.RED)
        test_results['auth'] = False
    
    # Test 7: Login Functionality (if playwright available)
    print_colored("\n7. Testing Login Functionality", Colors.BLUE)
    if LOGIN_TEST_AVAILABLE:
        login_success, login_message = await test_login_functionality()
        if login_success:
            print_colored(f"✓ Login functionality working - {login_message}", Colors.GREEN)
            test_results['login'] = True
        else:
            print_colored(f"✗ Login functionality failed - {login_message}", Colors.RED)
            test_results['login'] = False
    else:
        print_colored("⚠ Login test skipped - Playwright not available", Colors.YELLOW)
        test_results['login'] = None

    # Summary
    print_colored("\n📊 Test Summary", Colors.BLUE)
    print("=========================================")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"Database: Supabase Local (127.0.0.1:54322)")
    print()
    
    # Count results
    passed = sum(1 for result in test_results.values() if result is True)
    failed = sum(1 for result in test_results.values() if result is False)
    skipped = sum(1 for result in test_results.values() if result is None)
    total = len(test_results)
    
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped out of {total} tests")
    
    if failed > 0:
        print_colored("\n🔧 Next steps if tests fail:", Colors.BLUE)
        print("1. Ensure 'npx supabase start' is running")
        print("2. Check helm deployment: 'helm status missing-table -n missing-table'")
        print("3. View logs: 'kubectl logs -n missing-table -l app.kubernetes.io/component=backend'")
        print("4. Check database data: 'npx supabase db reset' to populate sample data")
        print("5. Verify network connectivity between k8s and host")

    print(f"\nTest completed at: {datetime.now()}")
    
    # Exit with error code if any tests failed
    if failed > 0:
        sys.exit(1)
    else:
        print_colored("🎉 All tests passed!", Colors.GREEN)
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())