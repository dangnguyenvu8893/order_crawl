# Enhanced 1688 Crawler - Hướng dẫn chi tiết

## Tổng quan

`enhanced_1688_crawler.py` là một hệ thống crawl mới tích hợp logic từ cả Python crawl service và Node.js backend extractors/transformers. Hệ thống này sử dụng **cách tiếp cận khác với regex** để trích xuất dữ liệu từ 1688.com.

## Tính năng chính

### 1. **Multi-Method Extraction**
- **DOM Parsing**: Trích xuất dữ liệu thông qua CSS selectors và DOM manipulation
- **Enhanced Regex**: Cải tiến regex patterns với fallback mechanisms
- **Script Tag Analysis**: Phân tích các script tags để tìm dữ liệu JavaScript

### 2. **Stealth Mode**
- Anti-detection techniques
- Browser fingerprint spoofing
- Random user agents rotation
- Cookie management

### 3. **Data Transformation**
- Logic từ Node.js `data_transformer.js`
- Standardized output format
- Fallback mechanisms

## Luồng hoạt động chi tiết

### **Bước 1: Khởi tạo và Setup**
```
1. Tạo Enhanced1688Crawler instance
   ↓
2. Setup Playwright browser với stealth mode
   - Browser arguments cho anti-detection
   - Disable automation flags
   ↓
3. Tạo stealth context
   - Random user agent
   - Chinese locale và timezone
   - Custom headers
   - Stealth scripts injection
```

### **Bước 2: Load trang web**
```
1. Parse product ID từ URL
   - Regex: r'offer/(\d+)\.html'
   ↓
2. Navigate đến trang với Playwright
   - wait_until='domcontentloaded'
   - timeout=60000ms
   ↓
3. Chờ JavaScript load
   - sleep(15s) cho dynamic content
   - wait_for_load_state('networkidle')
   - sleep(5s) thêm để đảm bảo
```

### **Bước 3: Multi-Method Data Extraction**

#### **Method 1: DOM Parsing**
```python
# Trích xuất tên sản phẩm
selectors = [
    'h1[class*="title"]', 'h1[class*="product"]',
    '.product-title', '.offer-title', 'h1',
    '[data-spm="title"]', '.mod-detail-title h1'
]

# Trích xuất hình ảnh
selectors = [
    '.mod-detail-gallery img', '.gallery img',
    '.product-images img', '[data-spm="gallery"] img',
    '.detail-gallery img', 'img[src*="alicdn.com"]'
]

# Trích xuất SKU properties
selectors = [
    '.sku-property', '.product-sku',
    '[data-spm="sku"]', '.mod-detail-sku'
]

# Trích xuất giá cả
selectors = [
    '.price-current', '.current-price',
    '.product-price', '[data-spm="price"]',
    '.mod-detail-price'
]
```

#### **Method 2: Enhanced Regex**
```python
# Window context extraction
patterns = [
    r'window\.context\s*=\s*({[\s\S]*?});',  # Direct assignment
    r'window\.context\s*=\s*\(function\([^)]*\)\s*{[\s\S]*?}\s*\)\s*\([^,]+,\s*({[\s\S]*?})\s*\);'  # Function call
]

# Script tag analysis
script_pattern = r'<script[^>]*>(.*?)</script>'
var_patterns = [
    r'var\s+(\w+)\s*=\s*({[\s\S]*?});',
    r'let\s+(\w+)\s*=\s*({[\s\S]*?});',
    r'const\s+(\w+)\s*=\s*({[\s\S]*?});',
    r'(\w+)\s*:\s*({[\s\S]*?})\s*,'
]
```

### **Bước 4: Data Transformation**

#### **Logic từ Node.js Transformers**
```python
# Transform window context (từ data_transformer.js)
if 'result' in context and 'data' in context['result']:
    root_data = context['result']['data']
    if 'Root' in root_data and 'fields' in root_data['Root']:
        fields = root_data['Root']['fields']

        if 'dataJson' in fields:
            data_json = fields['dataJson']

            # Product name
            if 'tempModel' in data_json and 'offerTitle' in data_json['tempModel']:
                transformed['product']['name'] = data_json['tempModel']['offerTitle']

            # Images
            if 'images' in data_json:
                images = data_json['images']
                transformed['product']['images'] = [
                    {'index': i, 'url': img.get('fullPathImageURI', img.get('imageURI', '')), 'is_main': i == 0}
                    for i, img in enumerate(images) if img
                ]

            # SKU properties
            if 'skuModel' in data_json and 'skuProps' in data_json['skuModel']:
                sku_props = data_json['skuModel']['skuProps']
                transformed['product']['sku_properties'] = [
                    {
                        'name': prop.get('prop', ''),
                        'values': [val.get('name', '') for val in prop.get('value', [])]
                    }
                    for prop in sku_props
                ]
```

