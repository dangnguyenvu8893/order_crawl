# PowerShell script để chạy Docker container trên Windows
# Sử dụng: .\run-docker.ps1

Write-Host "=== Docker Run Script cho Order Management Crawler ===" -ForegroundColor Green

# Tên image và container
$IMAGE_NAME = "order-management-crawler:latest"
$CONTAINER_NAME = "order-crawler"
$PORT = "5001"

# Kiểm tra container đã tồn tại chưa
$existingContainer = docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}"

if ($existingContainer -eq $CONTAINER_NAME) {
    Write-Host "Container '$CONTAINER_NAME' đã tồn tại. Đang dừng và xóa..." -ForegroundColor Yellow
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
}

# Chạy container mới
Write-Host "Đang chạy container mới..." -ForegroundColor Yellow
try {
    docker run -d `
        --name $CONTAINER_NAME `
        -p "${PORT}:5001" `
        --restart unless-stopped `
        $IMAGE_NAME
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Container đã chạy thành công!" -ForegroundColor Green
        
        # Chờ một chút để container khởi động
        Write-Host "Đang chờ container khởi động..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        
        # Kiểm tra health
        Write-Host "`n=== Kiểm tra Health ===" -ForegroundColor Cyan
        try {
            $healthResponse = Invoke-RestMethod -Uri "http://localhost:$PORT/health" -Method GET
            Write-Host "✅ Health check: $($healthResponse.message)" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ Health check thất bại, nhưng container có thể vẫn đang khởi động..." -ForegroundColor Yellow
        }
        
        Write-Host "`n=== Thông tin Container ===" -ForegroundColor Cyan
        docker ps --filter "name=$CONTAINER_NAME"
        
        Write-Host "`n=== Các endpoint có sẵn ===" -ForegroundColor Cyan
        Write-Host "• Health check: http://localhost:$PORT/health" -ForegroundColor White
        Write-Host "• Swagger UI: http://localhost:$PORT/swagger" -ForegroundColor White
        Write-Host "• Extract 1688: POST http://localhost:$PORT/extract-1688" -ForegroundColor White
        Write-Host "• Extract Pugo: POST http://localhost:$PORT/extract-pugo" -ForegroundColor White
        
        Write-Host "`n=== Các lệnh hữu ích ===" -ForegroundColor Cyan
        Write-Host "• Xem logs: docker logs $CONTAINER_NAME" -ForegroundColor White
        Write-Host "• Dừng container: docker stop $CONTAINER_NAME" -ForegroundColor White
        Write-Host "• Xóa container: docker rm $CONTAINER_NAME" -ForegroundColor White
        
    } else {
        Write-Host "❌ Không thể chạy container!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Lỗi khi chạy container: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Container đã sẵn sàng ===" -ForegroundColor Green
