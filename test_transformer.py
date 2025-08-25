#!/usr/bin/env python3
import json
import os
from py_transformers.transformer_1688 import transformer_1688

# Đường dẫn file input và output
input_file = r'D:\Order_Management\order_managerment_crawl\test result 1688\response_1756126921208.json'
output_file = r'D:\Order_Management\order_managerment_crawl\test-Result\transformed_1756126921208.json'

try:
    # Đọc file JSON từ extractor
    print(f"Đọc file: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Input data keys: {list(data.keys())}")
    print(f"Status: {data.get('status')}")
    print(f"SourceId: {data.get('sourceId')}")
    
    # Transform data
    print("Đang transform...")
    result = transformer_1688.transform(data)
    
    # Tạo thư mục output nếu chưa có
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Ghi kết quả
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"OK -> {output_file}")
    print(f"Output keys: {list(result.keys())}")
    print(f"Images count: {len(result.get('images', []))}")
    print(f"SKU properties count: {len(result.get('skuProperty', []))}")
    print(f"Name: {result.get('name', 'N/A')}")
    print(f"Max price: {result.get('maxPrice', 'N/A')}")
    
except Exception as e:
    print(f"Lỗi: {e}")
    import traceback
    traceback.print_exc()
