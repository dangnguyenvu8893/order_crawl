# Docker Guide - Pugo.vn Integration

## 🐳 **Docker Setup**

### ✅ **Đã cập nhật:**

1. **Dockerfile** - Chuyển từ Playwright sang Selenium
2. **docker-compose.yml** - Cập nhật tên service và network
3. **requirements.txt** - Thêm Selenium, xóa Playwright

### 🔧 **Cấu hình Docker:**

#### **Dockerfile:**
- **Base Image**: Python 3.11-slim
- **Browser**: Google Chrome + ChromeDriver
- **User**: appuser (non-root)
- **Port**: 5001
- **Health Check**: `/health` endpoint

#### **docker-compose.yml:**
- **Service**: crawler-service
- **Container**: order-management-crawler
- **Network**: crawler-network
- **Volumes**: logs directory

## 🚀 **Cách sử dụng:**

### **1. Test Docker Compatibility:**
```bash
python test_docker_compatibility.py
```

### **2. Build Docker Image:**
```bash
docker build -t order-management-crawler .
```

### **3. Test Docker Build:**
```bash
./test_docker_build.sh
```

### **4. Chạy Production:**
```bash
docker-compose up -d
```

### **5. Xem Logs:**
```bash
docker-compose logs -f
```

### **6. Stop Service:**
```bash
docker-compose down
```

## 📊 **Test Results:**

### ✅ **Compatibility Test:**
```
✅ Selenium import thành công
✅ Chrome driver hoạt động
✅ Extractor khởi tạo thành công
✅ Can handle: 1688, Taobao, Tmall, pugo.vn URLs
✅ Flask app import thành công
✅ Dockerfile syntax OK
```

### 🔍 **Docker Features:**

1. **Headless Chrome** - Chạy browser không giao diện
2. **Security** - Non-root user
3. **Health Check** - Tự động kiểm tra sức khỏe
4. **Logging** - Volume mount cho logs
5. **Network** - Isolated network

## ⚠️ **Lưu ý:**

1. **Docker Daemon** - Cần chạy Docker Desktop hoặc Docker daemon
2. **Chrome Dependencies** - Đã cài đặt đầy đủ dependencies
3. **Memory** - Chrome cần ít nhất 512MB RAM
4. **Port** - Đảm bảo port 5001 không bị chiếm

## 🐛 **Troubleshooting:**

### **Docker daemon không chạy:**
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

### **Build thất bại:**
```bash
# Xóa cache và build lại
docker system prune -f
docker build --no-cache -t order-management-crawler .
```

### **Container không start:**
```bash
# Xem logs
docker-compose logs

# Check health
curl http://localhost:5001/health
```

## 📈 **Performance:**

- **Build Time**: ~5-10 phút (lần đầu)
- **Startup Time**: ~30-60 giây
- **Memory Usage**: ~200-500MB
- **CPU Usage**: Low (chỉ khi crawl)

## 🔒 **Security:**

- **Non-root user**: appuser
- **Isolated network**: crawler-network
- **No exposed ports**: Chỉ port 5001
- **Health checks**: Tự động restart nếu lỗi
