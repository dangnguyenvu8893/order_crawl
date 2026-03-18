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


class ExtractorPandamall:
    def __init__(self) -> None:
        self.login_url = "https://pandamall.vn/login"
        self.api_intercept_path = "/api/pandamall/v1/item/details"
        self.email = "binhnguyendn1403@gmail.com"
        self.password = "Dom@21731823"

        # Đường dẫn lưu trữ session
        self.session_dir = "/app/logs/sessions"
        self.cookies_file = os.path.join(self.session_dir, "pandamall_cookies.pkl")
        self.session_file = os.path.join(self.session_dir, "pandamall_session.pkl")

        # TTL: 7 ngày theo JWT expiry
        self.session_ttl = 7 * 24 * 3600  # 604800 giây

        # Khởi tạo session directory với fallback
        self._init_session_directory()

    def _init_session_directory(self) -> None:
        """Khởi tạo thư mục session với fallback strategies"""
        # Strategy 1: Thử tạo thư mục chính
        try:
            os.makedirs(self.session_dir, exist_ok=True)
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
            "/tmp/pandamall_sessions",
            "/app/tmp/sessions",
            os.path.expanduser("~/pandamall_sessions"),
            os.path.join(os.getcwd(), "sessions")
        ]

        for fallback_dir in fallback_dirs:
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                test_file = os.path.join(fallback_dir, ".test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)

                self.session_dir = fallback_dir
                self.cookies_file = os.path.join(self.session_dir, "pandamall_cookies.pkl")
                self.session_file = os.path.join(self.session_dir, "pandamall_session.pkl")
                logger.info(f"✓ Using fallback session directory: {self.session_dir}")
                return
            except Exception as e:
                logger.debug(f"Fallback directory {fallback_dir} failed: {e}")
                continue

        # Strategy 3: Sử dụng tempfile (cuối cùng)
        try:
            import tempfile
            self.session_dir = tempfile.mkdtemp(prefix="pandamall_sessions_")
            self.cookies_file = os.path.join(self.session_dir, "pandamall_cookies.pkl")
            self.session_file = os.path.join(self.session_dir, "pandamall_session.pkl")
            logger.warning(f"⚠️ Using temporary session directory: {self.session_dir}")
            logger.warning("⚠️ Sessions will not persist between container restarts")
        except Exception as e:
            logger.error(f"❌ All session directory strategies failed: {e}")
            raise Exception("Không thể tạo thư mục session với bất kỳ strategy nào")

    def can_handle(self, url: str) -> bool:
        """Kiểm tra xem URL có thể được xử lý bởi pandamall extractor không"""
        supported_domains = [
            r"pandamall\.vn",
            r"item\.taobao\.com",
            r"detail\.1688\.com",
            r"detail\.tmall\.com",
            r"e\.tb\.cn",
            r"tb\.cn",
            r"s\.tb\.cn",
            r"qr\.1688\.com"
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
                        logger.info("🔄 Retrying với thư mục mới...")
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
                session_data['expires_at'] = time.time() + self.session_ttl
                with open(self.session_file, 'wb') as f:
                    pickle.dump(session_data, f)
                logger.info(f"✓ Đã lưu session vào {self.session_file}")
                return
            except PermissionError as e:
                logger.error(f"❌ Permission denied khi lưu session (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    try:
                        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
                        logger.info("🔄 Retrying với thư mục mới...")
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

                # Kiểm tra session có còn hợp lệ không (7 ngày theo JWT expiry)
                if session_data.get('expires_at', 0) > time.time():
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

        # Kiểm tra expires_at (7 ngày theo JWT)
        if session.get('expires_at', 0) <= time.time():
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
            'expires_at': session.get('expires_at', 0) if session else 0,
            'cookies_count': len(cookies) if cookies else 0
        }

    def _setup_browser(self):
        """Thiết lập Selenium browser"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium chưa được cài đặt trong môi trường chạy")

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

        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data-pandamall")
        chrome_options.add_argument("--remote-debugging-port=0")

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

        # Stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        return driver

    def _login_to_pandamall(self, driver) -> Tuple[bool, str]:
        """
        Đăng nhập vào pandamall.vn
        Trước tiên thử load session đã lưu, nếu không có thì đăng nhập mới
        Returns: (success, cookie_string)
        """
        # Thử load session đã lưu trước
        if self.is_session_valid():
            logger.info("Sử dụng session đã lưu...")
            cookies = self.load_cookies()
            if cookies:
                driver.get("https://pandamall.vn/")
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Không thể thêm cookie: {e}")

                # Inject localStorage (JWT) trước khi navigate — quan trọng vì Pandamall dùng JWT trong localStorage
                session = self.load_session()
                local_storage = session.get('local_storage') if session else None
                if local_storage:
                    try:
                        driver.execute_script(f"""
                            var data = {local_storage};
                            for (var key in data) {{ localStorage.setItem(key, data[key]); }}
                        """)
                        logger.info("✅ Đã inject localStorage (JWT) vào browser")
                    except Exception as e:
                        logger.warning(f"⚠️ Không inject được localStorage: {e}")

                # Test session bằng cách truy cập trang /account/ (trang chính sau login)
                driver.get("https://pandamall.vn/account/")
                time.sleep(2)

                if "/account" in driver.current_url:
                    logger.info(f"✅ Session vẫn hợp lệ — đang ở {driver.current_url}")
                    cookies_list = driver.get_cookies()
                    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
                    return True, cookie_string
                else:
                    logger.info("Session không còn hợp lệ, cần đăng nhập lại")

        # Đăng nhập mới
        logger.info("Bắt đầu đăng nhập mới vào pandamall.vn...")
        try:
            driver.get(self.login_url)
            time.sleep(2)

            # Điền account (email)
            account_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "account"))
            )
            account_input.clear()
            account_input.send_keys(self.email)
            logger.info("Đã điền email/account")

            # Điền password (dùng name vì type="text")
            password_input = driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("Đã điền password")

            # Click nút đăng nhập (Ant Design button)
            login_button = driver.find_element(
                By.CSS_SELECTOR, "button.ant-btn.ant-btn-primary"
            )
            login_button.click()
            logger.info("Đã click nút đăng nhập")

            # Chờ Pandamall redirect sang /account/ sau khi login
            time.sleep(4)

            current_url = driver.current_url
            if "/account" in current_url:
                logger.info(f"✅ Đăng nhập thành công — Pandamall redirect sang {current_url}")

                cookies = driver.get_cookies()
                cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

                # Lưu toàn bộ localStorage (chứa JWT Bearer token)
                local_storage = driver.execute_script("return JSON.stringify(localStorage);")
                logger.info(f"✅ Đã lấy localStorage ({len(local_storage)} bytes)")

                session_data = {
                    'cookie_string': cookie_string,
                    'local_storage': local_storage,
                    'login_time': time.time(),
                    'user_agent': driver.execute_script("return navigator.userAgent")
                }
                self.save_session(session_data)
                self.save_cookies(cookies)

                return True, cookie_string
            else:
                logger.error(f"Đăng nhập thất bại — URL hiện tại: {current_url}")
                return False, ""

        except Exception as e:
            logger.error(f"Lỗi khi đăng nhập: {e}")
            return False, ""

    def _extract_item_id(self, url: str) -> str:
        """
        Trích xuất item_id từ source URL
        1688: ID nằm trong path → /offer/123456789.html
        Taobao / Tmall: ID nằm trong query param → ?id=xxx
        """
        if "1688.com" in url:
            match = re.search(r'/offer/(\d+)\.html', url)
        else:
            match = re.search(r'id=(\d+)', url)
        return match.group(1) if match else ""

    def _detect_provider(self, url: str) -> str:
        """Detect provider từ source URL"""
        if "1688.com" in url:
            return "1688"
        elif "tmall.com" in url:
            return "tmall"
        elif "taobao.com" in url:
            return "taobao"
        return "taobao"  # default fallback

    def _call_pandamall_api_selenium(self, driver, source_url: str) -> Dict[str, Any]:
        """
        Tại trang /account/ (đã ở đây sau login):
        1. Điền source URL vào input#keyword
        2. Click submit button
        3. CDP intercept response từ /api/pandamall/v1/item/details
        """
        try:
            # Trang /account/ chính là trang search — driver đã ở đây sau login
            logger.info(f"Đang ở {driver.current_url} — tìm search box...")

            # Tìm và điền URL vào input#keyword
            keyword_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "keyword"))
            )
            keyword_input.clear()
            keyword_input.send_keys(source_url)
            logger.info(f"Đã điền URL vào input#keyword: {source_url[:80]}...")

            # Click nút search
            search_button = driver.find_element(
                By.CSS_SELECTOR, "button[type='submit'].ant-btn.ant-btn-default.button-search"
            )
            search_button.click()
            logger.info("Đã click nút search — chờ API /item/details...")

            # Sau khi bấm search, chờ và intercept /item/details
            for attempt in range(15):
                logger.info(f"Lần thử {attempt + 1}/15...")
                time.sleep(1)

                logs = driver.get_log('performance')

                for log in logs:
                    message = json.loads(log['message'])

                    if message['message']['method'] == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        resp_url = response['url']

                        if self.api_intercept_path in resp_url:
                            request_id = message['message']['params']['requestId']
                            logger.info(f"✅ Tìm thấy API response: {resp_url}")

                            try:
                                response_body = driver.execute_cdp_cmd(
                                    'Network.getResponseBody',
                                    {'requestId': request_id}
                                )
                                if response_body and 'body' in response_body:
                                    response_data = json.loads(response_body['body'])
                                    logger.info(f"✅ Lấy được response body ở lần thử {attempt + 1}")
                                    return {
                                        "status": "success",
                                        "data": response_data,
                                        "method": "network_monitoring",
                                        "response_status": 200
                                    }
                            except Exception as e:
                                logger.warning(f"Không lấy được response body: {e}")

            logger.error("Sau 15 lần thử, không tìm thấy API response /item/details")
            return {
                "status": "error",
                "message": "Không tìm thấy API response /item/details sau 15 lần thử",
                "method": "network_monitoring",
                "response_status": 404
            }

        except Exception as e:
            logger.error(f"Lỗi khi call Pandamall API: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract thông tin sản phẩm từ source URL qua Pandamall

        Args:
            url: Source URL (Taobao / 1688 / Tmall)

        Returns:
            Dict chứa kết quả extraction với metadata đầy đủ
        """
        original_url = url
        driver = None

        try:
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

            # Trích xuất item_id và provider từ URL
            item_id = self._extract_item_id(final_url)
            provider = self._detect_provider(final_url)
            logger.info(f"item_id={item_id}, provider={provider}")

            # Setup browser và đăng nhập
            driver = self._setup_browser()
            login_success, cookie_string = self._login_to_pandamall(driver)

            if not login_success:
                return self._create_error_response(
                    message="Đăng nhập thất bại",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result
                )

            # Gọi API với final URL
            api_result = self._call_pandamall_api_selenium(driver, final_url)

            return {
                "status": "success" if api_result["status"] == "success" else "error",
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "pandamall",
                "sourceId": item_id,
                "provider": provider,
                "login_success": login_success,
                "cookie_string": cookie_string,
                "resolve_result": resolve_result,
                "raw_data": api_result
            }

        except Exception as e:
            logger.error(f"Lỗi khi extract pandamall: {e}")
            return self._create_error_response(
                message=str(e),
                original_url=original_url,
                final_url=final_url if 'final_url' in locals() else None,
                resolve_result=resolve_result if 'resolve_result' in locals() else None
            )
        finally:
            if driver:
                driver.quit()

    def _create_error_response(self, message: str, original_url: str,
                               final_url: str = None, resolve_result: dict = None) -> Dict[str, Any]:
        """Tạo response lỗi chuẩn"""
        response = {
            "status": "error",
            "message": message,
            "original_url": original_url,
            "timestamp": time.time(),
            "sourceType": "pandamall"
        }

        if final_url:
            response["final_url"] = final_url
        if resolve_result:
            response["resolve_result"] = resolve_result

        return response


# Tạo instance global
extractor_pandamall = ExtractorPandamall()
