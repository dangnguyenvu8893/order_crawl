from flask import Flask, request, jsonify
from flasgger import Swagger, swag_from
# from playwright.sync_api import sync_playwright  # Removed - using Selenium now
import time
import logging
import os
import json
import random
import pickle
from parser_1688 import parser_1688
from parser_pugo import parser_pugo

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
swagger = Swagger(app)

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



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
