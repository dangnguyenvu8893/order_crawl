# Standard library imports
import json
import logging
import os
import pickle
import random
import re
import time
import uuid
from typing import Dict, Any, Tuple, Optional

# Third-party imports
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flasgger import Swagger, swag_from
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Local application imports
from parser_1688 import parser_1688
from parser_nhaphangchina import parser_nhaphangchina
from parser_pugo import parser_pugo

# from playwright.sync_api import sync_playwright  # Removed - using Selenium now

app = Flask(__name__)
# Cấu hình Swagger: tắt nút "Try it out" bằng cách vô hiệu hoá submit methods
app.config['SWAGGER'] = {
    'uiversion': 3,
    'swagger_ui': True,
    # Bật Try it out mặc định và cho phép chỉnh input/submit ngay
    'swagger_ui_config': {
        'supportedSubmitMethods': ['get', 'post', 'put', 'delete', 'patch', 'options', 'head'],
        'tryItOutEnabled': True,
        'persistAuthorization': True,
        'defaultModelsExpandDepth': -1,
        'displayOperationId': True
    }
}
# Đổi đường dẫn Swagger UI từ /apidocs sang /swagger
swagger = Swagger(app, config={
    'headers': [],
    'specs': [
        {
            'endpoint': 'apispec_1',
            'route': '/apispec_1.json',
            'rule_filter': lambda rule: True,
            'model_filter': lambda tag: True,
        }
    ],
    'static_url_path': '/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/swagger'
})

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lưu trữ cookies và sessions
COOKIES_FILE = "1688_cookies.pkl"
SESSIONS_FILE = "1688_sessions.pkl"

def load_cookies():
    """Load cookies đã lưu từ file"""
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        logger.error(f"Lỗi khi load cookies: {e}")
    return []

def save_cookies(cookies):
    """Lưu cookies vào file"""
    try:
        with open(COOKIES_FILE, 'wb') as f:
            pickle.dump(cookies, f)
        logger.info(f"Đã lưu {len(cookies)} cookies")
    except Exception as e:
        logger.error(f"Lỗi khi lưu cookies: {e}")

def load_sessions():
    """Load sessions đã lưu từ file"""
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        logger.error(f"Lỗi khi load sessions: {e}")
    return {}

def save_sessions(sessions):
    """Lưu sessions vào file"""
    try:
        with open(SESSIONS_FILE, 'wb') as f:
            pickle.dump(sessions, f)
        logger.info(f"Đã lưu {len(sessions)} sessions")
    except Exception as e:
        logger.error(f"Lỗi khi lưu sessions: {e}")

def generate_fake_cookies_17track():
    """Tạo fake cookies cho 17track.net dựa trên cookies thực tế để tránh tooltip"""
    cookies = []
    
    # Cookies quan trọng từ 17track.net (dựa trên cookies thực tế)
    current_time = int(time.time())
    random_uuid = str(uuid.uuid4())
    random_ga_id = random.randint(100000000, 999999999)
    
    base_cookies = [
        # Session cookie (quan trọng - giúp tránh bị coi là user mới)
        {
            'name': '__AP_SESSION__',
            'value': random_uuid.replace('-', ''),
            'domain': 't.17track.net',
            'path': '/'
        },
        # Google Analytics cookies (fake format tương tự)
        {
            'name': '_ga',
            'value': f'GA1.1.{random_ga_id}.{current_time}',
            'domain': '.17track.net',
            'path': '/'
        },
        {
            'name': '_ga_DFLC2LRX2J',
            'value': f'GS2.1.s{current_time}$o5$g1$t{current_time}$j60$l1$h{random.randint(1000000000, 9999999999)}',
            'domain': '.17track.net',
            'path': '/'
        },
        # Tracking cookies
        {
            'name': '_im_vid',
            'value': ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=26)),
            'domain': 't.17track.net',
            'path': '/'
        },
        {
            'name': '_pubcid',
            'value': str(uuid.uuid4()),
            'domain': '.17track.net',
            'path': '/'
        },
        {
            'name': '_gcl_au',
            'value': f'1.1.{random.randint(1000000000, 9999999999)}.{current_time}',
            'domain': '.17track.net',
            'path': '/'
        },
        # Cookies để tránh tooltip (thử các tên có thể)
        {
            'name': 'joyride',
            'value': 'completed',
            'domain': '.17track.net',
            'path': '/'
        },
        {
            'name': 'has_seen_welcome',
            'value': 'true',
            'domain': '.17track.net',
            'path': '/'
        }
    ]
    
    # Thêm cookies ngẫu nhiên để mỗi request khác nhau (mô phỏng tracking cookies)
    for _ in range(random.randint(2, 5)):
        cookie_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(8, 15)))
        cookie_value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=random.randint(10, 30)))
        cookies.append({
            'name': cookie_name,
            'value': cookie_value,
            'domain': '.17track.net',
            'path': '/'
        })
    
    cookies.extend(base_cookies)
    return cookies

def generate_fake_cookies():
    """Tạo fake cookies để bypass anti-bot"""
    cookies = []
    
    # Cookie cơ bản cho 1688.com
    base_cookies = [
        {
            'name': 'cna',
            'value': ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=22)),
            'domain': '.1688.com',
            'path': '/'
        },
        {
            'name': 'xlly_s',
            'value': ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=32)),
            'domain': '.1688.com',
            'path': '/'
        },
        {
            'name': 'ali_apache_id',
            'value': f"{random.randint(1000000000, 9999999999)}.{int(time.time())}",
            'domain': '.1688.com',
            'path': '/'
        }
    ]

    # Thêm cookies ngẫu nhiên
    for i in range(random.randint(5, 15)):
        cookie_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(8, 15)))
        cookie_value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=random.randint(10, 30)))
        cookies.append({
            'name': cookie_name,
            'value': cookie_value,
            'domain': '.1688.com',
            'path': '/'
        })

    cookies.extend(base_cookies)
    return cookies

# def setup_browser():
#     """Thiết lập Playwright browser - DISABLED, using Selenium now"""
#     return None, None

def create_stealth_context(browser, use_saved_cookies=True):
    """Tạo context với stealth mode"""
    # Load cookies đã lưu hoặc tạo mới
    if use_saved_cookies:
        cookies = load_cookies()
        if not cookies:
            cookies = generate_fake_cookies()
            save_cookies(cookies)
    else:
        cookies = generate_fake_cookies()

    # Tạo context với stealth mode
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={'width': 1920, 'height': 1080},
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
        extra_http_headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.1688.com/'
        }
    )

    # Thêm cookies vào context
    for cookie in cookies:
        try:
            context.add_cookies([cookie])
        except Exception as e:
            logger.warning(f"Không thể thêm cookie {cookie['name']}: {e}")

    # Thêm stealth script nâng cao
    context.add_init_script("""
        // Override webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        window.chrome = { runtime: {} };

        // Override canvas fingerprinting
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const context = originalGetContext.call(this, type, ...args);
            if (type === '2d') {
                const originalFillText = context.fillText;
                context.fillText = function(...args) {
                    return originalFillText.apply(this, args);
                };
            }
            return context;
        };

        // Override WebGL fingerprinting
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel(R) Iris(TM) Graphics 6100';
            }
            return getParameter.call(this, parameter);
        };

        // Override Audio fingerprinting
        if (window.AudioContext || window.webkitAudioContext) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            const originalGetChannelData = AudioContext.prototype.getChannelData;
            AudioContext.prototype.getChannelData = function(...args) {
                const channelData = originalGetChannelData.apply(this, args);
                return channelData;
            };
        }

        // Override permissions
        const originalQuery = navigator.permissions.query;
        navigator.permissions.query = function(parameters) {
            return Promise.resolve({ state: 'granted' });
        };

        // Override service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register = function() {
                return Promise.resolve({});
            };
        }

        // Override battery API
        if ('getBattery' in navigator) {
            navigator.getBattery = function() {
                return Promise.resolve({
                    charging: true,
                    chargingTime: Infinity,
                    dischargingTime: Infinity,
                    level: 0.85
                });
            };
        }

        // Override connection API
        if ('connection' in navigator) {
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
        }

        // Override geolocation
        if ('geolocation' in navigator) {
            navigator.geolocation.getCurrentPosition = function(success) {
                success({
                    coords: {
                        latitude: 39.9042,
                        longitude: 116.4074,
                        accuracy: 100
                    }
                });
            };
        }

        // Override timezone
        const originalDateTimeFormat = Intl.DateTimeFormat;
        Intl.DateTimeFormat = function(...args) {
            if (args.length === 0) {
                args = ['zh-CN', { timeZone: 'Asia/Shanghai' }];
            }
            return new originalDateTimeFormat(...args);
        };

        // Override performance timing
        if (window.performance && window.performance.timing) {
            const timing = window.performance.timing;
            timing.navigationStart = Date.now() - Math.random() * 1000;
        }

        // Override console methods
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

        // Override localStorage and sessionStorage
        const originalSetItem = Storage.prototype.setItem;
        Storage.prototype.setItem = function(key, value) {
            if (key.includes('webdriver') || key.includes('bot')) {
                return;
            }
            return originalSetItem.call(this, key, value);
        };
    """)

    return context

# def create_session_and_cookies():
#     """Tạo session mới và cookies - DISABLED, using Selenium now"""
#     return None, None, None

def get_page_content(page_content):
    """Lấy thông tin cơ bản về trang web"""
    try:
        return {
            "status": "success",
            "content_length": len(page_content)
        }
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin trang: {e}")
        return {"status": "error", "message": str(e)}

