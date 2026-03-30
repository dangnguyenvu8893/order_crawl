FROM python:3.11-slim as base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
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
    gpg \
    apt-transport-https \
    xvfb \
    xauth \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel

COPY order_crawl/requirements.txt /app/order_crawl/requirements.txt
RUN set -e && \
    echo "=== Installing Python dependencies from requirements.txt ===" && \
    pip install --no-cache-dir --verbose -r /app/order_crawl/requirements.txt && \
    echo "=== Explicitly installing beautifulsoup4 to ensure it's installed ===" && \
    pip install --no-cache-dir --verbose beautifulsoup4==4.12.3 || (echo "CRITICAL ERROR: Failed to install beautifulsoup4 explicitly" && exit 1) && \
    echo "=== Verifying beautifulsoup4 installation ===" && \
    pip show beautifulsoup4 || (echo "CRITICAL ERROR: beautifulsoup4 not found after explicit install" && pip list && exit 1) && \
    python -c "import bs4; print('beautifulsoup4 module imported successfully')" || (echo "CRITICAL ERROR: Cannot import bs4 module" && exit 1) && \
    python -c "from bs4 import BeautifulSoup; print('BeautifulSoup class imported successfully')" || (echo "CRITICAL ERROR: Cannot import BeautifulSoup class" && exit 1)

RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && \
        apt-get install -y google-chrome-stable && \
        ln -sf /usr/bin/google-chrome-stable /usr/bin/google-chrome; \
    else \
        apt-get update && \
        apt-get install -y chromium chromium-driver && \
        ln -sf /usr/bin/chromium /usr/bin/google-chrome; \
    fi && \
    rm -rf /var/lib/apt/lists/*

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
        ln -sf /usr/local/bin/chromedriver /usr/bin/chromedriver && \
        rm -rf /tmp/chromedriver* && \
        echo "ChromeDriver installed successfully:" && \
        chromedriver --version; \
    else \
        echo "Chromium driver already installed"; \
    fi

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

COPY order_crawl /app/order_crawl

RUN mkdir -p /app/logs /app/logs/sessions /app/order_crawl/logs && \
    chown -R appuser:appuser /app

WORKDIR /app/order_crawl

ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CRAWL_NEW_DIR=/app/order_crawl/crawl_new

USER appuser

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

CMD ["xvfb-run", "--server-num=99", "--server-args=-screen 0 1920x1080x24 -ac", "python", "app.py"]
