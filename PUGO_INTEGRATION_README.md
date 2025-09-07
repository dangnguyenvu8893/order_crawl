# Tích hợp Pugo.vn Crawler

## Tổng quan

Dự án đã được tích hợp thêm khả năng crawl dữ liệu từ pugo.vn, bổ sung cho khả năng crawl 1688.com hiện có.

## Cấu trúc tích hợp

### 1. Extractor (`py_extractors/extractor_pugo.py`)
- **Chức năng**: Sử dụng Selenium để mô phỏng hành động người dùng trên pugo.vn
- **Tính năng**:
  - Tự động đăng nhập với tài khoản: `vudn8893@gmail.com`
  - Truy cập trang search và điền URL sản phẩm
  - Monitor network requests để lấy response data
  - Hỗ trợ URL: Taobao, 1688, Tmall, pugo.vn

### 2. Transformer (`py_transformers/transformer_pugo.py`)
- **Chức năng**: Chuẩn hóa dữ liệu từ API response
- **Tính năng**:
  - Trích xuất thông tin sản phẩm (tên, giá, hình ảnh)
  - Parse SKU properties và variants
  - Xử lý bảng giá theo số lượng
  - Thông tin người bán

### 3. Parser (`parser_pugo.py`)
- **Chức năng**: Parse chi tiết API response
- **Tính năng**:
  - Phân tích cấu trúc dữ liệu phức tạp
  - Trích xuất thông số kỹ thuật
  - Xử lý mô tả sản phẩm

## API Endpoints mới

### 1. `/extract-pugo` (POST)
```json
{
  "url": "https://detail.1688.com/offer/948414629704.html?offerId=948414629704&spm=a260k.home2025.recommendpart.2"
}
```
**Chức năng**: Crawl raw data từ pugo.vn (hỗ trợ Taobao, 1688, Tmall URLs)

### 2. `/transform-pugo` (POST)
```json
{
  "raw_data": {
    "status": "success",
    "url": "https://item.taobao.com/item.htm?id=970024185525",
    "raw_data": { ... },
    "sourceId": "970024185525",
    "sourceType": "pugo"
  }
}
```
**Chức năng**: Chuẩn hóa dữ liệu raw

### 3. `/transform-pugo-from-url` (POST)
```json
{
  "url": "https://item.taobao.com/item.htm?id=970024185525"
}
```
**Chức năng**: Tự động extract + transform từ URL

### 4. `/parse-pugo` (POST)
```json
{
  "response_data": {
    "status": "success",
    "data": { ... }
  }
}
```
**Chức năng**: Parse API response

## Cách sử dụng

### 1. Chạy server
```bash
python app.py
```

### 2. Test tích hợp
```bash
python test_pugo_integration.py
```

### 3. Sử dụng API
```bash
# Extract raw data
curl -X POST http://localhost:5001/extract-pugo \
  -H "Content-Type: application/json" \
  -d '{"url": "https://item.taobao.com/item.htm?id=970024185525"}'

# Transform từ URL
curl -X POST http://localhost:5001/transform-pugo-from-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://item.taobao.com/item.htm?id=970024185525"}'
```

## Cấu hình

### Thông tin đăng nhập
- **Email**: `thutrang23072012@gmail.com`
- **Password**: `23072012Tinna228@`
- **Login URL**: `https://pugo.vn/dang-nhap`

### API Configuration
- **Base URL**: `https://pugo.vn/item/detail`
- **Required Headers**: `sign`, `Cookie`
- **Method**: GET với query parameter `url`

## Xử lý lỗi

### 1. Đăng nhập thất bại
- Kiểm tra thông tin đăng nhập
- Kiểm tra kết nối mạng
- Kiểm tra trang đăng nhập có thay đổi không

### 2. API call thất bại
- Kiểm tra sign header có hợp lệ không
- Kiểm tra cookie có hết hạn không
- Kiểm tra URL target có hợp lệ không

### 3. Parse lỗi
- Kiểm tra cấu trúc API response
- Cập nhật parser nếu API thay đổi

## Monitoring

### Logs
- Extractor logs: Thông tin đăng nhập và API calls
- Transformer logs: Quá trình chuẩn hóa dữ liệu
- Parser logs: Chi tiết parse dữ liệu

### Test Results
- File `pugo_test_results.json` chứa kết quả test
- Kiểm tra status của từng component

## Lưu ý quan trọng

1. **Sign Header**: Có thể cần cập nhật logic tạo sign header nếu pugo.vn thay đổi
2. **Cookie Expiry**: Session có thể hết hạn, cần refresh định kỳ
3. **Rate Limiting**: Tránh gọi API quá nhiều lần liên tiếp
4. **Stealth Mode**: Sử dụng các kỹ thuật tránh phát hiện bot

## Troubleshooting

### Lỗi thường gặp

1. **"Playwright chưa được cài đặt"**
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **"Đăng nhập thất bại"**
   - Kiểm tra thông tin đăng nhập
   - Kiểm tra trang đăng nhập có thay đổi selector không

3. **"API call failed"**
   - Kiểm tra sign header
   - Kiểm tra cookie validity
   - Kiểm tra URL format

### Debug Mode
Để debug chi tiết, thay đổi `headless=True` thành `headless=False` trong extractor để xem browser hoạt động.

## Tương lai

- [ ] Tự động refresh session
- [ ] Cache sign header và cookie
- [ ] Hỗ trợ multiple accounts
- [ ] Retry mechanism cho failed requests
- [ ] Metrics và monitoring
