#!/bin/bash

# Script khởi động 1688 Selenium Service
echo "🚀 Starting 1688 Selenium Service..."

# Kiểm tra Docker có sẵn không
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p logs

# Dừng và xóa container cũ nếu có
echo "🔄 Cleaning up old containers..."
docker-compose down

# Build và khởi động service
echo "🔨 Building and starting service..."
docker-compose up --build -d

# Chờ service khởi động
echo "⏳ Waiting for service to start..."
sleep 10

# Kiểm tra health
echo "🔍 Checking service health..."
for i in {1..6}; do
    if curl -f http://localhost:5001/health &> /dev/null; then
        echo "✅ Service is healthy and running!"
        echo "🌐 Service URL: http://localhost:5001"
        echo "📖 API Documentation:"
        echo "   - Health check: GET /health"
        echo "   - Load page: POST /load-page"
        echo "   - Load 1688 product: POST /load-1688-product"
        echo ""
        echo "📝 To view logs: docker-compose logs -f"
        echo "🛑 To stop service: docker-compose down"
        exit 0
    fi
    echo "⏳ Waiting for service to be ready... (attempt $i/6)"
    sleep 5
done

echo "❌ Service failed to start properly. Check logs with: docker-compose logs"
exit 1
