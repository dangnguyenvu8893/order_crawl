import re
import json
import time
import logging
import os
import pickle
from typing import Dict, Any, Optional, Tuple

# Import URL resolver utility
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.url_resolver import resolve_product_url

# Setup logger trước khi import selenium
logger = logging.getLogger(__name__)

# Import Selenium với error handling
# Note: Selenium warnings có thể xuất hiện trong môi trường dev không có selenium
try:
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    from selenium.webdriver.chrome.service import Service  # type: ignore
    SELENIUM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Selenium không khả dụng: {e}")
    webdriver = None
    By = None
    WebDriverWait = None
    EC = None
    Options = None
    Service = None
    SELENIUM_AVAILABLE = False


class ExtractorPugo:
    def __init__(self) -> None:
        self.login_url = "https://pugo.vn/dang-nhap"
        self.api_base_url = "https://pugo.vn/item/detail"
        self.email = "vudn8893@gmail.com"
        self.password = "Acd@123123"
        
        # Đường dẫn lưu trữ session
        self.session_dir = "/app/logs/sessions"
        self.cookies_file = os.path.join(self.session_dir, "pugo_cookies.pkl")
        self.session_file = os.path.join(self.session_dir, "pugo_session.pkl")
        
        # Khởi tạo session directory với fallback
        self._init_session_directory()
    
    def _init_session_directory(self) -> None:
        """Khởi tạo thư mục session với fallback strategies"""
        # Strategy 1: Thử tạo thư mục chính
        try:
            os.makedirs(self.session_dir, exist_ok=True)
            # Test write permission
            test_file = os.path.join(self.session_dir, ".test_write")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"✓ Session directory ready: {self.session_dir}")
            return
        except PermissionError as e:
            logger.warning(f"Permission denied cho thư mục chính {self.session_dir}: {e}")
        except Exception as e:
            logger.warning(f"Lỗi khi tạo thư mục chính {self.session_dir}: {e}")
        
        # Strategy 2: Thử các thư mục fallback khác
        fallback_dirs = [
            "/tmp/pugo_sessions",
            "/app/tmp/sessions", 
            os.path.expanduser("~/pugo_sessions"),
            os.path.join(os.getcwd(), "sessions")
        ]
        
        for fallback_dir in fallback_dirs:
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                # Test write permission
                test_file = os.path.join(fallback_dir, ".test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                # Update paths
                self.session_dir = fallback_dir
                self.cookies_file = os.path.join(self.session_dir, "pugo_cookies.pkl")
                self.session_file = os.path.join(self.session_dir, "pugo_session.pkl")
                logger.info(f"✓ Using fallback session directory: {self.session_dir}")
                return
            except Exception as e:
                logger.debug(f"Fallback directory {fallback_dir} failed: {e}")
                continue
        
        # Strategy 3: Sử dụng tempfile (cuối cùng)
        try:
            import tempfile
            self.session_dir = tempfile.mkdtemp(prefix="pugo_sessions_")
            self.cookies_file = os.path.join(self.session_dir, "pugo_cookies.pkl")
            self.session_file = os.path.join(self.session_dir, "pugo_session.pkl")
            logger.warning(f"⚠️ Using temporary session directory: {self.session_dir}")
            logger.warning("⚠️ Sessions will not persist between container restarts")
        except Exception as e:
            logger.error(f"❌ All session directory strategies failed: {e}")
            raise Exception("Không thể tạo thư mục session với bất kỳ strategy nào")
        
    def can_handle(self, url: str) -> bool:
        """
        Kiểm tra xem URL có thể được xử lý bởi pugo.vn extractor không
        
        Args:
            url: URL cần kiểm tra
            
        Returns:
            True nếu URL được hỗ trợ, False nếu không
        """
        # Danh sách các domain được hỗ trợ
        supported_domains = [
            r"pugo\.vn",
            r"item\.taobao\.com", 
            r"detail\.1688\.com",
            r"detail\.tmall\.com",
            r"e\.tb\.cn",      # Taobao short URL
            r"tb\.cn",         # Taobao short URL  
            r"s\.tb\.cn",      # Taobao short URL
            r"qr\.1688\.com"   # 1688 QR links
        ]
        
        return any(re.search(pattern, url) for pattern in supported_domains)
    
    def save_cookies(self, cookies: list) -> None:
        """Lưu cookies vào file với retry mechanism"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(self.cookies_file, 'wb') as f:
                    pickle.dump(cookies, f)
                logger.info(f"✓ Đã lưu {len(cookies)} cookies vào {self.cookies_file}")
                return
            except PermissionError as e:
                logger.error(f"❌ Permission denied khi lưu cookies (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Thử tạo lại thư mục với quyền khác
                    try:
                        os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
                        logger.info(f"🔄 Retrying với thư mục mới...")
                    except Exception as retry_e:
                        logger.warning(f"⚠️ Retry failed: {retry_e}")
                else:
                    logger.warning("⚠️ Không thể lưu cookies sau {max_retries} lần thử")
                    logger.warning("⚠️ Session sẽ không được persist, cần đăng nhập lại mỗi lần")
            except Exception as e:
                logger.error(f"❌ Lỗi khi lưu cookies: {e}")
                break
    
    def load_cookies(self) -> Optional[list]:
        """Load cookies từ file"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'rb') as f:
                    cookies = pickle.load(f)
                logger.info(f"Đã load {len(cookies)} cookies từ {self.cookies_file}")
                return cookies
        except Exception as e:
            logger.error(f"Lỗi khi load cookies: {e}")
        return None
    
    def save_session(self, session_data: dict) -> None:
        """Lưu thông tin session với retry mechanism"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                session_data['timestamp'] = time.time()
                with open(self.session_file, 'wb') as f:
                    pickle.dump(session_data, f)
                logger.info(f"✓ Đã lưu session vào {self.session_file}")
                return
            except PermissionError as e:
                logger.error(f"❌ Permission denied khi lưu session (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Thử tạo lại thư mục với quyền khác
                    try:
                        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
                        logger.info(f"🔄 Retrying với thư mục mới...")
                    except Exception as retry_e:
                        logger.warning(f"⚠️ Retry failed: {retry_e}")
                else:
                    logger.warning("⚠️ Không thể lưu session sau {max_retries} lần thử")
                    logger.warning("⚠️ Sẽ cần đăng nhập lại mỗi lần")
            except Exception as e:
                logger.error(f"❌ Lỗi khi lưu session: {e}")
                break
    
    def load_session(self) -> Optional[dict]:
        """Load thông tin session"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'rb') as f:
                    session_data = pickle.load(f)
                
                # Kiểm tra session có còn hợp lệ không (24 giờ)
                if time.time() - session_data.get('timestamp', 0) < 86400:
                    logger.info(f"Đã load session hợp lệ từ {self.session_file}")
                    return session_data
                else:
                    logger.info("Session đã hết hạn")
        except Exception as e:
            logger.error(f"Lỗi khi load session: {e}")
        return None
    
    def is_session_valid(self) -> bool:
        """Kiểm tra session có còn hợp lệ không"""
        session = self.load_session()
        if not session:
            return False
        
        # Kiểm tra thời gian (24 giờ)
        if time.time() - session.get('timestamp', 0) > 86400:
            return False
        
        # Kiểm tra cookies có tồn tại không
        cookies = self.load_cookies()
        if not cookies:
            return False
        
        return True
    
    def clear_session(self) -> None:
        """Xóa session và cookies đã lưu"""
        try:
            if os.path.exists(self.cookies_file):
                os.remove(self.cookies_file)
                logger.info(f"Đã xóa cookies file: {self.cookies_file}")
            
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                logger.info(f"Đã xóa session file: {self.session_file}")
                
        except Exception as e:
            logger.error(f"Lỗi khi xóa session: {e}")
    
    def get_session_info(self) -> dict:
        """Lấy thông tin session hiện tại"""
        session = self.load_session()
        cookies = self.load_cookies()
        
        return {
            'session_exists': session is not None,
            'cookies_exists': cookies is not None,
            'session_valid': self.is_session_valid(),
            'session_age': time.time() - session.get('timestamp', 0) if session else 0,
            'cookies_count': len(cookies) if cookies else 0
        }
    
    def _setup_browser(self):
        """Thiết lập Selenium browser"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium chưa được cài đặt trong môi trường chạy")
        
        # Cấu hình Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--log-level=0")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Thêm headless và user data dir để tránh conflict
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")
        chrome_options.add_argument("--remote-debugging-port=0")
        
        # Khởi tạo driver - thử Chrome trước, nếu không có thì dùng Chromium
        try:
            # Thử với ChromeDriver
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Chrome driver failed: {e}, trying Chromium...")
            try:
                # Thử với Chromium
                chrome_options.binary_location = "/usr/bin/chromium"
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logger.error(f"Both Chrome and Chromium failed: {e2}")
                # Thử với service và executable_path
                try:
                    service = Service(executable_path="/usr/bin/chromedriver")
                    chrome_options.binary_location = "/usr/bin/chromium"
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e3:
                    logger.error(f"All methods failed: {e3}")
                    raise Exception(f"Không thể khởi tạo browser: {e3}")
        
        # Enable network domain để monitor requests
        driver.execute_cdp_cmd('Network.enable', {})
        
        # Thêm stealth script
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    
    def _login_to_pugo(self, driver) -> Tuple[bool, str, str]:
        """
        Đăng nhập vào pugo.vn và trả về sign header và cookie
        Trước tiên thử load session đã lưu, nếu không có thì đăng nhập mới
        Returns: (success, sign_header, cookie_string)
        """
        # Thử load session đã lưu trước
        if self.is_session_valid():
            logger.info("Sử dụng session đã lưu...")
            cookies = self.load_cookies()
            if cookies:
                # Load cookies vào browser
                driver.get("https://pugo.vn/")
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Không thể thêm cookie: {e}")
                
                # Test session bằng cách truy cập trang cần đăng nhập
                driver.get("https://pugo.vn/backend/search")
                time.sleep(2)
                
                # Kiểm tra xem có cần đăng nhập lại không
                if "dang-nhap" not in driver.current_url:
                    logger.info("Session vẫn hợp lệ, không cần đăng nhập lại")
                    session = self.load_session()
                    return True, session.get('sign_header', ''), session.get('cookie_string', '')
                else:
                    logger.info("Session không còn hợp lệ, cần đăng nhập lại")
        
        # Đăng nhập mới nếu không có session hoặc session không hợp lệ
        logger.info("Bắt đầu đăng nhập mới...")
        try:
            logger.info("Bắt đầu đăng nhập vào pugo.vn...")
            
            # Truy cập trang đăng nhập
            driver.get(self.login_url)
            time.sleep(1)
            
            # Tìm và điền email
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("Đã điền email")
            
            # Tìm và điền password
            password_input = driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("Đã điền password")
            
            # Click nút đăng nhập
            login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            login_button.click()
            logger.info("Đã click nút đăng nhập")
            
            # Chờ đăng nhập hoàn tất (pugo.vn cần 5s để chuyển màn hình)
            time.sleep(4)
            
            # Kiểm tra xem đăng nhập có thành công không
            current_url = driver.current_url
            if "dang-nhap" not in current_url:
                logger.info("Đăng nhập thành công")
                
                # Lấy cookies
                cookies = driver.get_cookies()
                cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                
                # Tìm sign header trong JavaScript
                sign_header = driver.execute_script("""
                    if (window.sign) return window.sign;
                    if (window.authToken) return window.authToken;
                    if (window.token) return window.token;
                    if (localStorage.getItem('sign')) return localStorage.getItem('sign');
                    if (sessionStorage.getItem('sign')) return sessionStorage.getItem('sign');
                    return null;
                """)
                
                if sign_header:
                    logger.info(f"Đã lấy được sign header: {sign_header[:50]}...")
                else:
                    logger.warning("Không tìm thấy sign header")
                
                # Lưu session và cookies
                session_data = {
                    'sign_header': sign_header or "",
                    'cookie_string': cookie_string,
                    'login_time': time.time(),
                    'user_agent': driver.execute_script("return navigator.userAgent")
                }
                self.save_session(session_data)
                self.save_cookies(cookies)
                
                return True, sign_header or "", cookie_string
            else:
                logger.error("Đăng nhập thất bại - vẫn ở trang đăng nhập")
                return False, "", ""
                
        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập: {e}")
            return False, "", ""
    
    
    def _call_pugo_api_selenium(self, driver, target_url: str, sign_header: str, cookie_string: str) -> Dict[str, Any]:
        """
        Mô phỏng hành động người dùng trên trang search để lấy thông tin sản phẩm
        """
        try:
            logger.info("Truy cập trang search...")
            
            # Truy cập trang search
            driver.get("https://pugo.vn/backend/search")
            time.sleep(1)
            
            # Tìm input search
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "keywordSearchProduct"))
            )
            
            # Điền URL sản phẩm
            search_input.clear()
            search_input.send_keys(target_url)
            logger.info(f"Đã điền URL: {target_url}")
            
            # Tìm và click nút search
            search_button_selectors = [
                'button[type="submit"]',
                '.btn-search',
                'input[type="submit"]',
                '.search-btn'
            ]
            
            search_button = None
            for selector in search_button_selectors:
                try:
                    search_button = driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"Tìm thấy nút search với selector: {selector}")
                    break
                except:
                    continue
            
            if search_button:
                search_button.click()
                logger.info("Đã click nút search")
            else:
                logger.error("Không tìm thấy nút search")
                return {
                    "status": "error",
                    "message": "Không tìm thấy nút search",
                    "method": "search_simulation",
                    "response_status": 404
                }
            
            # Chờ kết quả với loop 1s x 10 lần
            logger.info("Chờ kết quả từ API...")
            api_responses = []
            
            for attempt in range(10):
                logger.info(f"Lần thử {attempt + 1}/10...")
                time.sleep(1)
                
                # Lấy kết quả từ network requests
                logs = driver.get_log('performance')
                
                for log in logs:
                    message = json.loads(log['message'])
                    
                    # Lấy response data
                    if message['message']['method'] == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response['url']
                        
                        if '/item/detail' in url:
                            request_id = message['message']['params']['requestId']
                            logger.info(f"Tìm thấy API response: {url}")
                            
                            # Lấy response body
                            try:
                                response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                if response_body and 'body' in response_body:
                                    response_data = json.loads(response_body['body'])
                                    logger.info(f"Tìm thấy API response (trả ngay) ở lần thử {attempt + 1}")
                                    return {
                                        "status": "success",
                                        "data": response_data,
                                        "method": "network_monitoring",
                                        "response_status": 200
                                    }
                            except Exception as e:
                                logger.warning(f"Không lấy được response body: {e}")
                
                # Nếu tìm thấy response (dù chưa hợp lệ), tiếp tục thử
                if api_responses:
                    logger.info(f"Tìm thấy {len(api_responses)} responses, tiếp tục thử...")
            
            # Nếu sau 10 lần thử vẫn không có response hợp lệ
            if api_responses:
                logger.warning(f"Sau 10 lần thử, chỉ tìm thấy {len(api_responses)} responses không hợp lệ")
                return {
                    "status": "partial_success",
                    "data": api_responses[-1],  # Lấy response cuối cùng
                    "method": "network_monitoring",
                    "response_status": 200,
                    "message": "Response không hoàn toàn hợp lệ"
                }
            else:
                logger.error("Sau 10 lần thử, không tìm thấy API response")
                return {
                    "status": "error",
                    "message": "Không tìm thấy API response sau 10 lần thử",
                    "method": "network_monitoring",
                    "response_status": 404
                }
            
            # Fallback: Thử lấy từ JavaScript response
            try:
                response_data = driver.execute_script("""
                    // Tìm response data trong page
                    if (window.searchResult) return window.searchResult;
                    if (window.productData) return window.productData;
                    if (window.apiResponse) return window.apiResponse;
                    
                    // Tìm trong các element có chứa JSON
                    var jsonElements = document.querySelectorAll('[data-json], .json-data, .api-response');
                    for (var i = 0; i < jsonElements.length; i++) {
                        try {
                            return JSON.parse(jsonElements[i].textContent || jsonElements[i].innerHTML);
                        } catch(e) {}
                    }
                    
                    return null;
                """)
                
                if response_data:
                    logger.info("Đã lấy được response data từ page")
                    return {
                        "status": "success",
                        "data": response_data,
                        "method": "page_content",
                        "response_status": 200
                    }
            except Exception as e:
                logger.warning(f"Không lấy được data từ page: {e}")
            
            # Nếu không tìm thấy gì
            logger.warning("Không tìm thấy response data")
            return {
                "status": "error",
                "message": "Không tìm thấy response data sau khi search",
                "method": "search_simulation",
                "response_status": 404
            }
                
        except Exception as e:
            logger.error(f"Lỗi khi mô phỏng search: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract thông tin từ URL pugo.vn
        
        Args:
            url: URL cần extract (có thể là short URL hoặc direct URL)
            
        Returns:
            Dict chứa kết quả extraction với metadata đầy đủ
        """
        original_url = url
        driver = None
        
        try:
            # BƯỚC 1: Resolve URL nếu cần thiết
            logger.info(f"Starting extraction for URL: {url}")
            resolve_result = resolve_product_url(url)
            
            if not resolve_result['success']:
                error_msg = f"Cannot resolve URL: {resolve_result.get('error', 'Unknown error')}"
                logger.error(f"URL resolution failed for {url}: {error_msg}")
                return self._create_error_response(
                    message=error_msg,
                    original_url=original_url,
                    resolve_result=resolve_result
                )
            
            # Sử dụng final URL để extract
            final_url = resolve_result['final_url']
            redirect_count = resolve_result.get('redirect_count', 0)
            logger.info(f"URL resolved: {original_url} → {final_url} ({redirect_count} redirects)")
            
            if not self.can_handle(final_url):
                return self._create_error_response(
                    message="Unsupported final URL after resolution",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result
                )
        
            # BƯỚC 2: Setup browser và đăng nhập
            driver = self._setup_browser()
            login_success, sign_header, cookie_string = self._login_to_pugo(driver)
            
            if not login_success:
                return self._create_error_response(
                    message="Đăng nhập thất bại",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result
                )
            
            # BƯỚC 3: Gọi API với final URL
            api_result = self._call_pugo_api_selenium(driver, final_url, sign_header, cookie_string)
            
            # Tạo response thành công
            return {
                "status": "success" if api_result["status"] == "success" else "error",
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "pugo",
                "sourceId": self._extract_source_id(final_url),
                "login_success": login_success,
                "sign_header": sign_header,
                "cookie_string": cookie_string,
                "resolve_result": resolve_result,
                "raw_data": api_result
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi extract pugo: {e}")
            return self._create_error_response(
                message=str(e),
                original_url=original_url,
                final_url=final_url if 'final_url' in locals() else None,
                resolve_result=resolve_result if 'resolve_result' in locals() else None
            )
        finally:
            if driver:
                driver.quit()
    
    def _extract_source_id(self, url: str) -> str:
        """
        Trích xuất source ID từ URL
        
        Args:
            url: URL cần trích xuất source ID
            
        Returns:
            Source ID string hoặc empty string nếu không tìm thấy
        """
        # Pattern matching cho các loại URL khác nhau
        url_patterns = {
            "item.taobao.com": r'id=(\d+)',
            "detail.1688.com": r'/offer/(\d+)\.html',
            "pugo.vn": r'/(\d+)'
        }
        
        for domain, pattern in url_patterns.items():
            if domain in url:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
        
        return ""
    
    def _create_error_response(self, message: str, original_url: str, 
                              final_url: str = None, resolve_result: dict = None) -> Dict[str, Any]:
        """
        Tạo response lỗi chuẩn
        
        Args:
            message: Thông báo lỗi
            original_url: URL gốc
            final_url: URL cuối cùng (nếu có)
            resolve_result: Kết quả resolve (nếu có)
            
        Returns:
            Dict response lỗi chuẩn
        """
        response = {
            "status": "error",
            "message": message,
            "original_url": original_url,
            "timestamp": time.time(),
            "sourceType": "pugo"
        }
        
        if final_url:
            response["final_url"] = final_url
        if resolve_result:
            response["resolve_result"] = resolve_result
            
        return response


# Tạo instance global
extractor_pugo = ExtractorPugo()
