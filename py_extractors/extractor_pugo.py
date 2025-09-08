import re
import json
import time
import logging
import os
import pickle
from typing import Dict, Any, Optional, Tuple

# Import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
except Exception:
    webdriver = None

logger = logging.getLogger(__name__)


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
        
        # Tạo thư mục session nếu chưa có
        os.makedirs(self.session_dir, exist_ok=True)
        
    def can_handle(self, url: str) -> bool:
        """Kiểm tra xem URL có thể được xử lý bởi pugo.vn extractor không"""
        # Chấp nhận URL pugo.vn, Taobao, 1688, Tmall (vì pugo.vn có thể xử lý các URL này)
        return bool(re.search(r"pugo\.vn", url) or 
                   re.search(r"item\.taobao\.com", url) or 
                   re.search(r"detail\.1688\.com", url) or
                   re.search(r"detail\.tmall\.com", url))
    
    def save_cookies(self, cookies: list) -> None:
        """Lưu cookies vào file"""
        try:
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(cookies, f)
            logger.info(f"Đã lưu {len(cookies)} cookies vào {self.cookies_file}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu cookies: {e}")
    
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
        """Lưu thông tin session"""
        try:
            session_data['timestamp'] = time.time()
            with open(self.session_file, 'wb') as f:
                pickle.dump(session_data, f)
            logger.info(f"Đã lưu session vào {self.session_file}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu session: {e}")
    
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
        if webdriver is None:
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
                    from selenium.webdriver.chrome.service import Service
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
        """
        if not self.can_handle(url):
            return {"status": "error", "message": "Unsupported URL - not a pugo.vn URL"}
        
        try:
            driver = self._setup_browser()
            
            # Đăng nhập và lấy thông tin xác thực
            login_success, sign_header, cookie_string = self._login_to_pugo(driver)
            
            if not login_success:
                return {
                    "status": "error",
                    "message": "Đăng nhập thất bại"
                }
            
            # Gọi API để lấy thông tin sản phẩm
            api_result = self._call_pugo_api_selenium(driver, url, sign_header, cookie_string)
            
            return {
                "status": "success" if api_result["status"] == "success" else "error",
                "url": url,
                "timestamp": time.time(),
                "sourceType": "pugo",
                "sourceId": self._extract_source_id(url),
                "login_success": login_success,
                "sign_header": sign_header,
                "cookie_string": cookie_string,
                "raw_data": api_result
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi extract pugo: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            if 'driver' in locals():
                driver.quit()
    
    def _extract_source_id(self, url: str) -> str:
        """Trích xuất source ID từ URL"""
        # Có thể cần điều chỉnh dựa trên format URL thực tế
        if "item.taobao.com" in url:
            # Từ URL Taobao
            match = re.search(r'id=(\d+)', url)
            return match.group(1) if match else ""
        elif "pugo.vn" in url:
            # Từ URL pugo.vn
            match = re.search(r'/(\d+)', url)
            return match.group(1) if match else ""
        return ""


# Tạo instance global
extractor_pugo = ExtractorPugo()