### **Bước 5: Result Selection và Output**
```python
# Chọn kết quả tốt nhất
best_result = None
if dom_result.get('status') == 'success':
    best_result = dom_result
elif regex_result.get('status') == 'success':
    best_result = regex_result

# Transform thành format chuẩn
transformed_data = self.transform_data_to_standard_format(best_result)

# Tạo response cuối cùng
final_result = {
    'status': 'success',
    'product_id': product_id,
    'sourceId': product_id,
    'sourceType': '1688',
    'url': url,
    'timestamp': time.time(),
    'content_length': len(html_content),
    'extraction_method': best_result.get('extraction_method', 'Unknown'),
    'parsed_product': transformed_data
}
```

## Cách sử dụng

### **1. Chạy trực tiếp**
```bash
cd order_managerment_crawl
python enhanced_1688_crawler.py
```

### **2. Import và sử dụng**
```python
from enhanced_1688_crawler import Enhanced1688Crawler
import asyncio

async def test_crawler():
    crawler = Enhanced1688Crawler()
    url = "https://detail.1688.com/offer/953742824238.html"
    result = await crawler.crawl_1688_product(url)
    print(result)

asyncio.run(test_crawler())
```

### **3. Tích hợp vào Flask app**
```python
from enhanced_1688_crawler import Enhanced1688Crawler

@app.route('/enhanced-crawl-1688', methods=['POST'])
async def enhanced_crawl_1688():
    data = request.get_json()
    url = data.get('url')

    crawler = Enhanced1688Crawler()
    result = await crawler.crawl_1688_product(url)

    return jsonify(result)
```

## Output Format

### **Success Response**
```json
{
  "status": "success",
  "product_id": "953742824238",
  "sourceId": "953742824238",
  "sourceType": "1688",
  "url": "https://detail.1688.com/offer/953742824238.html",
  "timestamp": 1703123456.789,
  "content_length": 50000,
  "extraction_method": "DOM",
  "parsed_product": {
    "status": "success",
    "sourceType": "1688",
    "product": {
      "name": "Tên sản phẩm",
      "max_price": "100.00",
      "images": [
        {
          "index": 0,
          "url": "https://cbu01.alicdn.com/img/...",
          "is_main": true
        }
      ],
      "sku_properties": [
        {
          "name": "Màu sắc",
          "values": ["Đỏ", "Xanh", "Vàng"]
        }
      ],
      "sku_map": [],
      "offer_price_ranges": []
    },
    "raw_data": {
      "images_count": 5,
      "sku_props_count": 2,
      "has_name": true,
      "has_price": true,
      "has_sku_map": false
    }
  }
}
```

### **Error Response**
```json
{
  "status": "error",
  "message": "Không thể trích xuất dữ liệu với bất kỳ phương pháp nào"
}
```

## Ưu điểm so với parser cũ

### **1. Đa dạng phương pháp trích xuất**
- **DOM Parsing**: Không phụ thuộc vào regex, linh hoạt hơn
- **Enhanced Regex**: Cải tiến patterns với fallback
- **Script Analysis**: Tìm dữ liệu trong JavaScript variables

### **2. Fallback Mechanisms**
- Nếu DOM parsing thất bại → thử Enhanced Regex
- Nếu Enhanced Regex thất bại → thử Script Analysis
- Multiple selectors cho mỗi loại dữ liệu

### **3. Tích hợp logic từ Node.js**
- Sử dụng logic transform từ `data_transformer.js`
- Consistent output format với backend
- Better error handling

### **4. Stealth Mode nâng cao**
- Browser fingerprint spoofing
- Anti-detection scripts
- Random user agents
- Cookie management

## Troubleshooting

### **1. Lỗi "Không thể khởi tạo browser"**
- Kiểm tra Playwright installation: `playwright install chromium`
- Kiểm tra system dependencies
- Tăng memory limit nếu cần

### **2. Lỗi "Không thể trích xuất dữ liệu"**
- Kiểm tra URL có hợp lệ không
- Thử với URL khác để test
- Kiểm tra logs để debug

### **3. Lỗi timeout**
- Tăng timeout values trong code
- Kiểm tra network connection
- Thử với proxy nếu cần

## Performance Tips

### **1. Optimize Browser Setup**
```python
# Giảm memory usage
browser_args = [
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-extensions',
    '--disable-plugins'
]
```

### **2. Optimize Wait Times**
```python
# Điều chỉnh theo network speed
await asyncio.sleep(10)  # Giảm từ 15s xuống 10s
```

### **3. Parallel Processing**
```python
# Crawl nhiều sản phẩm cùng lúc
async def crawl_multiple_products(urls):
    tasks = [crawler.crawl_1688_product(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results
```

## Kết luận

Enhanced 1688 Crawler cung cấp một cách tiếp cận mạnh mẽ và linh hoạt để trích xuất dữ liệu từ 1688.com. Với việc kết hợp nhiều phương pháp trích xuất và logic từ cả Python và Node.js backend, hệ thống này có khả năng xử lý các trường hợp phức tạp mà parser cũ không thể xử lý được.

