#!/usr/bin/env python3
"""
Simple test script for Team 3 Orchestrator
Run this to validate your system before tomorrow's testing
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, expected_status=200):
    """Test a single endpoint"""
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {endpoint}: OK")
            return True
        else:
            print(f"❌ {endpoint}: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ {endpoint}: ERROR - {e}")
        return False

def test_post_endpoint(endpoint, data, expected_status=200):
    """Test a POST endpoint"""
    try:
        response = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {endpoint}: OK")
            return True
        else:
            print(f"❌ {endpoint}: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ {endpoint}: ERROR - {e}")
        return False

def main():
    print("🧪 Testing Team 3 Orchestrator System")
    print("=" * 50)
    
    # Wait for service to be ready
    print("⏳ Waiting for service to be ready...")
    time.sleep(5)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Basic health check
    total_tests += 1
    if test_endpoint("/health"):
        tests_passed += 1
    
    # Test 2: Detailed health check
    total_tests += 1
    if test_endpoint("/health/detailed"):
        tests_passed += 1
    
    # Test 3: System resources
    total_tests += 1
    if test_endpoint("/system/resources"):
        tests_passed += 1
    
    # Test 4: List containers
    total_tests += 1
    if test_endpoint("/containers"):
        tests_passed += 1
    
    # Test 5: List images
    total_tests += 1
    if test_endpoint("/images"):
        tests_passed += 1
    
    # Test 6: Integration test
    total_tests += 1
    if test_endpoint("/test/integration"):
        tests_passed += 1
    
    # Test 7: Start a test container
    total_tests += 1
    test_data = {"count": 1, "resources": {"cpu_limit": "0.1", "memory_limit": "128m"}}
    if test_post_endpoint("/containers/nginx:alpine/start", test_data):
        tests_passed += 1
        print("   ℹ️  Test container started - check /containers to see it")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your system is ready for tomorrow!")
    else:
        print("⚠️  Some tests failed. Check the logs and fix issues before tomorrow.")
    
    print("\n🔍 To see detailed health status:")
    print(f"   curl {BASE_URL}/health/detailed")
    print("\n🔍 To see all containers:")
    print(f"   curl {BASE_URL}/containers")
    print("\n🔍 To run integration test:")
    print(f"   curl {BASE_URL}/test/integration")

if __name__ == "__main__":
    main()
