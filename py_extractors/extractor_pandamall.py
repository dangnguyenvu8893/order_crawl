import re
import json
import time
import logging
import os
import pickle
import threading
import uuid
import concurrent.futures
from typing import Dict, Any, Optional

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
    MAX_REQUESTS = 100  # restart Chrome sau N requests (memory management)

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

        # Persistent browser singleton state
        self._driver = None
        self._lock = threading.Lock()
        self._request_count = 0

        # Khởi tạo session directory với fallback
        self._init_session_directory()

    # ========== Session Directory ==========

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

    # ========== Session Save/Load ==========

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
                    logger.warning("⚠️ Không thể lưu cookies sau %d lần thử", max_retries)
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
                    logger.warning("⚠️ Không thể lưu session sau %d lần thử", max_retries)
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

        if session.get('expires_at', 0) <= time.time():
            return False

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
            'cookies_count': len(cookies) if cookies else 0,
            'request_count': self._request_count,
            'driver_alive': self._is_driver_alive(timeout=2.0),
        }

    # ========== Browser Management (Persistent Singleton) ==========

    def _is_driver_alive(self, timeout: float = 5.0) -> bool:
        """
        Detect cả crashed VÀ frozen browser.
        Dùng ThreadPoolExecutor để có timeout thực sự — signal.alarm không thread-safe.
        Đo được: healthy = 0.015s, frozen = trả False sau đúng timeout giây.
        """
        if self._driver is None:
            return False

        def probe():
            try:
                _ = self._driver.current_url
                return True
            except Exception:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(probe)
            try:
                return fut.result(timeout=timeout)
            except (concurrent.futures.TimeoutError, Exception):
                return False

    def _spawn_browser(self) -> None:
        """
        Spawn Chrome mới với:
        - unique user-data-dir (uuid) để tránh lock file conflict sau crash
        - Block images/fonts để giảm CDP buffer pressure (+4s improvement)
        - CDP buffer 100MB
        """
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium chưa được cài đặt trong môi trường chạy")

        uid = uuid.uuid4().hex[:8]
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--log-level=0")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--headless")
        chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-panda-{uid}")
        chrome_options.add_argument("--remote-debugging-port=0")

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Chrome driver failed: {e}, trying Chromium...")
            try:
                chrome_options.binary_location = "/usr/bin/chromium"
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logger.error(f"Chromium also failed: {e2}")
                try:
                    service = Service(executable_path="/usr/bin/chromedriver")
                    chrome_options.binary_location = "/usr/bin/chromium"
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e3:
                    raise Exception(f"Không thể khởi tạo browser: {e3}")

        # CDP: tăng buffer lên 100MB để giảm -32000 trên decimal requestId
        driver.execute_cdp_cmd('Network.enable', {
            'maxTotalBufferSize': 100 * 1024 * 1024,
            'maxResourceBufferSize': 50 * 1024 * 1024,
        })

        # Block images/fonts: giảm network noise, response body stay trong buffer lâu hơn
        driver.execute_cdp_cmd('Network.setBlockedURLs', {
            'urls': [
                '*.png', '*.jpg', '*.jpeg', '*.gif', '*.svg', '*.ico', '*.webp',
                '*.woff', '*.woff2', '*.ttf', '*.eot',
            ]
        })

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self._driver = driver
        self._request_count = 0
        logger.info(f"✅ Chrome spawned (user-data-dir: chrome-panda-{uid})")

    def _restore_session(self) -> bool:
        """
        Restore session từ file vào browser đã spawn.
        Dùng WebDriverWait(keyword) thay time.sleep để detect /account/ load xong.
        Fallback sang fresh login nếu session hết hạn.
        """
        if self.is_session_valid():
            cookies = self.load_cookies()
            session = self.load_session()
            if cookies and session:
                self._driver.get("https://pandamall.vn/")
                for cookie in cookies:
                    try:
                        self._driver.add_cookie(cookie)
                    except Exception:
                        pass

                local_storage = session.get('local_storage')
                if local_storage:
                    try:
                        self._driver.execute_script(f"""
                            var data = {local_storage};
                            for (var key in data) {{ localStorage.setItem(key, data[key]); }}
                        """)
                        logger.info("✅ Đã inject localStorage (JWT) vào browser")
                    except Exception as e:
                        logger.warning(f"⚠️ Không inject được localStorage: {e}")

                self._driver.get("https://pandamall.vn/account/")
                try:
                    WebDriverWait(self._driver, 10).until(
                        EC.presence_of_element_located((By.ID, "keyword"))
                    )
                    logger.info("✅ Session restored — đang ở /account/")
                    return True
                except Exception:
                    logger.info("Session không còn hợp lệ trên browser, sẽ đăng nhập mới")

        return self._fresh_login()

    def _fresh_login(self) -> bool:
        """Đăng nhập mới và lưu session. Dùng WebDriverWait thay time.sleep."""
        logger.info("Bắt đầu fresh login pandamall...")
        try:
            self._driver.get(self.login_url)

            account_input = WebDriverWait(self._driver, 10).until(
                EC.presence_of_element_located((By.NAME, "account"))
            )
            account_input.clear()
            account_input.send_keys(self.email)

            password_input = self._driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)

            login_button = self._driver.find_element(
                By.CSS_SELECTOR, "button.ant-btn.ant-btn-primary"
            )
            login_button.click()
            logger.info("Đã click nút đăng nhập — chờ /account/...")

            # Đợi đến khi search box xuất hiện (đồng nghĩa với redirect /account/ xong)
            WebDriverWait(self._driver, 15).until(
                EC.presence_of_element_located((By.ID, "keyword"))
            )

            cookies = self._driver.get_cookies()
            local_storage = self._driver.execute_script("return JSON.stringify(localStorage);")
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            self.save_session({
                'cookie_string': cookie_string,
                'local_storage': local_storage,
                'login_time': time.time(),
                'user_agent': self._driver.execute_script("return navigator.userAgent"),
            })
            self.save_cookies(cookies)
            logger.info("✅ Fresh login thành công, session đã lưu")
            return True

        except Exception as e:
            logger.error(f"❌ Fresh login thất bại: {e}")
            return False

    def _ensure_browser(self) -> None:
        """
        Đảm bảo browser singleton đang sống và sẵn sàng.
        Gọi bên trong lock — không thread-safe standalone.
        3 điều kiện trigger restart:
          1. _driver chưa tồn tại (startup hoặc sau crash quit)
          2. request_count >= MAX_REQUESTS (memory management)
          3. _is_driver_alive() == False (crash hoặc frozen)
        """
        needs_restart = False

        if self._driver is None:
            logger.info("Browser chưa khởi tạo — spawn mới")
            needs_restart = True
        elif self._request_count >= self.MAX_REQUESTS:
            logger.info(f"Đã xử lý {self._request_count} requests — restart Chrome định kỳ")
            needs_restart = True
        elif not self._is_driver_alive():
            logger.warning("Browser crash/frozen detected — restart")
            needs_restart = True

        if needs_restart:
            if self._driver is not None:
                try:
                    self._driver.quit()
                except Exception:
                    pass
                self._driver = None

            self._spawn_browser()
            if not self._restore_session():
                raise Exception("Không thể khôi phục session pandamall sau khi spawn browser mới")

    def _navigate_to_search(self) -> None:
        """
        Đảm bảo đang ở trang /account/ với search box sẵn sàng.
        Chỉ navigate nếu chưa ở /account/ (tránh round-trip không cần thiết).
        Dùng WebDriverWait thay time.sleep — đo được: 0.7s ổn định vs 2.3-5.4s với sleep.
        """
        try:
            if "/account" not in self._driver.current_url:
                self._driver.get("https://pandamall.vn/account/")
            WebDriverWait(self._driver, 10).until(
                EC.presence_of_element_located((By.ID, "keyword"))
            )
        except Exception as e:
            raise Exception(f"Không thể navigate về /account/ search page: {e}")

    def _cleanup_browser(self) -> None:
        """
        Cleanup sau mỗi request để giảm memory leak.
        Đo được: +6MB/req với cleanup vs ~50MB/req không cleanup.
        Plateau xảy ra sau ~15 requests — cleanup hoạt động hiệu quả.
        """
        try:
            self._driver.get("about:blank")
            self._driver.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
        except Exception:
            pass

    def initialize(self) -> None:
        """
        Gọi 1 lần khi Flask startup để warm-up browser (~7.6s).
        Sau đó các request đầu tiên sẽ warm (~1.5s) thay vì cold (~13s).
        """
        logger.info("🚀 Pandamall browser initializing (startup warm-up)...")
        acquired = self._lock.acquire(timeout=30)
        if not acquired:
            logger.error("Không thể acquire lock khi initialize — bỏ qua warm-up")
            return
        try:
            self._ensure_browser()
            logger.info("✅ Pandamall browser ready — warm-up hoàn tất")
        except Exception as e:
            logger.error(f"❌ Initialize failed (sẽ lazy-init ở request đầu tiên): {e}")
        finally:
            self._lock.release()

    # ========== API Call ==========

    def _call_pandamall_api_selenium(self, source_url: str) -> Dict[str, Any]:
        """
        Tại trang /account/ (đã navigate về đây):
        1. Drain log buffer cũ (tránh bắt response từ request trước)
        2. Điền URL vào input#keyword và click search
        3. Poll CDP logs:
           - Skip hex requestId (service worker/CORS preflight — Chrome không lưu body, -32000 guaranteed)
           - Capture decimal requestId (XHR thực — Chrome lưu body, getResponseBody thành công)
        """
        # Drain buffer cũ trước khi click — tránh bắt nhầm response từ request trước
        self._driver.get_log('performance')

        keyword_input = WebDriverWait(self._driver, 10).until(
            EC.presence_of_element_located((By.ID, "keyword"))
        )
        keyword_input.clear()
        keyword_input.send_keys(source_url)

        search_button = self._driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'].ant-btn.ant-btn-default.button-search"
        )
        search_button.click()
        logger.info(f"Đã click search — chờ API /item/details... URL: {source_url[:80]}")

        # Poll 15 lần x 1s = tối đa 15s
        for attempt in range(15):
            time.sleep(1)
            logs = self._driver.get_log('performance')

            for log in logs:
                message = json.loads(log['message'])
                if message['message']['method'] != 'Network.responseReceived':
                    continue

                params = message['message']['params']
                resp_url = params['response']['url']
                if self.api_intercept_path not in resp_url:
                    continue

                request_id = params['requestId']

                # Skip hex requestId: service worker/CORS preflight
                # Chrome không lưu body → getResponseBody luôn -32000. Không fix được.
                # Hex requestId: uppercase, length >= 16, ví dụ "9CEC4447FEC77B2C..."
                if re.match(r'^[0-9A-F]{16,}', request_id):
                    logger.info(f"Skip hex requestId (service worker): {request_id[:20]}...")
                    continue

                logger.info(f"✅ Tìm thấy API response (requestId={request_id[:20]})")
                try:
                    response_body = self._driver.execute_cdp_cmd(
                        'Network.getResponseBody',
                        {'requestId': request_id}
                    )
                    if response_body and 'body' in response_body:
                        data = json.loads(response_body['body'])
                        logger.info(f"✅ Lấy được response body ở lần thử {attempt + 1}")
                        return {
                            "status": "success",
                            "data": data,
                            "method": "network_monitoring",
                            "response_status": 200,
                        }
                except Exception as e:
                    logger.warning(f"Không lấy được response body: {e}")

        logger.error("Sau 15 lần thử, không tìm thấy API response /item/details")
        return {
            "status": "error",
            "message": "Không tìm thấy API response /item/details sau 15 lần thử",
            "method": "network_monitoring",
            "response_status": 404,
        }

    # ========== Public API ==========

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract thông tin sản phẩm từ source URL qua Pandamall.
        Sử dụng persistent browser singleton — warm request ~1.5s vs cold ~13s.

        Flow:
          resolve URL (trước lock) → acquire lock(30s) → ensure browser
          → navigate to search → call API → cleanup → release lock
        """
        original_url = url
        final_url = None
        resolve_result = None

        # Resolve URL trước lock (không cần browser, không block)
        try:
            resolve_result = resolve_product_url(url)
            if not resolve_result['success']:
                return self._create_error_response(
                    message=f"Cannot resolve URL: {resolve_result.get('error', 'Unknown error')}",
                    original_url=original_url,
                    resolve_result=resolve_result,
                )

            final_url = resolve_result['final_url']
            redirect_count = resolve_result.get('redirect_count', 0)
            logger.info(f"URL resolved: {original_url} → {final_url} ({redirect_count} redirects)")

            if not self.can_handle(final_url):
                return self._create_error_response(
                    message="Unsupported final URL after resolution",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result,
                )

            item_id = self._extract_item_id(final_url)
            provider = self._detect_provider(final_url)
            logger.info(f"item_id={item_id}, provider={provider}")

        except Exception as e:
            return self._create_error_response(message=str(e), original_url=original_url)

        # Acquire lock với timeout 30s (queue concurrent requests)
        acquired = self._lock.acquire(timeout=30)
        if not acquired:
            logger.warning(f"Lock timeout (30s) cho URL: {original_url}")
            return self._create_error_response(
                message="Server đang bận, thử lại sau (lock timeout 30s)",
                original_url=original_url,
                final_url=final_url,
                resolve_result=resolve_result,
            )

        try:
            self._ensure_browser()
            self._navigate_to_search()
            api_result = self._call_pandamall_api_selenium(final_url)
            self._request_count += 1

            return {
                "status": api_result["status"],
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "pandamall",
                "sourceId": item_id,
                "provider": provider,
                "resolve_result": resolve_result,
                "raw_data": api_result,
            }

        except Exception as e:
            logger.error(f"Lỗi khi extract pandamall: {e}")
            return self._create_error_response(
                message=str(e),
                original_url=original_url,
                final_url=final_url,
                resolve_result=resolve_result,
            )
        finally:
            self._cleanup_browser()
            self._lock.release()

    # ========== Helpers ==========

    def _extract_item_id(self, url: str) -> str:
        """
        Trích xuất item_id từ source URL
        1688: ID nằm trong path → /offer/123456789.html
        Taobao / Tmall: ID nằm trong query param → ?id=xxx
        """
        if "1688.com" in url:
            match = re.search(r'/offer/(\d+)\.html', url)
        else:
            # ✅ FIX: Dùng [?&] để chỉ match id= là query param độc lập
            # Tránh match ali_trackid=296_... (id= nằm trong tên param khác)
            match = re.search(r'[?&]id=(\d+)', url)
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

    def _create_error_response(self, message: str, original_url: str,
                               final_url: str = None, resolve_result: dict = None) -> Dict[str, Any]:
        """Tạo response lỗi chuẩn"""
        response = {
            "status": "error",
            "message": message,
            "original_url": original_url,
            "timestamp": time.time(),
            "sourceType": "pandamall",
        }
        if final_url:
            response["final_url"] = final_url
        if resolve_result:
            response["resolve_result"] = resolve_result
        return response


# Singleton instance — được Flask dùng qua import
extractor_pandamall = ExtractorPandamall()