def _build_chrome_driver(headless: bool = True):
    """Khởi tạo Chrome WebDriver headless với cấu hình chống bot nhẹ.
    
    Args:
        headless: Chạy browser ở chế độ headless hay không
        
    Returns:
        webdriver.Chrome: Chrome WebDriver instance
    """
    options = ChromeOptions()
    # Base options (theo pattern Pugo) - flags để tránh crash
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  # Tránh /dev/shm issues
    options.add_argument("--disable-gpu")  # Tránh GPU issues trong headless
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=vi-VN,vi")
    
    # Stealth options để bypass Cloudflare (best practices 2024)
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--exclude-switches=enable-automation")
    options.add_argument("--use-automation-extension=false")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-component-extensions-with-background-pages")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Headers để giống browser thật
    options.add_argument("--accept-lang=en-US,en;q=0.9,vi;q=0.8")
    
    # Headless mode (theo pattern Pugo - dùng --headless cũ ổn định hơn)
    if headless:
        options.add_argument("--headless")
        # Thêm user data dir để tránh conflict (theo pattern Pugo)
        # Tạo directory nếu chưa có
        import os
        user_data_dir = "/tmp/chrome-user-data"
        try:
            os.makedirs(user_data_dir, exist_ok=True)
        except Exception:
            pass  # Ignore nếu không tạo được
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--remote-debugging-port=0")
    
    # Logging setup (theo pattern Pugo)
    options.add_argument("--enable-logging")
    options.add_argument("--log-level=0")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    # Experimental options (theo pattern Pugo)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Set page load strategy
    options.page_load_strategy = 'normal'

    # Khởi tạo driver với fallback (theo pattern Pugo)
    driver = None
    try:
        logger.info("Đang khởi tạo Chrome driver...")
        # Thử với ChromeDriver
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome driver đã khởi tạo thành công")
    except Exception as e:
        logger.warning(f"Chrome driver failed: {e}, trying Chromium...")
        try:
            # Thử với Chromium
            options.binary_location = "/usr/bin/chromium"
            driver = webdriver.Chrome(options=options)
            logger.info("Chromium driver đã khởi tạo thành công")
        except Exception as e2:
            logger.error(f"Both Chrome and Chromium failed: {e2}")
            raise Exception(f"Không thể khởi tạo browser: {e2}")
    
    # Set timeouts
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    driver.implicitly_wait(10)
    
    # Enable network domain để monitor requests (theo pattern Pugo)
    try:
        driver.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    
    # Stealth script nâng cao để bypass Cloudflare (theo best practices 2024)
    try:
        stealth_script = """
        // Override webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // Override navigator properties để giống browser thật
        Object.defineProperty(navigator, 'plugins', { 
            get: () => [1, 2, 3, 4, 5] 
        });
        Object.defineProperty(navigator, 'languages', { 
            get: () => ['en-US', 'en', 'vi'] 
        });
        Object.defineProperty(navigator, 'platform', { 
            get: () => 'Win32' 
        });
        Object.defineProperty(navigator, 'hardwareConcurrency', { 
            get: () => 8 
        });
        Object.defineProperty(navigator, 'deviceMemory', { 
            get: () => 8 
        });
        
        // Thêm window.chrome để giống Chrome thật
        window.chrome = { 
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Override permissions API
        const originalQuery = navigator.permissions.query;
        navigator.permissions.query = function(parameters) {
            return Promise.resolve({ state: 'granted' });
        };
        
        // Override battery API
        if ('getBattery' in navigator) {
            navigator.getBattery = function() {
                return Promise.resolve({
                    charging: true,
                    chargingTime: Infinity,
                    dischargingTime: Infinity,
                    level: 1
                });
            };
        }
        
        // Override connection API
        if ('connection' in navigator) {
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
        }
        
        // Override WebGL để tránh fingerprinting
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel(R) Iris(TM) Graphics 6100';
            }
            return getParameter.call(this, parameter);
        };
        
        // Override canvas fingerprinting
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const context = originalGetContext.call(this, type, ...args);
            if (type === '2d') {
                const originalFillText = context.fillText;
                context.fillText = function(...args) {
                    return originalFillText.apply(this, args);
                };
            }
            return context;
        };
        
        // Override console để ẩn webdriver traces
        const originalLog = console.log;
        console.log = function(...args) {
            if (args[0] && typeof args[0] === 'string' && args[0].includes('webdriver')) {
                return;
            }
            return originalLog.apply(this, args);
        };
        
        // Override localStorage để ẩn webdriver traces
        const originalSetItem = localStorage.setItem;
        localStorage.setItem = function(key, value) {
            if (key.includes('webdriver') || key.includes('bot')) {
                return;
            }
            return originalSetItem.call(this, key, value);
        };
        """
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": stealth_script
        })
        logger.info("Đã áp dụng stealth script nâng cao để bypass Cloudflare")
    except Exception as e:
        logger.warning(f"Không thể áp dụng stealth script: {e}")
    
    # Thêm CDP commands để cải thiện stealth
    try:
        # Override User-Agent Client Hints
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "acceptLanguage": "en-US,en;q=0.9,vi;q=0.8",
            "platform": "Windows"
        })
        
        # Override permissions
        driver.execute_cdp_cmd('Browser.grantPermissions', {
            "origin": "https://www.17track.net",
            "permissions": ["geolocation", "notifications"]
        })
        
        logger.info("Đã cấu hình CDP commands để bypass Cloudflare")
    except Exception as e:
        logger.warning(f"Không thể cấu hình CDP commands: {e}")
    
    return driver

def _parse_tracking_html(html: str, tracking_number: str) -> Dict[str, Any]:
    """Parse HTML trả về cấu trúc timeline; xác thực tiêu đề có chứa mã vận đơn."""
    soup = BeautifulSoup(html, 'html.parser')
    shipping = soup.select_one('#shippingContent') or soup
    title_span = shipping.select_one('span.text-result.gradient-border')
    matched = False
    if title_span and tracking_number:
        matched = tracking_number in title_span.get_text(strip=True)

    timeline = []
    for li in shipping.select('ul.timeline_tracking li.event'):
        city_el = li.select_one('span > b')
        info_divs = li.select('div')
        primary_text = info_divs[0].get_text(strip=True) if info_divs else ''
        context_el = li.select_one('.context')
        city = city_el.get_text(strip=True) if city_el else ''
        status_text = primary_text
        context = context_el.get_text(strip=True) if context_el else None
        timeline.append({
            'city': city,
            'status': status_text,
            'context': context
        })

    return {
        'trackingNumber': tracking_number,
        'matched': matched,
        'timeline': timeline,
        'rawHtml': str(shipping)
    }

def _sanitize_raw_html(html: str) -> str:
    """Làm sạch HTML: bỏ script/style, sự kiện on*, javascript: URL."""
    soup = BeautifulSoup(html or '', 'html.parser')
    # Remove script and style tags completely
    for tag in soup(['script', 'style', 'iframe', 'object', 'embed']):
        tag.decompose()
    # Remove event handler attributes and javascript: links
    for tag in soup.find_all(True):
        # Remove on* attributes
        attrs = dict(tag.attrs)
        for attr in list(attrs.keys()):
            if attr.lower().startswith('on'):
                del tag.attrs[attr]
        # Sanitize href/src
        for attr in ('href', 'src'):
            val = tag.get(attr)
            if isinstance(val, str) and val.strip().lower().startswith('javascript:'):
                del tag.attrs[attr]
    return str(soup)

# ==================== 17TRACK.NET HELPER FUNCTIONS ====================

def _extract_17track_timeline_html(html: str, tracking_number: str) -> str:
    """
    Extract chỉ phần timeline HTML từ page source để render trực tiếp.
    Ưu tiên phương án này vì đơn giản và giữ nguyên styling.
    
    Args:
        html: HTML content từ 17track.net sau khi đã translation
        tracking_number: Mã vận đơn để validate
        
    Returns:
        str: HTML của timeline container (đầy đủ tất cả events)
    """
    soup = BeautifulSoup(html, 'html.parser')
    timeline_html = ''
    
    logger.info(f"Bắt đầu extract timeline HTML cho tracking number: {tracking_number}")
    
    # BƯỚC 1: Tìm tất cả span.yq-time để đảm bảo có events
    time_elements = soup.select('span.yq-time')
    logger.info(f"Tìm thấy {len(time_elements)} events (span.yq-time)")
    
    if not time_elements:
        logger.warning("Không tìm thấy events nào (không có span.yq-time)")
        return ''
    
    # BƯỚC 2: Tìm TẤT CẢ containers có events (mỗi carrier có div.relative riêng)
    # Strategy: Tìm tất cả div.relative có events và merge lại
    all_containers_with_events = []
    
    relative_divs = soup.select('div.relative')
    logger.info(f"Tìm thấy {len(relative_divs)} div.relative")
    
    for div in relative_divs:
        events_count = len(div.select('span.yq-time'))
        if events_count > 0:
            all_containers_with_events.append({
                'container': div,
                'events_count': events_count
            })
            logger.info(f"Tìm thấy container với {events_count} events")
    
    # BƯỚC 2.5: Kiểm tra xem có events nào không nằm trong div.relative không (ví dụ: Sync Time events)
    # Nếu số events trong div.relative < tổng số events, có thể có events ở nơi khác
    total_events_in_relative = sum(c['events_count'] for c in all_containers_with_events)
    if total_events_in_relative < len(time_elements):
        missing_events = len(time_elements) - total_events_in_relative
        logger.warning(f"Có {missing_events} events không nằm trong div.relative, có thể là Sync Time events hoặc events từ phần khác")
        
        # Tìm parent containers của các events không nằm trong div.relative
        for time_el in time_elements:
            # Kiểm tra xem event này đã nằm trong container nào chưa
            found_in_container = False
            for container_info in all_containers_with_events:
                if time_el in container_info['container'].select('span.yq-time'):
                    found_in_container = True
                    break
            
            if not found_in_container:
                # Tìm parent container của event này
                parent = time_el.find_parent('div', class_=lambda x: x and 'relative' in str(x))
                if not parent:
                    # Thử tìm parent khác (có thể là div khác)
                    parent = time_el.find_parent(['div', 'section', 'article'])
                    if parent:
                        # Kiểm tra xem parent này có chứa nhiều events không
                        events_in_parent = len(parent.select('span.yq-time'))
                        if events_in_parent > 0:
                            # Thêm vào danh sách containers
                            all_containers_with_events.append({
                                'container': parent,
                                'events_count': events_in_parent
                            })
                            logger.info(f"Tìm thấy container bổ sung với {events_in_parent} events (không phải div.relative)")
    
    # Sắp xếp theo số lượng events (nhiều nhất trước)
    all_containers_with_events.sort(key=lambda x: x['events_count'], reverse=True)
    
    # BƯỚC 3: Extract HTML - LUÔN merge tất cả containers có events (không chỉ lấy container lớn nhất)
    if all_containers_with_events:
        # LUÔN merge tất cả containers để đảm bảo lấy đầy đủ events từ tất cả carriers
        logger.info(f"Có {len(all_containers_with_events)} containers với events, merge tất cả để lấy đầy đủ...")
        
        # Tạo container mới chứa tất cả events
        merged_html_parts = []
        total_events = 0
        seen_events = set()  # Track events đã thêm để tránh duplicate
        
        for container_info in all_containers_with_events:
            container = container_info['container']
            events_in_container = container.select('span.yq-time')
            
            # Kiểm tra xem có events nào chưa được thêm chưa
            new_events_count = 0
            for event in events_in_container:
                event_id = id(event)  # Dùng id để track unique events
                if event_id not in seen_events:
                    seen_events.add(event_id)
                    new_events_count += 1
            
            if new_events_count > 0:
                total_events += len(events_in_container)
                # Lấy HTML của container này
                merged_html_parts.append(str(container))
                logger.info(f"Thêm container với {len(events_in_container)} events (trong đó {new_events_count} events mới)")
        
        # Merge tất cả containers
        timeline_html = '\n'.join(merged_html_parts)
        logger.info(f"Đã merge {len(merged_html_parts)} containers, tổng {total_events} events")
        
        # Kiểm tra số lượng events trong HTML đã extract
        events_in_html = len(BeautifulSoup(timeline_html, 'html.parser').select('span.yq-time'))
        logger.info(f"Đã extract timeline HTML: {len(timeline_html)} characters, {events_in_html} events")
        
        # Kiểm tra xem có đầy đủ events không
        if events_in_html < len(time_elements):
            logger.warning(f"Chỉ extract được {events_in_html}/{len(time_elements)} events, có thể thiếu events")
        elif events_in_html > len(time_elements):
            logger.info(f"Extract được {events_in_html} events (nhiều hơn {len(time_elements)} events ban đầu - có thể do merge nhiều containers)")
    else:
        logger.error("Không tìm thấy container nào có events")
        timeline_html = ''
    
    return timeline_html

