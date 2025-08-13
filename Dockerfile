# Sử dụng Python 3.11 slim image
FROM python:3.11-slim as base

# Cài đặt các dependencies cần thiết
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Playwright browsers với root user
RUN python -m playwright install chromium

# Tạo user không phải root và thư mục home
RUN groupadd -r playwright && useradd -r -g playwright -m -d /home/playwright playwright

# Tạo thư mục cache cho playwright user
RUN mkdir -p /home/playwright/.cache && chown -R playwright:playwright /home/playwright

# Copy browser binaries từ root cache sang playwright user cache
RUN cp -r /root/.cache/ms-playwright /home/playwright/.cache/ && \
    chown -R playwright:playwright /home/playwright/.cache

# Copy source code
COPY . .

# Tạo thư mục để lưu logs
RUN mkdir -p /app/logs

# Thay đổi ownership của tất cả files
RUN chown -R playwright:playwright /app

# Chuyển sang user playwright
USER playwright

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Command để chạy ứng dụng
CMD ["python", "app.py"]
