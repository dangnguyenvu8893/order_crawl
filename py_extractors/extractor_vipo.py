import re
import json
import time
import logging
import os
import pickle
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# Import URL resolver utility
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.url_resolver import resolve_product_url

# Setup logger trước khi import selenium
logger = logging.getLogger(__name__)

# Import Selenium với error handling
try:
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.common.keys import Keys  # type: ignore
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    from selenium.webdriver.chrome.service import Service  # type: ignore
    SELENIUM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Selenium không khả dụng: {e}")
    webdriver = None
    By = None
    Keys = None
    WebDriverWait = None
    EC = None
    Options = None
    Service = None
    SELENIUM_AVAILABLE = False

# Import requests cho API call
try:
    import requests  # type: ignore
    REQUESTS_AVAILABLE = True
except ImportError:
    logger.warning("Requests library không khả dụng")
    REQUESTS_AVAILABLE = False


class ExtractorVipo:
    def __init__(self) -> None:
        self.login_url = "https://vipomall.vn/start/login"
        self.api_base_url = "https://api-vipo.viettelpost.vn/listing/product/detail"
        self.phone = "0773376706"
        self.password = "Dom@21731823"
        
        # Đường dẫn lưu trữ session
        self.session_dir = "/app/logs/sessions"
        self.cookies_file = os.path.join(self.session_dir, "vipo_cookies.pkl")
        self.session_file = os.path.join(self.session_dir, "vipo_session.pkl")
        
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
            "/tmp/vipo_sessions",
            "/app/tmp/sessions", 
            os.path.expanduser("~/vipo_sessions"),
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
                self.cookies_file = os.path.join(self.session_dir, "vipo_cookies.pkl")
                self.session_file = os.path.join(self.session_dir, "vipo_session.pkl")
                logger.info(f"✓ Using fallback session directory: {self.session_dir}")
                return
            except Exception as e:
                logger.debug(f"Fallback directory {fallback_dir} failed: {e}")
                continue
        
        # Strategy 3: Sử dụng tempfile (cuối cùng)
        try:
            import tempfile
            self.session_dir = tempfile.mkdtemp(prefix="vipo_sessions_")
            self.cookies_file = os.path.join(self.session_dir, "vipo_cookies.pkl")
            self.session_file = os.path.join(self.session_dir, "vipo_session.pkl")
            logger.warning(f"⚠️ Using temporary session directory: {self.session_dir}")
            logger.warning("⚠️ Sessions will not persist between container restarts")
        except Exception as e:
            logger.error(f"❌ All session directory strategies failed: {e}")
            raise Exception("Không thể tạo thư mục session với bất kỳ strategy nào")
    
    def can_handle(self, url: str) -> bool:
        """
        Kiểm tra xem URL có thể được xử lý bởi vipo extractor không
        
        Args:
            url: URL cần kiểm tra
            
        Returns:
            True nếu URL được hỗ trợ, False nếu không
        """
        # Vipo có thể handle tất cả URLs (taobao, tmall, 1688, etc.)
        # Vì Vipo là platform trung gian
        supported_domains = [
            r"item\.taobao\.com",
            r"detail\.tmall\.com",
            r"detail\.1688\.com",
            r"e\.tb\.cn",
            r"tb\.cn",
            r"s\.tb\.cn",
            r"qr\.1688\.com",
            r"vipomall\.vn"
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
                    try:
                        os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
                        logger.info(f"🔄 Retrying với thư mục mới...")
                    except Exception as retry_e:
                        logger.warning(f"⚠️ Retry failed: {retry_e}")
                else:
                    logger.warning("⚠️ Không thể lưu cookies sau {max_retries} lần thử")
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
                    try:
                        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
                        logger.info(f"🔄 Retrying với thư mục mới...")
                    except Exception as retry_e:
                        logger.warning(f"⚠️ Retry failed: {retry_e}")
                else:
                    logger.warning("⚠️ Không thể lưu session sau {max_retries} lần thử")
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
        
        # Kiểm tra token có tồn tại không
        if not session.get('vipo_access_token'):
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
        
        # Cấu hình Chrome options (theo pattern Pugo)
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
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data-vipo")
        chrome_options.add_argument("--remote-debugging-port=0")
        
        # Khởi tạo driver - thử Chrome trước, nếu không có thì dùng Chromium
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Chrome driver failed: {e}, trying Chromium...")
            try:
                chrome_options.binary_location = "/usr/bin/chromium"
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logger.error(f"Both Chrome and Chromium failed: {e2}")
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
    
    def _login_to_vipo(self, driver) -> Tuple[bool, str]:
        """
        Đăng nhập vào vipomall.vn và trả về access token
        Trước tiên thử load session đã lưu, nếu không có thì đăng nhập mới
        Returns: (success, vipo_access_token)
        """
        # Thử load session đã lưu trước (theo pattern Pugo - không test browser mỗi lần)
        if self.is_session_valid():
            logger.info("Sử dụng session đã lưu...")
            session = self.load_session()
            if session and session.get('vipo_access_token'):
                # Với Vipo, chỉ cần token để gọi API, không cần test browser mỗi lần
                # Nếu API call thất bại (401/403) thì mới cần login lại
                token = session.get('vipo_access_token')
                logger.info("Session hợp lệ, sử dụng token đã lưu (không test browser)")
                return True, token
        
        # Đăng nhập mới nếu không có session hoặc session không hợp lệ
        logger.info("Bắt đầu đăng nhập mới...")
        try:
            logger.info("Bắt đầu đăng nhập vào vipomall.vn...")
            
            # Truy cập trang đăng nhập
            driver.get(self.login_url)
            time.sleep(3)  # Tăng thời gian chờ để page load
            
            # Kiểm tra xem đã đăng nhập sẵn chưa (có thể đã có token)
            try:
                existing_token = driver.execute_script("""
                    return localStorage.getItem('vipo_access_token');
                """)
                if existing_token:
                    logger.info("Đã tìm thấy token trong localStorage, có thể đã đăng nhập sẵn")
                    # Kiểm tra xem có ở trang chủ không
                    current_url = driver.current_url
                    if "login" not in current_url:
                        logger.info("Đã đăng nhập sẵn, sử dụng token hiện có")
                        cookies = driver.get_cookies()
                        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                        session_data = {
                            'vipo_access_token': existing_token,
                            'vipo_refresh_token': driver.execute_script("return localStorage.getItem('vipo_refresh_token');") or "",
                            'cookie_string': cookie_string,
                            'login_time': time.time(),
                            'user_agent': driver.execute_script("return navigator.userAgent")
                        }
                        self.save_session(session_data)
                        self.save_cookies(cookies)
                        return True, existing_token
            except Exception as e:
                logger.warning(f"Không thể kiểm tra token hiện có: {e}")
            
            # Thử nhiều selector cho phone input
            phone_input = None
            phone_selectors = [
                (By.ID, "emailOrPhone"),
                (By.CSS_SELECTOR, 'input[id="emailOrPhone"]'),
                (By.CSS_SELECTOR, 'input[formcontrolname="emailOrPhone"]'),
                (By.CSS_SELECTOR, 'input[type="text"]'),
                (By.NAME, "emailOrPhone")
            ]
            
            for selector_type, selector_value in phone_selectors:
                try:
                    phone_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    logger.info(f"Tìm thấy phone input với selector: {selector_type}={selector_value}")
                    break
                except Exception as e:
                    logger.debug(f"Selector {selector_type}={selector_value} không tìm thấy: {e}")
                    continue
            
            if not phone_input:
                # Log page source để debug
                logger.error("Không tìm thấy phone input với bất kỳ selector nào")
                logger.error(f"Current URL: {driver.current_url}")
                logger.error(f"Page title: {driver.title}")
                # Thử lấy token từ localStorage nếu có
                try:
                    token = driver.execute_script("return localStorage.getItem('vipo_access_token');")
                    if token:
                        logger.info("Tìm thấy token trong localStorage dù không tìm thấy form đăng nhập")
                        return True, token
                except:
                    pass
                return False, ""
            
            phone_input.clear()
            phone_input.send_keys(self.phone)
            logger.info("Đã điền SĐT")
            
            # Thử nhiều selector cho nút "Tiếp tục"
            continue_button = None
            continue_selectors = [
                (By.CSS_SELECTOR, 'button.btn-login-default'),
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, '//button[contains(text(), "Tiếp tục")]'),
                (By.XPATH, '//button[contains(text(), "tiếp tục")]'),
            ]
            
            for selector_type, selector_value in continue_selectors:
                try:
                    continue_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    logger.info(f"Tìm thấy continue button với selector: {selector_type}={selector_value}")
                    break
                except Exception as e:
                    logger.debug(f"Selector {selector_type}={selector_value} không tìm thấy: {e}")
                    continue
            
            if continue_button:
                continue_button.click()
                logger.info("Đã click nút Tiếp tục")
                time.sleep(3)  # Tăng thời gian chờ
            else:
                logger.warning("Không tìm thấy nút Tiếp tục, thử Enter")
                phone_input.send_keys(Keys.RETURN)
                time.sleep(3)
            
            # Tìm và điền mật khẩu
            password_input = None
            password_selectors = [
                (By.ID, "password"),
                (By.CSS_SELECTOR, 'input[id="password"]'),
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.NAME, "password")
            ]
            
            for selector_type, selector_value in password_selectors:
                try:
                    password_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    logger.info(f"Tìm thấy password input với selector: {selector_type}={selector_value}")
                    break
                except Exception as e:
                    logger.debug(f"Selector {selector_type}={selector_value} không tìm thấy: {e}")
                    continue
            
            if not password_input:
                logger.error("Không tìm thấy password input")
                return False, ""
            
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("Đã điền mật khẩu")
            
            # Click nút đăng nhập
            login_button = None
            login_selectors = [
                (By.CSS_SELECTOR, 'button.btn-login-default'),
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, '//button[contains(text(), "Đăng nhập")]'),
                (By.XPATH, '//button[contains(text(), "đăng nhập")]'),
            ]
            
            for selector_type, selector_value in login_selectors:
                try:
                    login_button = driver.find_element(selector_type, selector_value)
                    if login_button.is_displayed() and login_button.is_enabled():
                        logger.info(f"Tìm thấy login button với selector: {selector_type}={selector_value}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector_type}={selector_value} không tìm thấy: {e}")
                    continue
            
            if login_button:
                login_button.click()
                logger.info("Đã click nút đăng nhập")
            else:
                logger.warning("Không tìm thấy nút đăng nhập, thử Enter")
                password_input.send_keys(Keys.RETURN)
            
            # Chờ đăng nhập hoàn tất
            time.sleep(5)  # Tăng thời gian chờ
            
            # Kiểm tra xem đăng nhập có thành công không
            current_url = driver.current_url
            logger.info(f"Current URL sau khi đăng nhập: {current_url}")
            
            if "login" not in current_url:
                logger.info("Đăng nhập thành công")
                
                # Lấy cookies
                cookies = driver.get_cookies()
                cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                
                # Lấy vipo_access_token từ localStorage
                vipo_access_token = driver.execute_script("""
                    return localStorage.getItem('vipo_access_token');
                """)
                
                # Lấy vipo_refresh_token từ localStorage
                vipo_refresh_token = driver.execute_script("""
                    return localStorage.getItem('vipo_refresh_token');
                """)
                
                if vipo_access_token:
                    logger.info(f"Đã lấy được vipo_access_token: {vipo_access_token[:50]}...")
                else:
                    logger.warning("Không tìm thấy vipo_access_token")
                    # Thử lại sau 2 giây
                    time.sleep(2)
                    vipo_access_token = driver.execute_script("""
                        return localStorage.getItem('vipo_access_token');
                    """)
                    if vipo_access_token:
                        logger.info(f"Đã lấy được vipo_access_token sau retry: {vipo_access_token[:50]}...")
                
                # Lưu session và cookies
                session_data = {
                    'vipo_access_token': vipo_access_token or "",
                    'vipo_refresh_token': vipo_refresh_token or "",
                    'cookie_string': cookie_string,
                    'login_time': time.time(),
                    'user_agent': driver.execute_script("return navigator.userAgent")
                }
                self.save_session(session_data)
                self.save_cookies(cookies)
                
                return True, vipo_access_token or ""
            else:
                logger.error("Đăng nhập thất bại - vẫn ở trang đăng nhập")
                # Thử lấy token từ localStorage nếu có
                try:
                    token = driver.execute_script("return localStorage.getItem('vipo_access_token');")
                    if token:
                        logger.info("Tìm thấy token trong localStorage dù vẫn ở trang login")
                        return True, token
                except:
                    pass
                return False, ""
                
        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Thử lấy token từ localStorage nếu có
            try:
                token = driver.execute_script("return localStorage.getItem('vipo_access_token');")
                if token:
                    logger.info("Tìm thấy token trong localStorage sau khi có lỗi")
                    return True, token
            except:
                pass
            return False, ""
    
    def _search_product(self, driver, target_url: str) -> Optional[str]:
        """
        Mô phỏng search trên vipomall.vn và chờ redirect
        Returns: redirect URL hoặc None nếu thất bại
        """
        try:
            logger.info("Truy cập trang chủ vipomall.vn...")
            driver.get("https://vipomall.vn/")
            time.sleep(2)
            
            # Tìm input search
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search-navbar"))
            )
            
            # Điền URL sản phẩm
            search_input.clear()
            search_input.send_keys(target_url)
            logger.info(f"Đã điền URL: {target_url}")
            
            # Tìm và click nút search (div.input-group-prepend > img)
            search_button = driver.find_element(By.CSS_SELECTOR, 'div.input-group-prepend > img')
            search_button.click()
            logger.info("Đã click nút search")
            
            # Chờ redirect (tối đa 15 giây)
            max_wait = 15
            for i in range(max_wait):
                time.sleep(1)
                current_url = driver.current_url
                if "/san-pham/" in current_url:
                    logger.info(f"Đã redirect đến: {current_url}")
                    return current_url
            
            logger.warning("Không redirect sau 15 giây")
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi search product: {e}")
            return None
    
    def _extract_url_params(self, redirect_url: str) -> Dict[str, str]:
        """
        Extract product_id, platform_type, merchant_id từ redirect URL
        Example: https://vipomall.vn/san-pham/987315762638?platform_type=21&merchant_id=100
        """
        try:
            parsed = urlparse(redirect_url)
            product_id = parsed.path.split('/')[-1]  # Lấy phần cuối của path
            
            # Parse query params
            query_params = parse_qs(parsed.query)
            platform_type = query_params.get('platform_type', [None])[0]
            merchant_id = query_params.get('merchant_id', [None])[0]
            
            return {
                'product_id': product_id,
                'platform_type': platform_type or '21',
                'merchant_id': merchant_id or '100'
            }
        except Exception as e:
            logger.error(f"Lỗi khi extract URL params: {e}")
            return {
                'product_id': '',
                'platform_type': '21',
                'merchant_id': '100'
            }
    
    def _call_vipo_api_requests(self, product_id: str, platform_type: str, merchant_id: str, access_token: str) -> Dict[str, Any]:
        """
        Gọi Vipo API bằng requests library (phương án chính)
        """
        if not REQUESTS_AVAILABLE:
            return {
                "status": "error",
                "message": "Requests library không khả dụng"
            }
        
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'vi',
                'api-version': '1.0.3',
                'authorization': f'Bearer {access_token}',
                'content-type': 'application/json',
                'origin': 'https://vipomall.vn',
                'referer': 'https://vipomall.vn/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0'
            }
            
            payload = {
                "product_id": product_id,
                "platform_type": platform_type,
                "product_link": None,
                "merchant_id": merchant_id
            }
            
            logger.info(f"Gọi API Vipo với requests: product_id={product_id}, platform_type={platform_type}, merchant_id={merchant_id}")
            response = requests.post(
                self.api_base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '01':
                    logger.info("✓ API call thành công với requests")
                    return {
                        "status": "success",
                        "data": data.get('data', {}),
                        "method": "requests",
                        "response_status": 200
                    }
                else:
                    logger.warning(f"API trả về status không hợp lệ: {data.get('status')}")
                    return {
                        "status": "error",
                        "message": f"API status không hợp lệ: {data.get('status')}",
                        "method": "requests",
                        "response_status": response.status_code
                    }
            elif response.status_code == 401 or response.status_code == 403:
                # Token expired hoặc invalid - cần login lại
                logger.warning(f"API call thất bại do token expired/invalid: {response.status_code}")
                return {
                    "status": "token_expired",
                    "message": f"Token expired or invalid: {response.status_code}",
                    "method": "requests",
                    "response_status": response.status_code
                }
            else:
                logger.warning(f"API call thất bại: {response.status_code}")
                return {
                    "status": "error",
                    "message": f"API call failed: {response.status_code}",
                    "method": "requests",
                    "response_status": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Lỗi khi gọi API với requests: {e}")
            return {
                "status": "error",
                "message": str(e),
                "method": "requests"
            }
    
    def _call_vipo_api_selenium(self, driver, product_id: str, platform_type: str, merchant_id: str, access_token: str) -> Dict[str, Any]:
        """
        Gọi Vipo API bằng Selenium network monitoring (fallback)
        """
        try:
            logger.info("Thử gọi API với Selenium network monitoring (fallback)...")
            
            # Navigate đến trang product để trigger API call
            product_url = f"https://vipomall.vn/san-pham/{product_id}?platform_type={platform_type}&merchant_id={merchant_id}"
            driver.get(product_url)
            time.sleep(3)
            
            # Monitor network requests
            api_responses = []
            for attempt in range(10):
                time.sleep(1)
                
                # Lấy kết quả từ network requests
                logs = driver.get_log('performance')
                
                for log in logs:
                    try:
                        message = json.loads(log['message'])
                        
                        # Lấy response data
                        if message['message']['method'] == 'Network.responseReceived':
                            response = message['message']['params']['response']
                            url = response['url']
                            
                            if '/listing/product/detail' in url:
                                request_id = message['message']['params']['requestId']
                                logger.info(f"Tìm thấy API response: {url}")
                                
                                # Lấy response body
                                try:
                                    response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                    if response_body and 'body' in response_body:
                                        response_data = json.loads(response_body['body'])
                                        if response_data.get('status') == '01':
                                            logger.info(f"✓ Tìm thấy API response hợp lệ ở lần thử {attempt + 1}")
                                            return {
                                                "status": "success",
                                                "data": response_data.get('data', {}),
                                                "method": "selenium_network_monitoring",
                                                "response_status": 200
                                            }
                                        else:
                                            api_responses.append(response_data)
                                except Exception as e:
                                    logger.warning(f"Không lấy được response body: {e}")
                    except Exception:
                        continue
            
            # Nếu sau 10 lần thử vẫn không có response hợp lệ
            if api_responses:
                logger.warning(f"Sau 10 lần thử, chỉ tìm thấy {len(api_responses)} responses không hợp lệ")
                return {
                    "status": "error",
                    "message": "API response không hợp lệ",
                    "method": "selenium_network_monitoring",
                    "response_status": 200
                }
            else:
                logger.error("Sau 10 lần thử, không tìm thấy API response")
                return {
                    "status": "error",
                    "message": "Không tìm thấy API response sau 10 lần thử",
                    "method": "selenium_network_monitoring",
                    "response_status": 404
                }
                
        except Exception as e:
            logger.error(f"Lỗi khi gọi API với Selenium: {e}")
            return {
                "status": "error",
                "message": str(e),
                "method": "selenium_network_monitoring"
            }
    
    def _call_vipo_api(self, driver, product_id: str, platform_type: str, merchant_id: str, access_token: str) -> Dict[str, Any]:
        """
        Gọi Vipo API với fallback strategy: requests (chính) → Selenium (fallback)
        Nếu token expired, sẽ retry với login mới
        """
        # Phương án chính: requests
        result = self._call_vipo_api_requests(product_id, platform_type, merchant_id, access_token)
        
        if result.get('status') == 'success':
            return result
        
        # Nếu token expired, clear session và retry với login mới
        if result.get('status') == 'token_expired':
            logger.warning("Token expired, clear session và thử login lại...")
            self.clear_session()
            # Retry với login mới (sẽ được handle ở extract() level)
            return result
        
        # Fallback: Selenium network monitoring
        logger.warning("Requests thất bại, thử fallback với Selenium...")
        return self._call_vipo_api_selenium(driver, product_id, platform_type, merchant_id, access_token)
    
    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract thông tin từ URL vipomall.vn
        
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
        
            # BƯỚC 2: Setup browser và đăng nhập (optional)
            driver = self._setup_browser()
            login_success, vipo_access_token = self._login_to_vipo(driver)
            
            # Nếu không có token, thử lấy từ localStorage
            if not vipo_access_token:
                logger.warning("Không có token từ login, thử lấy từ localStorage...")
                try:
                    vipo_access_token = driver.execute_script("""
                        return localStorage.getItem('vipo_access_token');
                    """)
                    if vipo_access_token:
                        logger.info("Đã lấy được token từ localStorage")
                except Exception as e:
                    logger.warning(f"Không thể lấy token từ localStorage: {e}")
            
            if not vipo_access_token:
                return self._create_error_response(
                    message="Không có vipo_access_token để gọi API",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result
                )
            
            # BƯỚC 3: Search product và chờ redirect
            redirect_url = self._search_product(driver, final_url)
            
            if not redirect_url:
                return self._create_error_response(
                    message="Không thể search product hoặc không redirect",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result
                )
            
            # BƯỚC 4: Extract URL params từ redirect
            url_params = self._extract_url_params(redirect_url)
            product_id = url_params['product_id']
            platform_type = url_params['platform_type']
            merchant_id = url_params['merchant_id']
            
            if not product_id:
                return self._create_error_response(
                    message="Không thể extract product_id từ redirect URL",
                    original_url=original_url,
                    final_url=final_url,
                    redirect_url=redirect_url,
                    resolve_result=resolve_result
                )
            
            logger.info(f"Extracted params: product_id={product_id}, platform_type={platform_type}, merchant_id={merchant_id}")
            
            # BƯỚC 5: Gọi API với fallback strategy
            api_result = self._call_vipo_api(driver, product_id, platform_type, merchant_id, vipo_access_token)
            
            # Log kết quả API call
            logger.info(f"API call result status: {api_result.get('status')}")
            if api_result.get('status') != 'success':
                logger.error(f"API call thất bại: {api_result.get('message', 'Unknown error')}")
                logger.error(f"API result: {api_result}")
            
            # Tạo response thành công
            return {
                "status": "success" if api_result["status"] == "success" else "error",
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "vipo",
                "sourceId": product_id,
                "login_success": login_success,
                "vipo_access_token": vipo_access_token[:50] + "..." if vipo_access_token else "",
                "redirect_url": redirect_url,
                "url_params": url_params,
                "resolve_result": resolve_result,
                "raw_data": api_result
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi extract vipo: {e}")
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
            "detail.tmall.com": r'id=(\d+)',
            "vipomall.vn": r'/san-pham/(\d+)'
        }
        
        for domain, pattern in url_patterns.items():
            if domain in url:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
        
        return ""
    
    def _create_error_response(self, message: str, original_url: str, 
                              final_url: str = None, redirect_url: str = None,
                              resolve_result: dict = None, url_params: dict = None) -> Dict[str, Any]:
        """
        Tạo response lỗi chuẩn
        
        Args:
            message: Thông báo lỗi
            original_url: URL gốc
            final_url: URL cuối cùng (nếu có)
            redirect_url: Redirect URL (nếu có)
            resolve_result: Kết quả resolve (nếu có)
            url_params: URL params (nếu có)
            
        Returns:
            Dict response lỗi chuẩn
        """
        response = {
            "status": "error",
            "message": message,
            "original_url": original_url,
            "timestamp": time.time(),
            "sourceType": "vipo"
        }
        
        if final_url:
            response["final_url"] = final_url
        if redirect_url:
            response["redirect_url"] = redirect_url
        if resolve_result:
            response["resolve_result"] = resolve_result
        if url_params:
            response["url_params"] = url_params
            
        return response


# Tạo instance global
extractor_vipo = ExtractorVipo()