def _parse_17track_timeline(html: str, tracking_number: str) -> Dict[str, Any]:
    """
    Parse HTML từ 17track.net thành format tương thích với TrackingTimelineItem.
    NOTE: Phương án này là fallback, ưu tiên sử dụng safeHtml từ _extract_17track_timeline_html.
    
    Args:
        html: HTML content (có thể là full HTML hoặc timeline_html đã extract)
        tracking_number: Mã vận đơn để validate
        
    Returns:
        dict với format: {trackingNumber, matched, timeline[], rawHtml}
    """
    soup = BeautifulSoup(html, 'html.parser')
    timeline = []
    matched = False
    
    logger.info(f"Bắt đầu parse HTML cho tracking number: {tracking_number}")
    
    # Kiểm tra xem đây có phải là timeline_html đã extract (chỉ có div.relative) không
    # Nếu có nhiều div.relative với span.yq-time, đây là timeline_html đã extract
    relative_divs_with_events = soup.select('div.relative')
    time_elements = soup.select('span.yq-time')
    
    is_extracted_timeline = len(relative_divs_with_events) > 0 and len(time_elements) > 0
    
    if is_extracted_timeline:
        logger.info(f"Phát hiện timeline HTML đã extract ({len(relative_divs_with_events)} div.relative, {len(time_elements)} events), parse trực tiếp...")
        # Parse trực tiếp từ div.relative containers
        timeline_container = soup  # Dùng soup làm container vì timeline_html chỉ có div.relative
    else:
        # Tìm container timeline với nhiều fallback selectors (cho full HTML)
        timeline_container = None
        selectors = [
            'div.space-y-2 > div.space-y-3',
            'div.space-y-3',
            '[class*="space-y-3"]',
            '[class*="timeline"]'
        ]
        
        for selector in selectors:
            try:
                timeline_container = soup.select_one(selector)
                if timeline_container:
                    logger.info(f"Tìm thấy timeline container với selector: {selector}")
                    break
            except Exception as e:
                logger.warning(f"Selector {selector} failed: {e}")
                continue
    
    if timeline_container:
        # Validate tracking number có trong page không
        page_text = timeline_container.get_text()
        if tracking_number and tracking_number in page_text:
            matched = True
        
        # Extract các events từ timeline
        # Nếu là timeline_html đã extract, parse trực tiếp từ div.relative
        if is_extracted_timeline:
            # Parse trực tiếp từ div.relative containers (timeline_html đã extract)
            events = []
            for div in relative_divs_with_events:
                # Tìm tất cả div.flex.gap-3 trong mỗi div.relative
                flex_divs = div.select('div.flex.gap-3')
                events.extend(flex_divs)
            logger.info(f"Parse từ timeline HTML đã extract: {len(events)} events từ {len(relative_divs_with_events)} containers")
        else:
            # Extract các events từ timeline với nhiều fallback selectors (cho full HTML)
            all_events = []
            event_selectors = [
                'div.flex.gap-3',
                'div[class*="flex"][class*="gap"]',
                'div[class*="relative"]'
            ]
            
            for selector in event_selectors:
                try:
                    all_events = timeline_container.select(selector)
                    if all_events:
                        logger.info(f"Tìm thấy {len(all_events)} events với selector: {selector}")
                        break
                except Exception:
                    continue
            
            # Lọc các events có class chứa min-h-7 (timeline items)
            events = []
            for event in all_events:
                classes = event.get('class', [])
                class_str = ' '.join(classes) if classes else ''
                # Kiểm tra có class min-h-7 hoặc có relative (timeline items thường có)
                if 'min-h-7' in classes or 'relative' in classes or 'mb-' in class_str:
                    events.append(event)
            
            if not events:
                # Fallback: sử dụng tất cả div.flex.gap-3
                events = all_events
                logger.info(f"Sử dụng fallback, tổng {len(events)} events")
        
        logger.info(f"Tổng số events để parse: {len(events)}")
        
        for event in events:
            try:
                # Extract timestamp
                timestamp_el = event.select_one('span.yq-time')
                if not timestamp_el:
                    # Fallback: tìm tất cả span và check class
                    for span in event.select('span'):
                        classes = span.get('class', [])
                        if 'yq-time' in classes:
                            timestamp_el = span
                            break
                
                timestamp = timestamp_el.get_text(strip=True) if timestamp_el else ''
                
                # Extract description với nhiều fallback
                desc_el = None
                desc_selectors = [
                    'span.flex-1',
                    'span.text-text-primary',
                    'span.text-text-secondary',
                    'span[class*="flex-1"]',
                    'div[class*="flex-1"]'
                ]
                
                for selector in desc_selectors:
                    try:
                        desc_el = event.select_one(selector)
                        if desc_el and desc_el.get_text(strip=True):
                            break
                    except:
                        continue
                
                # Nếu không tìm thấy, tìm tất cả text trong event
                if not desc_el or not desc_el.get_text(strip=True):
                    # Tìm tất cả span/div có text
                    text_elements = event.select('span, div')
                    for el in text_elements:
                        text = el.get_text(strip=True)
                        # Bỏ qua timestamp và các text ngắn
                        if len(text) > 20 and 'yq-time' not in (el.get('class') or []):
                            desc_el = el
                            break
                
                description = desc_el.get_text(strip=True) if desc_el else ''
                
                # Debug log
                if not description:
                    logger.warning(f"Không tìm thấy description cho event, timestamp: {timestamp}")
                
                # Extract city từ description với nhiều pattern
                city = ''
                if description:
                    # Pattern 1: [Thành phố ...] hoặc [City ...]
                    city_patterns = [
                        r'\[(?:Thành phố|City|城市)\s*([^\]]+)\]',
                        r'\[([^\]]+)\]\s*[^[]*$',  # Lấy text trong ngoặc đầu tiên
                        r'Thành phố\s+([^\s,\[\]\.]+)',
                        r'City\s+([^\s,\[\]\.]+)'
                    ]
                    
                    for pattern in city_patterns:
                        city_match = re.search(pattern, description, re.IGNORECASE)
                        if city_match:
                            city = city_match.group(1).strip()
                            # Làm sạch city name
                            city = re.sub(r'^(Thành phố|City|城市)\s*', '', city, flags=re.IGNORECASE).strip()
                            if city:
                                break
                
                # Extract status từ icon hoặc description
                status = 'In Transit'  # Default
                
                # Tìm icon với nhiều cách
                icon_el = None
                icon_selectors = [
                    'svg use',
                    'svg use[xlink\\:href]',
                    'svg use[href]',
                    '[class*="icon-"]'
                ]
                
                for selector in icon_selectors:
                    try:
                        icon_el = event.select_one(selector)
                        if icon_el:
                            break
                    except:
                        continue
                
                if icon_el:
                    icon_href = icon_el.get('xlink:href', '') or icon_el.get('href', '')
                    icon_id = icon_el.get('id', '')
                    icon_classes = ' '.join(icon_el.get('class', []))
                    
                    # Tìm status từ icon
                    icon_text = f"{icon_href} {icon_id} {icon_classes}".lower()
                    
                    if 'delivered' in icon_text:
                        status = 'Delivered'
                    elif 'in-transit' in icon_text or 'intransit' in icon_text:
                        status = 'In Transit'
                    elif 'outfordelivery' in icon_text or 'out for delivery' in icon_text:
                        status = 'Out for Delivery'
                    elif 'pickup' in icon_text or 'pick up' in icon_text:
                        status = 'Pick Up'
                    elif 'inforeceived' in icon_text or 'info received' in icon_text:
                        status = 'Info received'
                    elif 'notfound' in icon_text or 'not found' in icon_text:
                        status = 'Not found'
                    elif 'alert' in icon_text:
                        status = 'Alert'
                    elif 'expired' in icon_text:
                        status = 'Expired'
                
                # Fallback: Tìm status từ description nếu không có icon
                if status == 'In Transit' and description:
                    desc_lower = description.lower()
                    if 'delivered' in desc_lower or 'đã giao' in desc_lower or 'đã nhận' in desc_lower:
                        status = 'Delivered'
                    elif 'đang giao' in desc_lower or 'out for delivery' in desc_lower:
                        status = 'Out for Delivery'
                    elif 'not found' in desc_lower or 'không tìm thấy' in desc_lower:
                        status = 'Not found'
                
                timeline.append({
                    'city': city or 'Unknown',
                    'status': status,
                    'context': description
                })
            except Exception as e:
                logger.warning(f"Lỗi khi parse event trong timeline: {e}")
                continue
        
        logger.info(f"Đã parse được {len(timeline)} events từ timeline")
    else:
        logger.warning("Không tìm thấy timeline container")
    
    # Nếu không tìm thấy timeline nhưng có matched, vẫn return matched=True
    if not matched and tracking_number:
        page_text = html
        if tracking_number in page_text:
            matched = True
            logger.info(f"Tracking number {tracking_number} được tìm thấy trong page text")
    
    # Debug: Log một phần HTML để kiểm tra
    if not timeline:
        logger.warning("Không tìm thấy timeline events, đang kiểm tra HTML structure...")
        # Tìm tất cả div có chứa yq-time
        time_elements = soup.select('span.yq-time')
        logger.info(f"Tìm thấy {len(time_elements)} elements có class yq-time")
        if time_elements:
            logger.info(f"Ví dụ timestamp: {time_elements[0].get_text(strip=True) if time_elements else 'N/A'}")
    
    logger.info(f"Parse hoàn tất: matched={matched}, timeline_count={len(timeline)}")
    
    return {
        'trackingNumber': tracking_number,
        'matched': matched,
        'timeline': timeline,
        'rawHtml': html
    }

