from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import logging
import os
import json
import re
import random

app = Flask(__name__)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_browser():
    """Thiết lập Playwright browser với các kỹ thuật bypass anti-bot nâng cao nhất"""
    try:
        playwright = sync_playwright().start()
        
        # Sử dụng các options để bypass anti-bot
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--no-zygote',
                '--disable-logging',
                '--disable-permissions-api',
                '--disable-background-networking',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-domain-reliability',
                '--disable-features=AudioServiceOutOfProcess',
                '--disable-hang-monitor',
                '--disable-prompt-on-repost',
                '--disable-renderer-backgrounding',
                '--disable-sync-preferences',
                '--metrics-recording-only',
                '--safebrowsing-disable-auto-update',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--disable-accelerated-2d-canvas',
                '--disable-3d-apis',
                '--disable-webgl',
                '--disable-threaded-animation',
                '--disable-threaded-scrolling',
                '--disable-in-process-stack-traces',
                '--disable-histogram-customizer',
                '--disable-gl-extensions',
                '--disable-composited-antialiasing',
                '--disable-partial-raster',
                '--disable-skia-runtime-opts',
                '--disable-software-rasterizer',
                '--disable-zero-copy',
                '--disable-gpu-memory-buffer-compositor-resources',
                '--disable-gpu-memory-buffer-video-frames',
                '--disable-gpu-memory-buffer-vaapi',
                '--disable-gpu-sandbox',
                '--disable-accelerated-video-decode',
                '--disable-accelerated-video-encode',
                '--disable-accelerated-mjpeg-decode',
                '--disable-accelerated-video-decode',
                '--disable-accelerated-video-encode',
                '--disable-accelerated-mjpeg-decode',
                '--disable-accelerated-video-decode',
                '--disable-accelerated-video-encode',
                '--disable-accelerated-mjpeg-decode'
            ]
        )
        return playwright, browser
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo browser: {e}")
        return None, None

