# 1688 Selenium Service

Service Selenium được dockerize để load và crawl dữ liệu từ trang web 1688.com.

## Tính năng

- Load trang web 1688.com với Selenium WebDriver
- API endpoints để trigger việc load trang
- Xử lý JavaScript và dynamic content
- Trích xuất thông tin sản phẩm, giá cả, mô tả
- Dockerized để dễ dàng deploy

## Cài đặt và chạy

### Sử dụng Docker Compose (Khuyến nghị)

1. Clone repository:
```bash
git clone <repository-url>
cd order_managerment_crawl
```

2. Build và chạy service:
```bash
docker-compose up --build
```

3. Service sẽ chạy tại: `http://localhost:5000`

### Sử dụng Docker trực tiếp

1. Build image:
```bash
docker build -t 1688-selenium-service .
```

2. Chạy container:
```bash
docker run -p 5000:5000 --name 1688-selenium 1688-selenium-service
```

## API Endpoints

### 1. Health Check
```
GET /health
```
Kiểm tra trạng thái service.



### 2. Load sản phẩm 1688.com
```
POST /load-1688-product
Content-Type: application/json

{
  "product_id": "948998794646"
}
```

**Parameters:**
- `product_id` (required): ID sản phẩm 1688.com

## Ví dụ sử dụng

### Test với curl

1. Health check:
```bash
curl http://localhost:5000/health
```

2. Load sản phẩm 1688:
```bash
curl -X POST http://localhost:5000/load-1688-product \
  -H "Content-Type: application/json" \
  -d '{"product_id": "948998794646"}'
```

### Test với Python

```python
import requests
import json

# Load trang sản phẩm 1688
url = "http://localhost:5000/load-1688-product"
data = {"product_id": "948998794646"}

response = requests.post(url, json=data)
result = response.json()

print(f"Status: {result['status']}")
print(f"Content length: {result['content_length']}")
print(f"Product ID: {result['product_id']}")
print(f"URL: {result['url']}")
```

## Cấu trúc Response

### Success Response
```json
{
  "status": "success",
  "product_id": "948998794646",
  "url": "https://detail.1688.com/offer/948998794646.html",
  "content": "<!DOCTYPE html>...",
  "content_length": 50000,
  "cookies_used": 15,
  "timestamp": 1703123456.789
}
```

### Error Response
```json
{
  "error": "Error message"
}
```

## Troubleshooting

### Lỗi Chrome Driver
- Kiểm tra logs container: `docker logs 1688-selenium-service`
- Đảm bảo Chrome và ChromeDriver versions tương thích

### Lỗi Memory
- Tăng memory limit cho container trong docker-compose.yml
- Giảm số lượng concurrent requests

### Lỗi Network
- Kiểm tra firewall settings
- Đảm bảo container có thể truy cập internet

## Logs

Logs được lưu trong thư mục `./logs` và có thể xem bằng:
```bash
docker logs -f 1688-selenium-service
```

## Bảo mật

- Service chạy với user `selenium` (không phải root)
- Chỉ expose port 5000
- Sử dụng bridge network để isolate

## Performance

- Mỗi request tạo một Chrome instance mới
- Tự động cleanup resources sau mỗi request
- Health check để monitor service status

