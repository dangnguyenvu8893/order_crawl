# Sử dụng Python 3.11 slim image
FROM python:3.11-slim as base

# Cài đặt các dependencies cần thiết cho Selenium
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
    unzip \
    gpg \
    software-properties-common \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
        # Cài đặt ChromeDriver cho AMD64
        CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1-3) && \
        echo "Chrome version: $CHROME_VERSION" && \
        # Sử dụng Chrome for Testing API mới
        CHROMEDRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}") && \
        echo "ChromeDriver version: $CHROMEDRIVER_VERSION" && \
        wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ && \
        chmod +x /usr/local/bin/chromedriver && \
        rm -rf /tmp/chromedriver*; \
    else \
        # Chromium driver đã được cài đặt cùng với chromium package
        echo "Chromium driver already installed"; \
    fi

# Tạo user không phải root và thư mục home
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Copy source code
COPY . .

# Tạo thư mục để lưu logs
RUN mkdir -p /app/logs

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
CMD ["python", "app.py"]