def _handle_17track_tooltip(driver, wait) -> bool:
    """
    Xử lý tooltip (react-joyride) nếu xuất hiện sau khi redirect.
    
    Args:
        driver: Selenium WebDriver
        wait: WebDriverWait instance
        
    Returns:
        bool: True nếu đã xử lý (có tooltip và đã đóng) hoặc không có tooltip
    """
    try:
        # Kiểm tra có tooltip không (với timeout ngắn)
        tooltip_close_button = None
        try:
            # Dùng WebDriverWait với timeout ngắn (3s) để tránh treo
            short_wait = WebDriverWait(driver, 3)
            tooltip_close_button = short_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    'button.tooltip__close'))
            )
        except Exception:
            # Không có tooltip, không cần xử lý
            logger.info("Không có tooltip, tiếp tục...")
            return True
        
        if tooltip_close_button:
            logger.info("Phát hiện tooltip, đang đóng...")
            try:
                # Scroll vào view để đảm bảo element visible
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", tooltip_close_button)
                time.sleep(0.5)
                
                # Thử click bằng JavaScript nếu click thường không được
                try:
                    tooltip_close_button.click()
                    logger.info("Đã click nút close tooltip bằng Selenium")
                except Exception:
                    # Fallback: click bằng JavaScript
                    driver.execute_script("arguments[0].click();", tooltip_close_button)
                    logger.info("Đã click nút close tooltip bằng JavaScript")
                
                # Chờ tooltip đóng
                time.sleep(1)
                
                # Kiểm tra tooltip đã đóng chưa
                try:
                    # Đợi tooltip biến mất (với timeout ngắn)
                    short_wait.until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, 'button.tooltip__close'))
                    )
                    logger.info("Tooltip đã được đóng thành công")
                except Exception:
                    # Tooltip có thể vẫn còn, nhưng không ảnh hưởng nhiều
                    logger.warning("Tooltip có thể vẫn còn, tiếp tục...")
                
                return True
            except Exception as e:
                logger.warning(f"Không thể đóng tooltip: {e}")
                return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Lỗi khi xử lý tooltip: {e}")
        return True  # Trả về True để tiếp tục dù có lỗi

def _handle_17track_reference(driver, wait, phone_number: Optional[str] = None) -> Tuple[bool, bool]:
    """
    Xử lý reference dialog trên 17track.net nếu có.
    
    Args:
        driver: Selenium WebDriver
        wait: WebDriverWait instance
        phone_number: Số điện thoại để điền (mặc định: 0971037741)
        
    Returns:
        tuple: (needed: bool, success: bool)
    """
    if phone_number is None:
        phone_number = "0971037741"
    
    try:
        # Kiểm tra có message "Please enter a reference to view the package details" không (với timeout ngắn)
        reference_message = None
        try:
            # Dùng WebDriverWait với timeout ngắn (5s) để tránh treo
            short_wait = WebDriverWait(driver, 5)
            # Pattern mới: tìm text "Please enter a reference to view the package details" 
            # Có thể ở trong span hoặc p tag
            try:
                reference_message = short_wait.until(
                    EC.presence_of_element_located((By.XPATH, 
                        "//span[contains(text(), 'Please enter a reference to view the package details')]"))
                )
                logger.info("Phát hiện message yêu cầu reference (pattern: span)")
            except Exception:
                # Thử tìm trong p tag
                try:
                    reference_message = short_wait.until(
                        EC.presence_of_element_located((By.XPATH, 
                            "//p[contains(text(), 'Please enter a reference to view the package details')]"))
                    )
                    logger.info("Phát hiện message yêu cầu reference (pattern: p tag)")
                except Exception:
                    # Fallback: tìm text ngắn hơn
                    reference_message = short_wait.until(
                        EC.presence_of_element_located((By.XPATH, 
                            "//*[contains(text(), 'Please enter a reference')]"))
                    )
                    logger.info("Phát hiện message yêu cầu reference (pattern: fallback)")
        except Exception:
            # Không có message, không cần reference
            logger.info("Không cần reference, tiếp tục...")
            return (False, True)
        
        if reference_message:
            logger.info("Phát hiện yêu cầu reference, đang xử lý...")
            
            # Tìm và click link "reference" - chỉ dùng pattern mới (aria-haspopup="dialog")
            try:
                # Pattern mới: span có aria-haspopup="dialog" và chứa text "reference"
                reference_link = driver.find_element(By.XPATH,
                    "//span[contains(text(), 'reference') and @aria-haspopup='dialog']")
                logger.info("Tìm thấy reference link (pattern: aria-haspopup='dialog')")
                
                # Scroll vào view trước khi click
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", reference_link)
                time.sleep(0.5)
                
                # Thử click bằng JavaScript nếu click thường không được
                try:
                    reference_link.click()
                    logger.info("Đã click link reference bằng Selenium")
                except Exception:
                    driver.execute_script("arguments[0].click();", reference_link)
                    logger.info("Đã click link reference bằng JavaScript")
                
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Không tìm thấy hoặc không click được link reference: {e}")
                return (True, False)
            
            # Chờ dialog xuất hiện
            try:
                dialog = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"]'))
                )
                logger.info("Dialog reference đã xuất hiện")
            except Exception:
                logger.warning("Dialog reference không xuất hiện")
                return (True, False)
            
            # Tìm input phone number
            phone_input = None
            try:
                phone_input = dialog.find_element(By.CSS_SELECTOR, 
                    'input[name="phone_number_last_4"]')
            except Exception:
                # Thử các selector khác
                try:
                    phone_input = dialog.find_element(By.CSS_SELECTOR,
                        'input[id*="-form-item"]')
                except Exception:
                    logger.warning("Không tìm thấy input phone number")
                    return (True, False)
            
            if phone_input:
                phone_input.clear()
                phone_input.send_keys(phone_number)
                logger.info(f"Đã điền phone number: {phone_number}")
                
                # Click nút Confirm
                try:
                    confirm_btn = dialog.find_element(By.CSS_SELECTOR,
                        'button[type="submit"]')
                    confirm_btn.click()
                    logger.info("Đã click nút Confirm")
                    
                    # Chờ dialog đóng
                    time.sleep(2)
                    return (True, True)
                except Exception as e:
                    logger.error(f"Không thể click Confirm: {e}")
                    return (True, False)
            
            return (True, False)
            
    except Exception as e:
        logger.error(f"Lỗi khi xử lý reference: {e}")
        return (True, False)