def create_ultimate_stealth_context(browser):
    """Tạo context với các kỹ thuật stealth tối ưu"""
    # Random user agents từ các browser thực tế
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]
    
    # Random viewport sizes
    viewports = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
        {'width': 1536, 'height': 864}
    ]
    
    context = browser.new_context(
        user_agent=random.choice(user_agents),
        viewport=random.choice(viewports),
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
        extra_http_headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.1688.com/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-full-version': '"120.0.6099.109"',
            'sec-ch-ua-platform-version': '"14.1.2"',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-wow64': '?0'
        }
    )
    
    # Thêm stealth script tối ưu
    context.add_init_script("""
        // Override webdriver property
        Object.defineProperty(navigator, 'webdriver', { 
            get: () => undefined,
            configurable: true
        });
        
        // Override plugins
        Object.defineProperty(navigator, 'plugins', { 
            get: () => [1, 2, 3, 4, 5],
            configurable: true
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', { 
            get: () => ['zh-CN', 'zh', 'en'],
            configurable: true
        });
        
        // Override platform
        Object.defineProperty(navigator, 'platform', { 
            get: () => 'MacIntel',
            configurable: true
        });
        
        // Override hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', { 
            get: () => 8,
            configurable: true
        });
        
        // Override device memory
        Object.defineProperty(navigator, 'deviceMemory', { 
            get: () => 8,
            configurable: true
        });
        
        // Override max touch points
        Object.defineProperty(navigator, 'maxTouchPoints', { 
            get: () => 0,
            configurable: true
        });
        
        // Override vendor
        Object.defineProperty(navigator, 'vendor', { 
            get: () => 'Google Inc.',
            configurable: true
        });
        
        // Override user agent data
        if (navigator.userAgentData) {
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({
                    brands: [
                        {brand: 'Not_A Brand', version: '8'},
                        {brand: 'Chromium', version: '120'},
                        {brand: 'Google Chrome', version: '120'}
                    ],
                    mobile: false,
                    platform: 'macOS'
                }),
                configurable: true
            });
        }
        
        // Override chrome object
        window.chrome = { 
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Override permissions
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' }),
                request: () => Promise.resolve({ state: 'granted' }),
                requestAll: () => Promise.resolve([{ state: 'granted' }])
            }),
            configurable: true
        });
        
        // Override service worker
        if ('serviceWorker' in navigator) {
            Object.defineProperty(navigator, 'serviceWorker', {
                get: () => ({
                    register: () => Promise.resolve({}),
                    getRegistration: () => Promise.resolve({}),
                    getRegistrations: () => Promise.resolve([])
                }),
                configurable: true
            });
        }
        
        // Override canvas fingerprinting
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const context = originalGetContext.call(this, type, ...args);
            if (type === '2d') {
                const originalFillText = context.fillText;
                context.fillText = function(...args) {
                    return originalFillText.apply(this, args);
                };
                
                const originalToDataURL = context.toDataURL;
                context.toDataURL = function(...args) {
                    return originalToDataURL.apply(this, args);
                };
            }
            return context;
        };
        
        // Override WebGL fingerprinting
        if (window.WebGLRenderingContext) {
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                if (parameter === 37447) {
                    return '4.1.0';
                }
                return getParameter.call(this, parameter);
            };
        }
        
        // Override audio fingerprinting
        if (window.AudioContext) {
            const originalGetChannelData = AudioContext.prototype.getChannelData;
            AudioContext.prototype.getChannelData = function(...args) {
                return originalGetChannelData.apply(this, args);
            };
        }
        
        // Override battery API
        if (navigator.getBattery) {
            navigator.getBattery = () => Promise.resolve({
                charging: true,
                chargingTime: Infinity,
                dischargingTime: Infinity,
                level: 0.8
            });
        }
        
        // Override connection API
        if (navigator.connection) {
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                }),
                configurable: true
            });
        }
        
        // Override media devices
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
            navigator.mediaDevices.enumerateDevices = () => Promise.resolve([]);
        }
        
        // Override geolocation
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition = (success) => {
                success({
                    coords: {
                        latitude: 39.9042,
                        longitude: 116.4074,
                        accuracy: 100
                    },
                    timestamp: Date.now()
                });
            };
        }
        
        // Override timezone
        if (Intl) {
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(...args) {
                if (args.length > 0 && args[0] === 'Asia/Shanghai') {
                    return new originalDateTimeFormat('en-US', { timeZone: 'America/New_York' });
                }
                return new originalDateTimeFormat(...args);
            };
        }
        
        // Override performance timing
        if (window.performance && window.performance.timing) {
            const timing = window.performance.timing;
            timing.navigationStart = Date.now() - Math.random() * 1000;
            timing.loadEventEnd = Date.now();
        }
        
        // Override console methods to avoid detection
        const originalLog = console.log;
        const originalWarn = console.warn;
        const originalError = console.error;
        
        console.log = function(...args) {
            if (args[0] && typeof args[0] === 'string' && args[0].includes('webdriver')) {
                return;
            }
            return originalLog.apply(this, args);
        };
        
        console.warn = function(...args) {
            if (args[0] && typeof args[0] === 'string' && args[0].includes('webdriver')) {
                return;
            }
            return originalWarn.apply(this, args);
        };
        
        console.error = function(...args) {
            if (args[0] && typeof args[0] === 'string' && args[0].includes('webdriver')) {
                return;
            }
            return originalError.apply(this, args);
        };
    """)
    
    return context

