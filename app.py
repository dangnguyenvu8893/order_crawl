from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import time
import logging
import os
import json
import random
import pickle

app = Flask(__name__)

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

def setup_browser():
    """Thiết lập Playwright browser"""
    try:
        playwright = sync_playwright().start()
        
        # Cấu hình browser
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--window-size=1920,1080',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--disable-plugins',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate'
        ]
        
        browser = playwright.chromium.launch(
            headless=True,
            args=browser_args
        )
        return playwright, browser
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo browser: {e}")
        return None, None

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

def create_session_and_cookies():
    """Tạo session mới và cookies"""
    try:
        playwright, browser = setup_browser()
        if not browser:
            return None, None, None
        
        # Tạo context với stealth mode
        context = create_stealth_context(browser, use_saved_cookies=False)
        page = context.new_page()
        
        # Truy cập trang chủ 1688.com để tạo session
        logger.info("Đang tạo session mới trên 1688.com...")
        page.goto("https://www.1688.com/", wait_until='domcontentloaded', timeout=60000)
        time.sleep(5)
        
        # Lấy cookies từ session hiện tại
        cookies = page.context.cookies()
        logger.info(f"Đã tạo session với {len(cookies)} cookies")
        
        # Lưu cookies mới
        save_cookies(cookies)
        
        # Lưu session info
        session_info = {
            'timestamp': time.time(),
            'cookies_count': len(cookies),
            'user_agent': page.evaluate("navigator.userAgent"),
            'viewport': page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
        }
        
        sessions = load_sessions()
        sessions[f"session_{int(time.time())}"] = session_info
        save_sessions(sessions)
        
        return playwright, browser, context
        
    except Exception as e:
        logger.error(f"Lỗi khi tạo session: {e}")
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        return None, None, None

def get_page_content(page_content):
    """Lấy nội dung trang web"""
    try:
        return {
            "status": "success",
            "content": page_content,
            "content_length": len(page_content)
        }
    except Exception as e:
        logger.error(f"Lỗi khi lấy nội dung trang: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Stealth Playwright service is running"})

@app.route('/create-session', methods=['POST'])
def create_new_session():
    """API endpoint để tạo session mới"""
    try:
        logger.info("Bắt đầu tạo session mới...")
        
        playwright, browser, context = create_session_and_cookies()
        if not context:
            return jsonify({"error": "Không thể tạo session"}), 500
        
        try:
            # Lấy thông tin session
            page = context.new_page()
            page.goto("https://www.1688.com/", wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            session_info = {
                "status": "success",
                "message": "Session mới đã được tạo",
                "cookies_count": len(context.cookies()),
                "timestamp": time.time()
            }
            
            return jsonify(session_info)
            
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            
    except Exception as e:
        logger.error(f"Lỗi khi tạo session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/load-1688-product', methods=['POST'])
def load_1688_product():
    """API endpoint để load sản phẩm 1688.com"""
    try:
        data = request.get_json()
        if not data or 'product_id' not in data:
            return jsonify({"error": "Product ID is required"}), 400
        
        product_id = data['product_id']
        url = f"https://detail.1688.com/offer/{product_id}.html"
        use_saved_cookies = data.get('use_saved_cookies', True)
        
        logger.info(f"Bắt đầu load sản phẩm 1688: {product_id}")
        
        # Khởi tạo browser
        playwright, browser = setup_browser()
        if not browser:
            return jsonify({"error": "Không thể khởi tạo browser"}), 500
        
        try:
            # Tạo context với stealth mode
            context = create_stealth_context(browser, use_saved_cookies=use_saved_cookies)
            page = context.new_page()
            
            # Load trang
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            logger.info(f"Đã load trang sản phẩm thành công: {url}")
            
            # Chờ trang load hoàn toàn
            time.sleep(15)
            
            # Chờ thêm để đảm bảo JavaScript đã chạy xong
            try:
                page.wait_for_load_state('domcontentloaded', timeout=30000)
            except:
                logger.warning("DOM content loaded timeout, tiếp tục với content hiện tại")
            
            # Chờ thêm một chút để đảm bảo dữ liệu đã load
            time.sleep(5)
            
            # Lấy page content
            page_content = page.content()
            
            # Lấy nội dung trang
            result = get_page_content(page_content)
            result["product_id"] = product_id
            result["url"] = url
            result["timestamp"] = time.time()
            result["cookies_used"] = len(context.cookies())
            
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