def _configure_17track_translation(driver, wait) -> bool:
    """
    Cấu hình translation trên 17track.net sang tiếng Việt.
    
    Args:
        driver: Selenium WebDriver
        wait: WebDriverWait instance
        
    Returns:
        bool: True nếu thành công
    """
    try:
        # Tìm container translation
        translation_container = None
        try:
            translation_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div#yq-tracking-translate'))
            )
        except Exception:
            logger.warning("Không tìm thấy translation container")
            return False
        
        if not translation_container:
            return False
        
        # Kiểm tra và chọn Vietnamese
        try:
            combobox = translation_container.find_element(By.CSS_SELECTOR,
                'button[role="combobox"]')
            combobox_text = combobox.find_element(By.TAG_NAME, 'span').text.strip()
            
            if 'Vietnamese' not in combobox_text:
                logger.info("Đang chọn Vietnamese...")
                # Scroll vào view trước
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", combobox)
                time.sleep(0.5)
                
                # Thử click bằng JavaScript
                try:
                    driver.execute_script("arguments[0].click();", combobox)
                    logger.info("Đã click combobox bằng JavaScript")
                    time.sleep(1)  # Đợi dropdown mở
                except Exception as e1:
                    logger.warning(f"Không thể click combobox bằng JavaScript: {e1}")
                    # Thử click thường
                    try:
                        combobox.click()
                        time.sleep(1)
                    except Exception as e2:
                        logger.warning(f"Không thể click combobox: {e2}")
                
                # Tìm và click option Vietnamese trong dropdown
                try:
                    # Đợi dropdown mở
                    wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Vietnamese')]")))
                    vietnamese_option = driver.find_element(By.XPATH,
                        "//span[contains(text(), 'Vietnamese')]")
                    # Click bằng JavaScript để tránh intercept
                    driver.execute_script("arguments[0].click();", vietnamese_option)
                    logger.info("Đã chọn Vietnamese")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Không tìm thấy hoặc không click được option Vietnamese: {e}")
            else:
                logger.info("Vietnamese đã được chọn")
        except Exception as e:
            logger.warning(f"Không thể chọn Vietnamese: {e}")
        
        # Bật toggle translation
        try:
            toggle = translation_container.find_element(By.CSS_SELECTOR,
                'button.relative.inline-flex.h-6.w-11')
            
            # Kiểm tra trạng thái hiện tại
            toggle_classes = toggle.get_attribute('class') or ''
            is_active = 'bg-blue-600' in toggle_classes
            
            if not is_active:
                logger.info("Đang bật toggle translation...")
                # Scroll vào view để đảm bảo element visible
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", toggle)
                time.sleep(0.5)
                
                # Thử click bằng JavaScript nếu click thường không được
                try:
                    toggle.click()
                    logger.info("Đã click toggle bằng Selenium")
                except Exception:
                    # Fallback: click bằng JavaScript
                    driver.execute_script("arguments[0].click();", toggle)
                    logger.info("Đã click toggle bằng JavaScript")
                
                time.sleep(1)
                logger.info("Đã bật toggle translation")
            else:
                logger.info("Toggle translation đã được bật")
        except Exception as e:
            logger.warning(f"Không thể bật toggle translation: {e}")
        
        # Đợi translation hoàn tất với polling (theo pattern test web - ngay sau khi bật toggle)
        logger.info("Đang đợi translation hoàn tất (polling pattern)...")
        # Chờ thêm một chút sau khi bật toggle để translation bắt đầu (tối ưu: giảm từ 3s xuống 2s)
        time.sleep(2)
        
        # Keywords để detect Vietnamese text (mở rộng thêm để detect cả tiếng Trung đầy đủ)
        vietnamese_keywords = ['thành phố', 'đã', 'được', 'giao', 'nhận', 'chuyển', 'kho', 'tàu', 'chuyến']
        
        # Polling để đợi translation hoàn tất cho timeline events (tối ưu: giảm từ 40s xuống 25s)
        timeline_translated = False
        
        # Tối ưu: Giảm iterations từ 40 → 25, check mỗi 2s thay vì 1s để giảm overhead
        # Tổng thời gian: 25 iterations x 2s = 50s max, nhưng thường exit sớm hơn
        max_iterations = 25
        check_interval = 2  # Check mỗi 2s thay vì 1s
        logger.info(f"Bắt đầu polling loop ({max_iterations} iterations x {check_interval}s = tối đa {max_iterations * check_interval}s)...")
        for i in range(max_iterations):
            time.sleep(check_interval)
            # Log mỗi 5 giây để theo dõi
            elapsed_time = (i + 1) * check_interval
            if elapsed_time % 5 == 0 or i == 0:
                logger.info(f"Polling iteration {i+1}/{max_iterations} (đã đợi {elapsed_time}s)...")
            
            try:
                # Kiểm tra timeline container - tìm lại mỗi lần để tránh stale element (theo test web)
                timeline_elements_check = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
                
                if timeline_elements_check:
                    # Lấy HTML và check (theo test web - dùng page_source trực tiếp)
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                
                # Tìm timeline container có events (theo pattern test web chính xác)
                # Tìm div.relative chứa nhiều events nhất (container chính)
                timeline_containers = soup.select('div.relative')
                main_container = None
                max_events_count = 0
                
                for container in timeline_containers:
                    events = container.select('span.yq-time')
                    if len(events) > max_events_count:
                        max_events_count = len(events)
                        main_container = container
                
                # Kiểm tra Vietnamese text trong container chính
                if main_container:
                    # Check text trong các span.flex-1 (description đã dịch)
                    description_spans = main_container.select('span.flex-1')
                    container_text = main_container.get_text().lower()
                    
                    # Kiểm tra có Vietnamese keywords trong description
                    found_vietnamese = any(keyword in container_text for keyword in vietnamese_keywords)
                    
                    # Hoặc check trực tiếp trong description spans
                    if not found_vietnamese and description_spans:
                        for span in description_spans[:3]:  # Check 3 spans đầu
                            span_text = span.get_text().lower()
                            if any(keyword in span_text for keyword in vietnamese_keywords):
                                found_vietnamese = True
                                break
                    
                    if found_vietnamese:
                        elapsed_time = (i + 1) * check_interval
                        logger.info(f"✓ Đã phát hiện text tiếng Việt trong timeline events sau {elapsed_time}s (iteration {i+1}/{max_iterations})")
                        timeline_translated = True
                        break
                
                if timeline_translated:
                    break
            except Exception as e:
                elapsed_time = (i + 1) * check_interval
                logger.warning(f"Lỗi khi kiểm tra translation sau {elapsed_time}s: {e}")
                # Nếu là timeout, log chi tiết
                if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                    logger.warning(f"Timeout khi lấy page_source sau {elapsed_time}s - có thể driver đang chậm")
            
            # Log mỗi 5 giây (theo pattern test web) - log NGAY CẢ KHI CÓ EXCEPTION
            elapsed_time = (i + 1) * check_interval
            if elapsed_time % 5 == 0:
                logger.info(f"Chưa thấy text tiếng Việt sau {elapsed_time}s, tiếp tục đợi...")
        
        if not timeline_translated:
            max_wait_time = max_iterations * check_interval
            logger.warning(f"Đã chờ {max_wait_time}s nhưng chưa phát hiện text tiếng Việt trong timeline events - thử scroll lại timeline")
            # Thử scroll lại timeline để trigger translation (theo pattern codebase - đơn giản, không threading)
            try:
                # Kiểm tra driver còn sống
                try:
                    driver.current_url
                except Exception:
                    logger.warning("Driver đã bị đóng, không thể scroll")
                else:
                    # Tìm timeline elements (giới hạn timeout bằng cách dùng find_elements thay vì wait)
                    try:
                        timeline_elements = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
                        if timeline_elements:
                            # Scroll đến event cuối cùng để trigger translation (tối ưu: giảm từ 2s xuống 1s)
                            logger.info(f"Scroll đến event cuối cùng để trigger translation...")
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", timeline_elements[-1])
                            time.sleep(1)  # Chờ translation sau scroll
                            
                            # Kiểm tra lại một lần nữa (đơn giản, không phức tạp)
                            html_check = driver.page_source
                            soup_check = BeautifulSoup(html_check, 'html.parser')
                            timeline_containers_check = soup_check.select('div.relative')
                            
                            for container in timeline_containers_check:
                                events = container.select('span.yq-time')
                                if len(events) > 0:
                                    container_text = container.get_text().lower()
                                    found_vietnamese = any(keyword in container_text for keyword in vietnamese_keywords)
                                    if found_vietnamese:
                                        logger.info("✓ Đã phát hiện text tiếng Việt sau khi scroll lại timeline")
                                        timeline_translated = True
                                        break
                        else:
                            logger.warning("Không tìm thấy timeline elements để scroll")
                    except Exception as e:
                        logger.warning(f"Lỗi khi scroll timeline: {e}")
            except Exception as e:
                logger.warning(f"Không thể scroll lại timeline: {e}")
        
        # Log kết quả cuối cùng
        if timeline_translated:
            logger.info("✓ Translation đã hoàn tất, có Vietnamese text trong timeline")
        else:
            logger.warning("⚠ Translation có thể chưa hoàn tất hoặc không có Vietnamese text, sẽ lấy HTML hiện tại")
        
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi cấu hình translation: {e}")
        return False

def _extract_17track_via_copy_details(driver, wait, tracking_number: str) -> Optional[str]:
    """
    Thử extract tracking info bằng cách intercept copy event từ button "Copy details".
    Best practice: Intercept copy event để lấy data trực tiếp, không cần đọc clipboard.
    
    Args:
        driver: Selenium WebDriver
        wait: WebDriverWait instance
        tracking_number: Mã vận đơn để validate
        
    Returns:
        str: Text content từ copy event hoặc None nếu không lấy được
    """
    try:
        logger.info("Thử extract tracking info bằng cách intercept copy event từ 'Copy details'...")
        
        # Tìm button "Copy details"
        try:
            copy_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@title, 'Copy detailed tracking results') or contains(text(), 'Copy details')]"))
            )
            logger.info("Tìm thấy button 'Copy details'")
        except Exception as e:
            logger.warning(f"Không tìm thấy button 'Copy details': {e}")
            return None
        
        # Best practice: Intercept copy event để lấy data trực tiếp (không cần clipboard permission)
        try:
            # Inject script để intercept copy event và capture data
            copied_data = driver.execute_script("""
                // Tạo biến global để lưu data
                window.__copiedData = null;
                
                // Intercept copy event
                document.addEventListener('copy', function(e) {
                    // Lấy data từ clipboard event
                    const selection = window.getSelection().toString();
                    if (selection) {
                        window.__copiedData = selection;
                    } else {
                        // Nếu không có selection, thử lấy từ clipboardData
                        if (e.clipboardData) {
                            const data = e.clipboardData.getData('text/plain');
                            if (data) {
                                window.__copiedData = data;
                            }
                        }
                    }
                }, true);
                
                // Trigger click để copy
                arguments[0].click();
                
                // Đợi một chút để event được trigger
                return new Promise((resolve) => {
                    setTimeout(() => {
                        resolve(window.__copiedData || null);
                    }, 500);
                });
            """, copy_button)
            
            if copied_data and len(copied_data) > 100:
                logger.info(f"✓ Đã lấy được text từ copy event ({len(copied_data)} ký tự)")
                # Validate: kiểm tra có chứa tracking number không
                if tracking_number in copied_data:
                    logger.info("✓ Copy event text chứa tracking number, hợp lệ")
                    return copied_data
                else:
                    logger.warning("⚠ Copy event text không chứa tracking number")
            else:
                logger.warning("⚠ Copy event text quá ngắn hoặc rỗng")
        except Exception as e:
            logger.warning(f"Không thể intercept copy event: {e}")
            # Fallback: Thử cách khác - trigger copy và xử lý alert
        
        # Fallback 2: Thử với alert handling (nếu có alert xuất hiện)
        try:
            # Xử lý alert nếu có
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                logger.info(f"Phát hiện alert: {alert_text}")
                # Accept alert (có thể là permission request)
                alert.accept()
                time.sleep(0.5)
            except Exception:
                # Không có alert, tiếp tục
                pass
            
            # Thử đọc clipboard sau khi xử lý alert
            try:
                # Cấp quyền clipboard bằng CDP (best practice)
                driver.execute_cdp_cmd('Browser.grantPermissions', {
                    'origin': driver.current_url.split('/')[0] + '//' + driver.current_url.split('/')[2],
                    'permissions': ['clipboard-read', 'clipboard-write']
                })
                
                clipboard_text = driver.execute_script("""
                    return navigator.clipboard.readText().then(
                        text => text,
                        err => null
                    );
                """)
                
                if clipboard_text and len(clipboard_text) > 100 and tracking_number in clipboard_text:
                    logger.info(f"✓ Đã lấy được text từ clipboard sau khi cấp quyền ({len(clipboard_text)} ký tự)")
                    return clipboard_text
            except Exception as e2:
                logger.warning(f"Không thể đọc clipboard sau khi cấp quyền: {e2}")
        except Exception as e3:
            logger.warning(f"Lỗi trong fallback 2: {e3}")
        
        return None
        
    except Exception as e:
        logger.warning(f"Lỗi khi extract via copy details: {e}")
        return None