def extract_1688_data(page_content):
    """Trích xuất dữ liệu từ trang 1688.com"""
    try:
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Tìm script chứa dữ liệu sản phẩm
        scripts = soup.find_all('script')
        product_data = None
        
        for script in scripts:
            if script.string and 'window.context' in script.string:
                script_content = script.string
                match = re.search(r'window\.context\s*=\s*({.*?});', script_content, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        if 'result' in data and 'data' in data['result']:
                            product_data = data['result']['data']
                            break
                    except json.JSONDecodeError:
                        continue
        
        if product_data:
            result = {
                "status": "success",
                "extracted_data": True,
                "product_info": {}
            }
            
            # Thông tin cơ bản
            if 'productTitle' in product_data:
                title_data = product_data['productTitle']['fields']
                result["product_info"]["title"] = title_data.get('title', '')
                result["product_info"]["sale_count"] = title_data.get('saleNum', '')
                result["product_info"]["unit"] = title_data.get('unit', '')
            
            # Thông tin giá
            if 'mainPrice' in product_data:
                price_data = product_data['mainPrice']['fields']
                if 'priceModel' in price_data:
                    price_model = price_data['priceModel']
                    result["product_info"]["price_range"] = price_model.get('priceDisplay', '')
                    result["product_info"]["current_prices"] = price_model.get('currentPrices', [])
            
            # Thông tin hình ảnh
            if 'gallery' in product_data:
                gallery_data = product_data['gallery']['fields']
                result["product_info"]["images"] = gallery_data.get('offerImgList', [])
                result["product_info"]["subject"] = gallery_data.get('subject', '')
            
            # Thông tin SKU
            if 'skuSelection' in product_data:
                sku_data = product_data['skuSelection']['fields']
                result["product_info"]["sku_info"] = sku_data
            
            # Thông tin vận chuyển
            if 'shippingServices' in product_data:
                shipping_data = product_data['shippingServices']['fields']
                result["product_info"]["shipping"] = {
                    "delivery_fee": shipping_data.get('deliveryFee', ''),
                    "location": shipping_data.get('location', ''),
                    "delivery_limit": shipping_data.get('deliveryLimitText', '')
                }
            
            # Thông tin bảo vệ người mua
            if 'mainServices' in product_data:
                services_data = product_data['mainServices']['fields']
                result["product_info"]["buyer_protection"] = services_data.get('guaranteeList', [])
            
            # Thông tin chi tiết sản phẩm
            if 'detailDescription' in product_data:
                detail_data = product_data['detailDescription']
                result["product_info"]["detail"] = {
                    "brand": detail_data.get('texts', {}).get('brandName', ''),
                    "category": detail_data.get('leafCategoryName', ''),
                    "company": detail_data.get('sellerModel', {}).get('companyName', ''),
                    "feature_attributes": detail_data.get('featureAttributes', [])
                }
            
            return result
        else:
            return extract_from_html(soup)
            
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất dữ liệu: {e}")
        return {"status": "error", "message": str(e)}

def extract_from_html(soup):
    """Trích xuất dữ liệu từ HTML khi không có script data"""
    try:
        result = {
            "status": "success",
            "extracted_data": False,
            "html_data": {}
        }
        
        # Tìm title
        title = soup.find('title')
        if title:
            result["html_data"]["title"] = title.get_text().strip()
        
        # Tìm tất cả text content
        text_content = soup.get_text(separator=' ', strip=True)
        result["html_data"]["content"] = text_content[:2000] + "..." if len(text_content) > 2000 else text_content
        
        # Tìm tất cả links
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        result["html_data"]["links"] = links[:20]
        
        # Tìm tất cả images
        images = [img.get('src') for img in soup.find_all('img', src=True)]
        result["html_data"]["images"] = images[:20]
        
        return result
        
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất từ HTML: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Ultimate Stealth Playwright service is running"})

@app.route('/load-1688-product', methods=['POST'])
def load_1688_product():
    """API endpoint đặc biệt để load sản phẩm 1688.com với ultimate stealth mode"""
    try:
        data = request.get_json()
        if not data or 'product_id' not in data:
            return jsonify({"error": "Product ID is required"}), 400
        
        product_id = data['product_id']
        url = f"https://detail.1688.com/offer/{product_id}.html"
        
        logger.info(f"Bắt đầu load sản phẩm 1688 với ultimate stealth mode: {product_id}")
        
        # Khởi tạo browser
        playwright, browser = setup_browser()
        if not browser:
            return jsonify({"error": "Không thể khởi tạo browser"}), 500
        
        try:
            # Tạo ultimate stealth context
            context = create_ultimate_stealth_context(browser)
            page = context.new_page()
            
            # Load trang với ultimate stealth mode
            page.goto(url, wait_until='domcontentloaded', timeout=120000)
            logger.info(f"Đã load trang sản phẩm thành công: {url}")
            
            # Chờ trang load hoàn toàn
            time.sleep(30)
            
            # Chờ thêm để đảm bảo JavaScript đã chạy xong
            try:
                page.wait_for_load_state('networkidle', timeout=60000)
            except:
                logger.warning("Network idle timeout, tiếp tục với content hiện tại")
            
            # Chờ thêm một chút để đảm bảo dữ liệu đã load
            time.sleep(10)
            
            # Lấy page content
            page_content = page.content()
            
            # Trích xuất dữ liệu
            result = extract_1688_data(page_content)
            result["product_id"] = product_id
            result["url"] = url
            result["timestamp"] = time.time()
            
            logger.info(f"Load sản phẩm 1688 thành công: {product_id}")
            return jsonify(result)
            
        finally:
            # Đóng browser và playwright
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            logger.info("Đã đóng browser")
            
    except Exception as e:
        logger.error(f"Lỗi khi load sản phẩm 1688: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
