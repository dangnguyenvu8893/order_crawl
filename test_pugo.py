#!/usr/bin/env python3
"""
Test script đơn giản để verify pugo.vn integration
"""

import requests
import json

def test_pugo_integration():
    """Test pugo.vn integration"""
    print("=== TEST PUGO.VN INTEGRATION ===")
    
    base_url = "http://localhost:5001"
    
    # Test URL 1688
    test_url = "https://detail.1688.com/offer/948414629704.html?offerId=948414629704&spm=a260k.home2025.recommendpart.2"
    
    try:
        print(f"Testing URL: {test_url}")
        
        # Test extract-pugo
        print("\n1. Testing extract-pugo...")
        response = requests.post(f"{base_url}/extract-pugo", json={"url": test_url})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Status: {result.get('status')}")
            print(f"   Login Success: {result.get('login_success')}")
            
            raw_data = result.get('raw_data', {})
            if raw_data.get('status') == 'success':
                api_data = raw_data.get('data', {})
                if api_data.get('success'):
                    product_data = api_data['data']
                    print(f"   ✅ Product: {product_data.get('name', 'N/A')[:50]}...")
                    print(f"   ✅ Price: {product_data.get('sellPrice', 'N/A')} ({product_data.get('sellPriceVND', 'N/A')} VND)")
                    print(f"   ✅ Shop: {product_data.get('shopName', 'N/A')}")
                    print(f"   ✅ Images: {len(product_data.get('imgThumbs', []))}")
                    print(f"   ✅ SKUs: {len(product_data.get('skuMaps', []))}")
                else:
                    print(f"   ❌ API Error: {api_data.get('message')}")
            else:
                print(f"   ❌ Extract Error: {raw_data.get('message')}")
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
        
        # Test transform-pugo-from-url
        print("\n2. Testing transform-pugo-from-url...")
        response = requests.post(f"{base_url}/transform-pugo-from-url", json={"url": test_url})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Status: {result.get('status')}")
            print(f"   Name: {result.get('name', 'N/A')[:50]}...")
            print(f"   Max Price: {result.get('maxPrice', 'N/A')}")
            print(f"   Images: {len(result.get('images', []))}")
            print(f"   SKU Properties: {len(result.get('skuProperty', []))}")
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
        
        print("\n✅ PUGO.VN INTEGRATION TEST COMPLETED")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_pugo_integration()