def _track_17track_selenium(driver, wait, tracking_number: str, phone_number: Optional[str] = None) -> Dict[str, Any]:
    """
    Thực hiện tracking trên 17track.net với Selenium.
    
    Args:
        driver: Selenium WebDriver
        wait: WebDriverWait instance
        tracking_number: Mã vận đơn cần tra cứu
        phone_number: Số điện thoại nếu cần reference (mặc định: 0971037741)
        
    Returns:
        dict: {html: str, success: bool, error?: str}
    """
    try:
        logger.info(f"Bắt đầu track 17track cho: {tracking_number}")
        
        # Bước 1: Redirect trực tiếp đến URL tracking (TỐI ƯU - bỏ qua trang chủ, điền form, click)
        tracking_url = f'https://t.17track.net/en#nums={tracking_number}'
        logger.info(f"Redirect trực tiếp đến: {tracking_url}")
        try:
            driver.get(tracking_url)
            time.sleep(2)  # Chờ page load với tracking number
        except Exception as e:
            logger.error(f"Lỗi khi redirect trực tiếp: {e}")
            return {'html': '', 'success': False, 'error': f'Failed to load tracking page: {str(e)}'}
        
        # Kiểm tra driver còn sống trước khi tiếp tục
        try:
            current_url = driver.current_url
            logger.info(f"Đã load trang tracking: {current_url}")
        except Exception:
            logger.error("Driver bị đóng sau khi load trang tracking")
            return {'html': '', 'success': False, 'error': 'Driver closed after page load'}
        
        # Bước 4.5: Xử lý tooltip (react-joyride) nếu xuất hiện (TRƯỚC reference dialog)
        logger.info("Kiểm tra tooltip...")
        tooltip_handled = _handle_17track_tooltip(driver, wait)
        if not tooltip_handled:
            logger.warning("Tooltip không được xử lý thành công, tiếp tục...")
        
        # Chờ một chút sau khi đóng tooltip (tối ưu: giảm từ 1s xuống 0.5s)
        if tooltip_handled:
            time.sleep(0.5)
        
        # Bước 5: Xử lý reference dialog (nếu có)
        logger.info("Kiểm tra reference dialog...")
        reference_needed, reference_success = _handle_17track_reference(driver, wait, phone_number)
        if reference_needed and not reference_success:
            logger.warning("Reference dialog không được xử lý thành công")
        
        # Chờ thêm một chút sau khi xử lý reference (tối ưu: giảm từ 2s xuống 1s)
        if reference_needed:
            time.sleep(1)
        
        # Chờ để đảm bảo page đã load hoàn toàn (tối ưu: giảm từ 3s xuống 2s)
        logger.info("Đang chờ page load hoàn toàn...")
        time.sleep(2)
        
        # Bước 6a: Scroll để load events TRƯỚC khi translation (theo pattern test web - đơn giản)
        try:
            logger.info("Đang scroll để load events TRƯỚC khi translation...")
            # Scroll đơn giản như test web - tìm events trước, scroll đến event cuối
            timeline_elements = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
            logger.info(f"Tìm thấy {len(timeline_elements)} events TRƯỚC khi translation")
            
            # Kiểm tra: Nếu không có events, có thể yêu cầu xác thực thông tin bảo mật
            if len(timeline_elements) == 0:
                logger.warning("Không tìm thấy events TRƯỚC khi translation - có thể yêu cầu xác thực thông tin bảo mật")
                # Thử scroll và đợi thêm một chút để xem có events xuất hiện không
                time.sleep(2)
                timeline_elements = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
                logger.info(f"Sau khi đợi thêm: {len(timeline_elements)} events")
                
                # Nếu vẫn không có events, trả về lỗi
                if len(timeline_elements) == 0:
                    error_msg = "Đơn hàng này yêu cầu xác thực thông tin bảo mật. Xin vui lòng liên hệ CSKH để được thông tin chi tiết."
                    logger.error(error_msg)
                    return {'html': '', 'success': False, 'error': error_msg}
            
            # Scroll đến event cuối cùng để load đầy đủ (tối ưu: giảm từ 2s xuống 1s)
            if timeline_elements:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", timeline_elements[-1])
                time.sleep(1)
                # Đếm lại sau scroll
                timeline_elements = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
                logger.info(f"Sau scroll: {len(timeline_elements)} events")
        except Exception as e:
            logger.warning(f"Không thể scroll: {e}")
        
        # Bước 6b: Cấu hình translation SAU KHI timeline đã được load đầy đủ
        logger.info("Cấu hình translation SAU KHI timeline đã load...")
        translation_success = _configure_17track_translation(driver, wait)
        if not translation_success:
            logger.warning("Không thể cấu hình translation, tiếp tục với dữ liệu gốc")
        
        # Translation đã được xử lý trong _configure_17track_translation với polling
        # Không cần scroll lại nhiều, chỉ cần đợi translation hoàn tất (đã có trong function)
        
        # Kiểm tra lại xem có text tiếng Việt trong timeline events không (để log)
        try:
            timeline_elements_final = driver.find_elements(By.CSS_SELECTOR, 'span.yq-time')
            logger.info(f"Tìm thấy {len(timeline_elements_final)} events sau translation")
            
            # Check một lần nữa để chắc chắn
            timeline_containers = driver.find_elements(By.CSS_SELECTOR, 'div.relative')
            for container in timeline_containers:
                events = container.find_elements(By.CSS_SELECTOR, 'span.yq-time')
                if len(events) > 0:
                    container_text = container.text.lower()
                    vietnamese_keywords = ['thành phố', 'đã', 'được', 'giao', 'nhận', 'chuyển', 'kho']
                    found_vietnamese = any(keyword in container_text for keyword in vietnamese_keywords)
                    if found_vietnamese:
                        logger.info("✓ Đã phát hiện text tiếng Việt trong timeline events")
                        break
                    else:
                        logger.warning("Chưa thấy text tiếng Việt trong timeline events")
                        break
        except Exception as e:
            logger.warning(f"Không thể kiểm tra timeline events: {e}")
        
        # Kiểm tra driver còn sống trước khi lấy HTML
        try:
            driver.current_url
        except Exception:
            logger.error("Driver bị đóng trước khi lấy HTML")
            return {'html': '', 'success': False, 'error': 'Driver closed before getting HTML'}
        
        # Bước 7: Thử extract bằng "Copy details" trước (TỐI ƯU MỚI - nhanh hơn parse HTML)
        logger.info("Thử extract tracking info bằng 'Copy details'...")
        clipboard_text = _extract_17track_via_copy_details(driver, wait, tracking_number)
        
        if clipboard_text:
            logger.info("✓ Đã lấy được data từ clipboard, sẽ parse text trực tiếp...")
            # TODO: Parse clipboard text trực tiếp thay vì convert sang HTML
            # Tạm thời vẫn dùng HTML parsing để đảm bảo tương thích
            logger.info("Sử dụng clipboard text để parse timeline (sẽ implement sau)...")
        
        # Bước 8: Lấy HTML sau khi đã xử lý (fallback nếu clipboard không hoạt động)
        logger.info("Đang lấy HTML content...")
        try:
            html = driver.page_source
            logger.info(f"Đã lấy HTML, độ dài: {len(html)} characters")
        except Exception as e:
            logger.error(f"Lỗi khi lấy HTML: {e}")
            return {'html': '', 'success': False, 'error': f'Failed to get HTML: {str(e)}'}
        
        return {
            'html': html,
            'success': True,
            'clipboard_text': clipboard_text if clipboard_text else None  # Thêm clipboard text vào response
        }
        
    except Exception as e:
        logger.error(f"Lỗi trong _track_17track_selenium: {e}")
        return {
            'html': '',
            'success': False,
            'error': str(e)
        }

@swag_from({
    'tags': ['tracking'],
    'summary': 'Tra cứu hành trình vận đơn trên 17track.net',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'trackingNumber': {'type': 'string', 'example': '78952381275889'},
                'phoneNumber': {'type': 'string', 'example': '0971037741', 'description': 'Số điện thoại nếu cần reference (optional)'}
            },
            'required': ['trackingNumber']
        }
    }],
    'responses': {200: {'description': 'Tracking timeline', 'schema': {'type': 'object'}}}
})
@app.route('/track/17track', methods=['POST'])
def track_17track():
    """
    Tra cứu vận đơn trên 17track.net
    Request: { trackingNumber: string, phoneNumber?: string }
    Response: { trackingNumber, matched, timeline[], safeHtml?, elapsedMs }
    """
    data = request.get_json(silent=True) or {}
    tracking_number = data.get('trackingNumber', '').strip()
    phone_number = data.get('phoneNumber', None)
    
    if not tracking_number:
        return jsonify({'error': 'trackingNumber is required'}), 400
    
    start_ts = time.time()
    driver = None
    try:
        driver = _build_chrome_driver(headless=True)
        driver.set_page_load_timeout(60)
        wait = WebDriverWait(driver, 60)
        
        # Kiểm tra driver ngay sau khi build
        try:
            current_url_test = driver.current_url
            logger.info("Driver đã khởi tạo thành công")
        except Exception as e:
            logger.error(f"Driver bị đóng ngay sau khi khởi tạo: {e}")
            elapsed = round((time.time() - start_ts) * 1000)
            return jsonify({
                'trackingNumber': tracking_number,
                'matched': False,
                'timeline': [],
                'error': f'Driver initialization failed: {str(e)}',
                'elapsedMs': elapsed
            }), 502
        
        # Thực hiện tracking với Selenium
        track_result = _track_17track_selenium(driver, wait, tracking_number, phone_number)
        
        if not track_result['success']:
            error_msg = track_result.get('error', 'Unknown error')
            logger.error(f"Tracking failed: {error_msg}")
            elapsed = round((time.time() - start_ts) * 1000)
            return jsonify({
                'trackingNumber': tracking_number,
                'matched': False,
                'timeline': [],
                'error': error_msg,
                'elapsedMs': elapsed
            }), 502
        
        html = track_result['html']
        
        # ƯU TIÊN: Extract timeline HTML để render trực tiếp (đơn giản, giữ styling)
        # Extract timeline HTML - đơn giản: lấy được bao nhiêu render bấy nhiêu
        timeline_html = _extract_17track_timeline_html(html, tracking_number)
        
        # Sanitize timeline HTML để render an toàn
        safe_timeline_html = ''
        if timeline_html:
            try:
                safe_timeline_html = _sanitize_raw_html(timeline_html)
                events_count = len(BeautifulSoup(safe_timeline_html, 'html.parser').select('span.yq-time'))
                logger.info(f"Đã extract và sanitize timeline HTML: {len(safe_timeline_html)} characters, {events_count} events")
            except Exception as e:
                logger.warning(f"Lỗi khi sanitize timeline HTML: {e}")
        else:
            logger.warning("Không extract được timeline HTML")
        
        # Parse timeline từ HTML (fallback cho search/sort/filter nếu frontend cần)
        # Đơn giản: chỉ parse nếu cần, không phức tạp hóa
        parsed = _parse_17track_timeline(timeline_html if timeline_html else html, tracking_number)
        
        # Gán safeHtml - đây là phần chính để render
        parsed['safeHtml'] = safe_timeline_html
        
        if safe_timeline_html:
            logger.info(f"✓ safeHtml sẵn sàng để render: {len(safe_timeline_html)} characters")
        
        elapsed = round((time.time() - start_ts) * 1000)
        parsed['elapsedMs'] = elapsed
        
        return jsonify(parsed)
        
    except Exception as e:
        logger.error(f"Track 17track error: {e}")
        # Phân loại lỗi cơ bản
        msg = str(e).lower()
        if 'timeout' in msg:
            return jsonify({'error': 'TIMEOUT'}), 408
        return jsonify({'error': 'UPSTREAM_CHANGED', 'message': str(e)}), 502
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

