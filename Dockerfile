# Sử dụng Python 3.11 slim image
FROM python:3.11-slim as base

# Dùng bash để hỗ trợ pipefail
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Cài đặt các dependencies cần thiết cho Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgdk-pixbuf-2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    unzip \
    apt-transport-https \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Tạo thư mục làm việc
WORKDIR /app

# Upgrade pip và setuptools trước khi cài đặt dependencies
RUN pip install --upgrade pip setuptools wheel

# Copy requirements và cài đặt Python dependencies
# Best practice: Copy requirements.txt riêng để tận dụng Docker layer caching
COPY requirements.txt .
# Đảm bảo pip install fail nếu có lỗi và verify installation
# CRITICAL: beautifulsoup4 là dependency bắt buộc cho tracking functionality
# Best practice: Cài đặt beautifulsoup4 riêng biệt để đảm bảo 100% được cài đặt
RUN set -e && \
    echo "=== Installing Python dependencies from requirements.txt ===" && \
    pip install --no-cache-dir --verbose -r requirements.txt && \
    echo "=== Explicitly installing beautifulsoup4 to ensure it's installed ===" && \
    pip install --no-cache-dir --verbose beautifulsoup4==4.12.3 || (echo "CRITICAL ERROR: Failed to install beautifulsoup4 explicitly" && exit 1) && \
    echo "=== Verifying beautifulsoup4 installation ===" && \
    pip show beautifulsoup4 || (echo "CRITICAL ERROR: beautifulsoup4 not found after explicit install" && pip list && exit 1) && \
    python -c "import bs4; print('✓ beautifulsoup4 module imported successfully')" || (echo "CRITICAL ERROR: Cannot import bs4 module" && exit 1) && \
    python -c "from bs4 import BeautifulSoup; print('✓ BeautifulSoup class imported successfully')" || (echo "CRITICAL ERROR: Cannot import BeautifulSoup class" && exit 1) && \
    echo "=== beautifulsoup4 verification completed successfully ==="

# Cài đặt Chrome cho Selenium (multi-arch support)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        # Cài đặt Google Chrome cho AMD64
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && \
        apt-get install -y google-chrome-stable && \
        # Tạo symlink cho google-chrome
        ln -sf /usr/bin/google-chrome-stable /usr/bin/google-chrome; \
    else \
        # For ARM64, use Chromium instead
        apt-get update && \
        apt-get install -y chromium chromium-driver && \
        # Tạo symlink cho chromium
        ln -sf /usr/bin/chromium /usr/bin/google-chrome; \
    fi && \
    rm -rf /var/lib/apt/lists/*

# Cài đặt ChromeDriver (nếu cần)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
        echo "Chrome version: $CHROME_VERSION" && \
        echo "Fetching latest ChromeDriver version..." && \
        CHROMEDRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('channels', {}).get('Stable', {}).get('version', ''))") && \
        if [ -z "$CHROMEDRIVER_VERSION" ]; then \
            echo "Warning: Could not fetch from API, using Chrome version" && \
            CHROMEDRIVER_VERSION=$(echo "$CHROME_VERSION" | cut -d'.' -f1-3); \
        fi && \
        echo "ChromeDriver version to install: $CHROMEDRIVER_VERSION" && \
        DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
        echo "Downloading from: $DOWNLOAD_URL" && \
        wget -q --show-progress -O /tmp/chromedriver.zip "$DOWNLOAD_URL" && \
        unzip -q /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ && \
        chmod +x /usr/local/bin/chromedriver && \
        rm -rf /tmp/chromedriver* && \
        echo "ChromeDriver installed successfully:" && \
        chromedriver --version; \
    else \
        echo "Chromium driver already installed"; \
    fi

# Tạo user không phải root và thư mục home
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Copy source code
COPY . .

# Tạo thư mục để lưu logs và sessions
RUN mkdir -p /app/logs/sessions

# Thay đổi ownership của tất cả files
RUN chown -R appuser:appuser /app

# Thiết lập biến môi trường cho Chrome
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Chuyển sang user appuser
USER appuser

# Expose port khớp với Flask app (5001)
EXPOSE 5001

# Health check khớp cổng 5001
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Command để chạy ứng dụng
# xvfb-run tạo virtual display :99 → Chrome chạy non-headless, bypass Cloudflare bot detection
CMD ["xvfb-run", "--server-num=99", "--server-args=-screen 0 1920x1080x24 -ac", "python", "app.py"]