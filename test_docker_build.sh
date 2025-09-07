#!/bin/bash

# Script để test Docker build cho pugo.vn integration

echo "=== TEST DOCKER BUILD FOR PUGO.VN INTEGRATION ==="

# Kiểm tra Docker daemon
echo "1. Checking Docker daemon..."
if ! docker info > /dev/null 2>&1; then
    echo "   ❌ Docker daemon không chạy. Vui lòng start Docker Desktop"
    echo "   Hoặc chạy: sudo systemctl start docker"
    exit 1
fi
echo "   ✅ Docker daemon đang chạy"

# Build Docker image
echo "2. Building Docker image..."
if docker build -t order-management-crawler .; then
    echo "   ✅ Docker image build thành công"
else
    echo "   ❌ Docker image build thất bại"
    exit 1
fi

# Test Docker container
echo "3. Testing Docker container..."
if docker run --rm -d --name test-crawler -p 5001:5001 order-management-crawler; then
    echo "   ✅ Docker container start thành công"
    
    # Chờ container khởi động
    echo "   Waiting for container to start..."
    sleep 10
    
    # Test health check
    echo "4. Testing health check..."
    if curl -f http://localhost:5001/health > /dev/null 2>&1; then
        echo "   ✅ Health check passed"
    else
        echo "   ❌ Health check failed"
    fi
    
    # Test pugo endpoint
    echo "5. Testing pugo endpoint..."
    response=$(curl -s -X POST http://localhost:5001/extract-pugo \
        -H "Content-Type: application/json" \
        -d '{"url": "https://detail.1688.com/offer/948414629704.html?offerId=948414629704&spm=a260k.home2025.recommendpart.2"}' \
        -w "%{http_code}")
    
    if [[ "$response" == *"200" ]]; then
        echo "   ✅ Pugo endpoint hoạt động"
    else
        echo "   ❌ Pugo endpoint không hoạt động"
    fi
    
    # Stop container
    echo "6. Stopping test container..."
    docker stop test-crawler
    echo "   ✅ Container stopped"
    
else
    echo "   ❌ Docker container start thất bại"
    exit 1
fi

echo ""
echo "🎉 DOCKER BUILD TEST COMPLETED SUCCESSFULLY!"
echo ""
echo "Để chạy production:"
echo "1. docker-compose up -d"
echo "2. Truy cập: http://localhost:5001"
echo ""
echo "Để xem logs:"
echo "docker-compose logs -f"