@swag_from({
    'tags': ['tracking'],
    'summary': 'Tra cứu hành trình vận đơn nội địa Trung Quốc (amzcheck.net)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'trackingNumber': {'type': 'string', 'example': '78952381275889'}
            },
            'required': ['trackingNumber']
        }
    }],
    'responses': {200: {'description': 'Tracking timeline', 'schema': {'type': 'object'}}}
})
@app.route('/track/china', methods=['POST'])
def track_china():
    data = request.get_json(silent=True) or {}
    tracking_number = data.get('trackingNumber', '').strip()
    if not tracking_number:
        return jsonify({'error': 'trackingNumber is required'}), 400

    start_ts = time.time()
    driver = None
    try:
        driver = _build_chrome_driver(headless=True)
        driver.set_page_load_timeout(60)
        wait = WebDriverWait(driver, 60)

        driver.get('https://amzcheck.net/')

        # Điền mã vận đơn
        inp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#inp_num')))
        inp.clear()
        inp.send_keys(tracking_number)

        # Click nút Tra cứu
        btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#dnus')))
        btn.click()

        def _wait_and_parse():
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#shippingContent, #trackingContent')))
            time.sleep(1.0)  # đợi render hoàn tất nhẹ
            html_local = driver.page_source
            parsed_local = _parse_tracking_html(html_local, tracking_number)
            try:
                parsed_local['safeHtml'] = _sanitize_raw_html(parsed_local.get('rawHtml') or '')
            except Exception:
                parsed_local['safeHtml'] = ''
            return parsed_local

        parsed = _wait_and_parse()

        # Nếu chưa có timeline hoặc không khớp, thử Enter trên input
        if not parsed.get('timeline') or parsed.get('matched') is False:
            try:
                inp2 = driver.find_element(By.CSS_SELECTOR, '#inp_num')
                inp2.clear(); inp2.send_keys(tracking_number + "\n")
                parsed = _wait_and_parse()
            except Exception:
                pass

        # Nếu vẫn chưa có, thử gọi trực tiếp JS handler
        if not parsed.get('timeline') or parsed.get('matched') is False:
            try:
                driver.execute_script('if (typeof checkChinaShippingForm === "function") { checkChinaShippingForm(); }')
                parsed = _wait_and_parse()
            except Exception:
                pass

        # Trả về 200 cả khi không khớp hoặc không có timeline để FE hiển thị rõ ràng
        if not parsed.get('timeline') or parsed.get('matched') is False:
            elapsed = round((time.time() - start_ts) * 1000)
            parsed['elapsedMs'] = elapsed
            return jsonify(parsed)

        elapsed = round((time.time() - start_ts) * 1000)
        parsed['elapsedMs'] = elapsed
        return jsonify(parsed)

    except Exception as e:
        logger.error(f"Track error: {e}")
        # Phân loại lỗi cơ bản
        msg = str(e).lower()
        if 'timeout' in msg:
            return jsonify({'error': 'TIMEOUT'}), 408
        return jsonify({'error': 'UPSTREAM_CHANGED', 'message': str(e)}), 502
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Order Management Crawler service is running"})

# @app.route('/create-session', methods=['POST'])
# def create_new_session():
#     """API endpoint để tạo session mới - DISABLED, using Selenium now"""
#     return jsonify({"error": "Endpoint disabled - using Selenium now"}), 501

"""Loại bỏ route cũ /load-1688-product theo yêu cầu."""

"""Loại bỏ route cũ /enhanced-crawl-1688 theo yêu cầu."""

@app.route('/pugo-session-info', methods=['GET'])
def pugo_session_info():
    """Lấy thông tin session pugo.vn hiện tại"""
    try:
        from py_extractors.extractor_pugo import ExtractorPugo
        extractor = ExtractorPugo()
        session_info = extractor.get_session_info()
        
        return jsonify({
            "status": "success",
            "session_info": session_info
        })
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/pugo-clear-session', methods=['POST'])
def pugo_clear_session():
    """Xóa session pugo.vn hiện tại"""
    try:
        from py_extractors.extractor_pugo import ExtractorPugo
        extractor = ExtractorPugo()
        extractor.clear_session()
        
        return jsonify({
            "status": "success",
            "message": "Đã xóa session và cookies"
        })
    except Exception as e:
        logger.error(f"Lỗi khi xóa session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/nhaphangchina-session-info', methods=['GET'])
def nhaphangchina_session_info():
    """Lấy thông tin session nhaphangchina hiện tại"""
    try:
        from py_extractors.extractor_nhaphangchina import ExtractorNhaphangchina
        extractor = ExtractorNhaphangchina()
        session_info = extractor.get_session_info()
        return jsonify({"status": "success", "session_info": session_info})
    except Exception as e:
        logger.error(f"Lỗi khi lấy session nhaphangchina: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/nhaphangchina-clear-session', methods=['POST'])
def nhaphangchina_clear_session():
    """Xóa session nhaphangchina hiện tại"""
    try:
        from py_extractors.extractor_nhaphangchina import ExtractorNhaphangchina
        extractor = ExtractorNhaphangchina()
        extractor.clear_session()
        return jsonify({"status": "success", "message": "Đã xóa session nhaphangchina"})
    except Exception as e:
        logger.error(f"Lỗi khi xóa session nhaphangchina: {e}")
        return jsonify({"error": str(e)}), 500

@swag_from({
    'tags': ['extractor'],
    'summary': 'Extractor 1688 (raw) - theo dõi dữ liệu thô như backend extractor',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://detail.1688.com/offer/953742824238.html'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Raw extractor output', 'schema': {'type': 'object'}}}
})
@app.route('/extract-1688', methods=['POST'])
def route_extract_1688():
    try:
        from py_extractors.extractor_1688 import extractor_1688
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        result = extractor_1688.extract(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Extractor error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform 1688 (chuẩn hoá) - nhận raw JSON từ extractor, trả về format chuẩn',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'raw_data': {
                    'type': 'object',
                    'description': 'Raw JSON output từ extractor (có status, url, raw_data, sourceId, ...)',
                    'example': {
                        'status': 'success',
                        'url': 'https://detail.1688.com/offer/953742824238.html',
                        'raw_data': {
                            'result': {
                                'data': {
                                    'Root': {
                                        'fields': {
                                            'dataJson': {}
                                        }
                                    }
                                }
                            }
                        },
                        'sourceId': '953742824238',
                        'sourceType': '1688'
                    }
                }
            },
            'required': ['raw_data']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-1688', methods=['POST'])
def route_transform_1688():
    try:
        from py_transformers.transformer_1688 import transformer_1688
        payload = request.get_json() or {}

        # Chấp nhận 2 dạng body:
        # 1) { "raw_data": { ... } }  ← chuẩn
        # 2) Toàn bộ JSON từ extractor (có key "result" ở root)  ← linh hoạt
        if isinstance(payload, dict) and 'raw_data' in payload:
            raw_input = payload
        elif isinstance(payload, dict) and 'result' in payload:
            raw_input = { 'raw_data': payload }
        else:
            return jsonify({'error': 'Body phải là {"raw_data": {...}} hoặc JSON có key "result"'}), 400

        transformed = transformer_1688.transform(raw_input)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform 1688 từ URL (tự động extract + transform)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://detail.1688.com/offer/953742824238.html'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-1688-from-url', methods=['POST'])
def route_transform_1688_from_url():
    try:
        from py_extractors.extractor_1688 import extractor_1688
        from py_transformers.transformer_1688 import transformer_1688
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        raw = extractor_1688.extract(url)
        transformed = transformer_1688.transform(raw)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cookies-info', methods=['GET'])
def get_cookies_info():
    """API endpoint để xem thông tin cookies"""
    try:
        cookies = load_cookies()
        sessions = load_sessions()

        return jsonify({
            "status": "success",
            "cookies_count": len(cookies),
            "sessions_count": len(sessions),
            "cookies": cookies[:5],  # Chỉ hiển thị 5 cookies đầu
            "sessions": sessions
        })

    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin cookies: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== NHAPHANGCHINA ENDPOINTS ====================

@swag_from({
    'tags': ['extractor'],
    'summary': 'Extractor Nhaphangchina (raw)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body',
        'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=847402700057'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Raw extractor output', 'schema': {'type': 'object'}}}
})
@app.route('/extract-nhaphangchina', methods=['POST'])
def route_extract_nhaphangchina():
    try:
        from py_extractors.extractor_nhaphangchina import extractor_nhaphangchina
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        result = extractor_nhaphangchina.extract(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Extractor nhaphangchina error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Nhaphangchina (chuẩn hoá)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body',
        'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'raw_data': {'type': 'object'}
            },
            'required': ['raw_data']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-nhaphangchina', methods=['POST'])
def route_transform_nhaphangchina():
    try:
        from py_transformers.transformer_nhaphangchina import transformer_nhaphangchina
        payload = request.get_json() or {}
        if isinstance(payload, dict) and 'raw_data' in payload:
            raw_input = payload
        elif isinstance(payload, dict) and 'status' in payload:
            raw_input = {'raw_data': payload}
        else:
            return jsonify({'error': 'Body phải là {"raw_data": {...}} hoặc JSON có key "status"'}), 400
        transformed = transformer_nhaphangchina.transform(raw_input)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer nhaphangchina error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Nhaphangchina từ URL',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=847402700057'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-nhaphangchina-from-url', methods=['POST'])
def route_transform_nhaphangchina_from_url():
    try:
        from py_extractors.extractor_nhaphangchina import extractor_nhaphangchina
        from py_transformers.transformer_nhaphangchina import transformer_nhaphangchina
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        raw = extractor_nhaphangchina.extract(url)
        transformed = transformer_nhaphangchina.transform(raw)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer nhaphangchina error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['parser'],
    'summary': 'Parse Nhaphangchina response (HTML/JSON)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'payload': {
                    'type': 'object',
                    'description': 'Dữ liệu trả về từ loaddetailajax (HTML hoặc JSON string)'
                }
            },
            'required': ['payload']
        }
    }],
    'responses': {200: {'description': 'Parsed output', 'schema': {'type': 'object'}}}
})
@app.route('/parse-nhaphangchina', methods=['POST'])
def route_parse_nhaphangchina():
    data = request.get_json() or {}
    payload = data.get('payload')
    if payload is None:
        return jsonify({'error': 'payload is required'}), 400
    try:
        result = parser_nhaphangchina.parse(payload)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Parser nhaphangchina error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== PUGO.VN ENDPOINTS ====================

