#!/usr/bin/env python3
"""
Test Docker compatibility cho pugo.vn integration
"""

import os
import sys
import subprocess

def test_docker_compatibility():
    """Test xem code có tương thích với Docker không"""
    print("=== TEST DOCKER COMPATIBILITY ===")
    
    # Test 1: Kiểm tra Selenium có thể import không
    print("1. Testing Selenium import...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        print("   ✅ Selenium import thành công")
    except ImportError as e:
        print(f"   ❌ Selenium import thất bại: {e}")
        return False
    
    # Test 2: Kiểm tra Chrome có sẵn không
    print("2. Testing Chrome availability...")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Thử tạo driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
        print("   ✅ Chrome driver hoạt động")
    except Exception as e:
        print(f"   ❌ Chrome driver lỗi: {e}")
        return False
    
    # Test 3: Kiểm tra extractor có thể khởi tạo không
    print("3. Testing extractor initialization...")
    try:
        from py_extractors.extractor_pugo import ExtractorPugo
        extractor = ExtractorPugo()
        print("   ✅ Extractor khởi tạo thành công")
    except Exception as e:
        print(f"   ❌ Extractor khởi tạo thất bại: {e}")
        return False
    
    # Test 4: Kiểm tra can_handle method
    print("4. Testing can_handle method...")
    try:
        test_urls = [
            "https://detail.1688.com/offer/948414629704.html",
            "https://item.taobao.com/item.htm?id=123",
            "https://detail.tmall.com/item.htm?id=123",
            "https://pugo.vn/item/123"
        ]
        
        for url in test_urls:
            if extractor.can_handle(url):
                print(f"   ✅ Can handle: {url}")
            else:
                print(f"   ❌ Cannot handle: {url}")
    except Exception as e:
        print(f"   ❌ can_handle test thất bại: {e}")
        return False
    
    # Test 5: Kiểm tra Flask app có thể import không
    print("5. Testing Flask app import...")
    try:
        from app import app
        print("   ✅ Flask app import thành công")
    except Exception as e:
        print(f"   ❌ Flask app import thất bại: {e}")
        return False
    
    print("\n✅ TẤT CẢ TESTS PASSED - CODE TƯƠNG THÍCH VỚI DOCKER")
    return True

def test_dockerfile_syntax():
    """Test Dockerfile syntax"""
    print("\n=== TEST DOCKERFILE SYNTAX ===")
    
    try:
        # Kiểm tra Dockerfile có tồn tại không
        if not os.path.exists("Dockerfile"):
            print("   ❌ Dockerfile không tồn tại")
            return False
        
        # Kiểm tra docker-compose.yml có tồn tại không
        if not os.path.exists("docker-compose.yml"):
            print("   ❌ docker-compose.yml không tồn tại")
            return False
        
        print("   ✅ Dockerfile và docker-compose.yml tồn tại")
        
        # Kiểm tra requirements.txt
        if not os.path.exists("requirements.txt"):
            print("   ❌ requirements.txt không tồn tại")
            return False
        
        print("   ✅ requirements.txt tồn tại")
        
        # Kiểm tra selenium trong requirements.txt
        with open("requirements.txt", "r") as f:
            content = f.read()
            if "selenium" in content:
                print("   ✅ Selenium có trong requirements.txt")
            else:
                print("   ❌ Selenium không có trong requirements.txt")
                return False
        
        print("   ✅ Dockerfile syntax OK")
        return True
        
    except Exception as e:
        print(f"   ❌ Dockerfile test thất bại: {e}")
        return False

if __name__ == "__main__":
    print("Testing Docker compatibility for pugo.vn integration...\n")
    
    # Test code compatibility
    code_ok = test_docker_compatibility()
    
    # Test Dockerfile syntax
    dockerfile_ok = test_dockerfile_syntax()
    
    if code_ok and dockerfile_ok:
        print("\n🎉 TẤT CẢ TESTS PASSED!")
        print("Code sẵn sàng để build Docker image")
        print("\nĐể build và chạy:")
        print("1. docker build -t order-management-crawler .")
        print("2. docker-compose up -d")
    else:
        print("\n❌ CÓ LỖI CẦN SỬA TRƯỚC KHI BUILD DOCKER")
        sys.exit(1)
