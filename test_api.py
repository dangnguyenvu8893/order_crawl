#!/usr/bin/env python3
"""
Script test để kiểm tra các API endpoints của Selenium service
"""

import requests
import json
import time

# Cấu hình
BASE_URL = "http://localhost:5001"
TEST_PRODUCT_ID = "948998794646"
TEST_URL = f"https://detail.1688.com/offer/{TEST_PRODUCT_ID}.html"

def test_health_check():
    """Test health check endpoint"""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False



def test_load_1688_product():
    """Test load 1688 product endpoint"""
    print("\n🔍 Testing load 1688 product endpoint...")
    try:
        data = {
            "product_id": TEST_PRODUCT_ID
        }
        
        print(f"   Loading product ID: {TEST_PRODUCT_ID}")
        response = requests.post(f"{BASE_URL}/load-1688-product", json=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Load 1688 product successful")
            print(f"   Status: {result.get('status', 'N/A')}")
            print(f"   Content length: {result.get('content_length', 'N/A')}")
            print(f"   Product ID: {result.get('product_id', 'N/A')}")
            print(f"   URL: {result.get('url', 'N/A')}")
            print(f"   Cookies used: {result.get('cookies_used', 'N/A')}")
        else:
            print(f"❌ Load 1688 product failed: {response.status_code}")
            print(f"   Error: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Load 1688 product error: {e}")
        return False

def test_invalid_requests():
    """Test invalid requests"""
    print("\n🔍 Testing invalid requests...")
    

    
    # Test missing product ID
    try:
        response = requests.post(f"{BASE_URL}/load-1688-product", json={})
        if response.status_code == 400:
            print("✅ Missing product ID validation passed")
        else:
            print(f"❌ Missing product ID validation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Missing product ID test error: {e}")

def main():
    """Main test function"""
    print("🚀 Starting API tests for 1688 Selenium Service")
    print("=" * 50)
    
    # Wait for service to be ready
    print("⏳ Waiting for service to be ready...")
    time.sleep(5)
    
    # Run tests
    tests = [
        test_health_check,
        test_load_1688_product,
        test_invalid_requests
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(2)  # Wait between tests
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Service is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the service logs.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