@swag_from({
    'tags': ['extractor'],
    'summary': 'Extractor Pugo.vn (raw) - theo dõi dữ liệu thô như backend extractor',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=970024185525'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Raw extractor output', 'schema': {'type': 'object'}}}
})
@app.route('/extract-pugo', methods=['POST'])
def route_extract_pugo():
    try:
        from py_extractors.extractor_pugo import extractor_pugo
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        result = extractor_pugo.extract(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Extractor error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Pugo.vn (chuẩn hoá) - nhận raw JSON từ extractor, trả về format chuẩn',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'raw_data': {
                    'type': 'object',
                    'description': 'Raw JSON output từ extractor (có status, url, raw_data, sourceId, ...)',
                    'example': {
                        'status': 'success',
                        'url': 'https://item.taobao.com/item.htm?id=970024185525',
                        'raw_data': {
                            'status': 'success',
                            'data': {
                                'name': 'Product Name',
                                'images': ['https://example.com/image1.jpg'],
                                'price': '100.00'
                            }
                        },
                        'sourceId': '970024185525',
                        'sourceType': 'pugo'
                    }
                }
            },
            'required': ['raw_data']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-pugo', methods=['POST'])
def route_transform_pugo():
    try:
        from py_transformers.transformer_pugo import transformer_pugo
        payload = request.get_json() or {}

        # Chấp nhận 2 dạng body:
        # 1) { "raw_data": { ... } }  ← chuẩn
        # 2) Toàn bộ JSON từ extractor (có key "result" ở root)  ← linh hoạt
        if isinstance(payload, dict) and 'raw_data' in payload:
            raw_input = payload
        elif isinstance(payload, dict) and 'status' in payload:
            raw_input = { 'raw_data': payload }
        else:
            return jsonify({'error': 'Body phải là {"raw_data": {...}} hoặc JSON có key "status"'}), 400

        transformed = transformer_pugo.transform(raw_input)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Pugo.vn từ URL (tự động extract + transform)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=970024185525'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-pugo-from-url', methods=['POST'])
def route_transform_pugo_from_url():
    try:
        from py_extractors.extractor_pugo import extractor_pugo
        from py_transformers.transformer_pugo import transformer_pugo
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        raw = extractor_pugo.extract(url)
        transformed = transformer_pugo.transform(raw)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['parser'],
    'summary': 'Parse Pugo.vn API response - parse dữ liệu từ API response',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'response_data': {
                    'type': 'object',
                    'description': 'API response data từ pugo.vn',
                    'example': {
                        'status': 'success',
                        'data': {
                            'name': 'Product Name',
                            'images': ['https://example.com/image1.jpg'],
                            'price': '100.00'
                        }
                    }
                }
            },
            'required': ['response_data']
        }
    }],
    'responses': {200: {'description': 'Parsed output', 'schema': {'type': 'object'}}}
})
@app.route('/parse-pugo', methods=['POST'])
def route_parse_pugo():
    try:
        data = request.get_json() or {}
        response_data = data.get('response_data')
        if not response_data:
            return jsonify({'error': 'response_data is required'}), 400
        result = parser_pugo.parse_api_response(response_data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Parser error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== PANDAMALL.VN ENDPOINTS ====================

@app.route('/pandamall-session-info', methods=['GET'])
def pandamall_session_info():
    """Lấy thông tin session pandamall.vn hiện tại"""
    try:
        from py_extractors.extractor_pandamall import ExtractorPandamall
        extractor = ExtractorPandamall()
        session_info = extractor.get_session_info()

        return jsonify({
            "status": "success",
            "session_info": session_info
        })
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin session pandamall: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/pandamall-clear-session', methods=['POST'])
def pandamall_clear_session():
    """Xóa session pandamall.vn hiện tại"""
    try:
        from py_extractors.extractor_pandamall import ExtractorPandamall
        extractor = ExtractorPandamall()
        extractor.clear_session()

        return jsonify({
            "status": "success",
            "message": "Đã xóa session và cookies pandamall"
        })
    except Exception as e:
        logger.error(f"Lỗi khi xóa session pandamall: {e}")
        return jsonify({"error": str(e)}), 500

@swag_from({
    'tags': ['extractor'],
    'summary': 'Extractor Pandamall.vn (raw) - lấy dữ liệu thô qua Selenium + CDP',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=1024618738333'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Raw extractor output', 'schema': {'type': 'object'}}}
})
@app.route('/extract-pandamall', methods=['POST'])
def route_extract_pandamall():
    try:
        from py_extractors.extractor_pandamall import extractor_pandamall
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        result = extractor_pandamall.extract(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Extractor pandamall error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Pandamall.vn từ URL (tự động extract + transform)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=1024618738333'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-pandamall-from-url', methods=['POST'])
def route_transform_pandamall_from_url():
    try:
        from py_extractors.extractor_pandamall import extractor_pandamall
        from py_transformers.transformer_pandamall import transformer_pandamall
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        raw = extractor_pandamall.extract(url)
        transformed = transformer_pandamall.transform(raw)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer pandamall error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== VIPO.VN ENDPOINTS ====================

@swag_from({
    'tags': ['extractor'],
    'summary': 'Extractor Vipo.vn (raw) - theo dõi dữ liệu thô như backend extractor',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=987315762638'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Raw extractor output', 'schema': {'type': 'object'}}}
})
@app.route('/extract-vipo', methods=['POST'])
def route_extract_vipo():
    try:
        from py_extractors.extractor_vipo import extractor_vipo
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        result = extractor_vipo.extract(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Extractor error: {e}")
        return jsonify({'error': str(e)}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Vipo.vn (chuẩn hoá) - nhận raw JSON từ extractor, trả về format chuẩn',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'raw_data': {
                    'type': 'object',
                    'description': 'Raw JSON output từ extractor (có status, url, raw_data, sourceId, ...)',
                    'example': {
                        'status': 'success',
                        'url': 'https://item.taobao.com/item.htm?id=987315762638',
                        'raw_data': {
                            'status': 'success',
                            'data': {
                                'product_name': 'Product Name',
                                'main_img_url_list': ['https://example.com/image1.jpg'],
                                'product_id': '987315762638'
                            }
                        },
                        'sourceId': '987315762638',
                        'sourceType': 'vipo'
                    }
                }
            },
            'required': ['raw_data']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-vipo', methods=['POST'])
def route_transform_vipo():
    try:
        from py_transformers.transformer_vipo import transformer_vipo
        payload = request.get_json() or {}

        # Chấp nhận 2 dạng body:
        # 1) { "raw_data": { ... } }  ← chuẩn
        # 2) Toàn bộ JSON từ extractor (có key "status" ở root)  ← linh hoạt
        if isinstance(payload, dict) and 'raw_data' in payload:
            raw_input = payload
        elif isinstance(payload, dict) and 'status' in payload:
            raw_input = { 'raw_data': payload }
        else:
            return jsonify({'error': 'Body phải là {"raw_data": {...}} hoặc JSON có key "status"'}), 400

        logger.debug(f"Transform Vipo: raw_input keys: {list(raw_input.keys()) if isinstance(raw_input, dict) else 'not a dict'}")
        if 'raw_data' in raw_input:
            logger.debug(f"Transform Vipo: raw_data keys: {list(raw_input['raw_data'].keys())[:10] if isinstance(raw_input.get('raw_data'), dict) else 'not a dict'}")

        transformed = transformer_vipo.transform(raw_input)
        
        # Log kết quả
        logger.debug(f"Transform Vipo: result keys: {list(transformed.keys()) if isinstance(transformed, dict) else 'not a dict'}")
        logger.debug(f"Transform Vipo: name length: {len(transformed.get('name', ''))}")
        logger.debug(f"Transform Vipo: images count: {len(transformed.get('images', []))}")
        
        return jsonify(transformed)
    except Exception as e:
        import traceback
        logger.error(f"Transformer error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@swag_from({
    'tags': ['transformer'],
    'summary': 'Transform Vipo.vn từ URL (tự động extract + transform)',
    'consumes': ['application/json'],
    'parameters': [{
        'in': 'body', 'name': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'example': 'https://item.taobao.com/item.htm?id=987315762638'}
            },
            'required': ['url']
        }
    }],
    'responses': {200: {'description': 'Transformed output', 'schema': {'type': 'object'}}}
})
@app.route('/transform-vipo-from-url', methods=['POST'])
def route_transform_vipo_from_url():
    try:
        from py_extractors.extractor_vipo import extractor_vipo
        from py_transformers.transformer_vipo import transformer_vipo
        data = request.get_json() or {}
        url = data.get('url')
        if not url:
            return jsonify({'error': 'url is required'}), 400
        raw = extractor_vipo.extract(url)
        transformed = transformer_vipo.transform(raw)
        return jsonify(transformed)
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    # Warm-up Pandamall browser singleton trước khi nhận request
    # (~7.6s startup, sau đó warm requests ~1.5s thay vì cold ~13s)
    try:
        from py_extractors.extractor_pandamall import extractor_pandamall as _panda
        _panda.initialize()
    except Exception as _e:
        logger.warning(f"Pandamall warm-up failed (sẽ lazy-init): {_e}")

    app.run(host='0.0.0.0', port=5001, debug=True)
