import base64
import json
import logging
import os
import pickle
import re
import time
from typing import Any, Dict, Optional, Tuple

import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from parser_nhaphangchina import parser_nhaphangchina
from utils.url_resolver import resolve_product_url

logger = logging.getLogger(__name__)

try:
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.support import expected_conditions as EC  # type: ignore
    from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    SELENIUM_AVAILABLE = True
except ImportError as exc:  # pragma: no cover - Selenium only in runtime
    logger.warning("Selenium không khả dụng: %s", exc)
    webdriver = None
    By = None
    EC = None
    WebDriverWait = None
    Options = None
    SELENIUM_AVAILABLE = False


class ExtractorNhaphangchina:
    """Crawler flow mô phỏng pattern của Pugo nhưng cho nhaphangchina."""

    def __init__(self) -> None:
        self.base_url = "https://muahang.nhaphangchina.vn"
        self.login_url = f"{self.base_url}/login"
        self.dashboard_url = f"{self.base_url}/dashboard"
        self.search_url = f"{self.base_url}/order/searchproduct"
        self.detail_endpoint = f"{self.base_url}/order/loaddetailajax"

        self.email = os.getenv("NHAPHANGCHINA_USERNAME", "thanhbinhkd95@gmail.com")
        self.password = os.getenv("NHAPHANGCHINA_PASSWORD", "123123")

        self.session_dir = "/app/logs/sessions"
        self.cookies_file = os.path.join(
            self.session_dir, "nhaphangchina_cookies.pkl"
        )
        self.session_file = os.path.join(
            self.session_dir, "nhaphangchina_session.pkl"
        )
        self._init_session_directory()

        self.parser = parser_nhaphangchina
        self.api_monitor_attempts = 12
        self.api_monitor_interval = 1.2

    # ------------------------------------------------------------------
    # Session helpers (reuse logic từ pattern Pugo)
    # ------------------------------------------------------------------
    def _init_session_directory(self) -> None:
        try:
            os.makedirs(self.session_dir, exist_ok=True)
        except Exception as exc:
            fallback_dir = os.path.join(os.getcwd(), "sessions")
            logger.warning(
                "Không thể tạo session_dir mặc định (%s): %s. Fallback %s",
                self.session_dir,
                exc,
                fallback_dir,
            )
            os.makedirs(fallback_dir, exist_ok=True)
            self.session_dir = fallback_dir
            self.cookies_file = os.path.join(
                self.session_dir, "nhaphangchina_cookies.pkl"
            )
            self.session_file = os.path.join(
                self.session_dir, "nhaphangchina_session.pkl"
            )

    def save_cookies(self, cookies: list) -> None:
        try:
            with open(self.cookies_file, "wb") as handle:
                pickle.dump(cookies, handle)
            logger.info("Đã lưu %s cookies", len(cookies))
        except Exception as exc:
            logger.error("Không thể lưu cookies: %s", exc)

    def load_cookies(self) -> Optional[list]:
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, "rb") as handle:
                    return pickle.load(handle)
        except Exception as exc:
            logger.error("Không thể load cookies: %s", exc)
        return None

    def save_session(self, session_data: Dict[str, Any]) -> None:
        try:
            session_data["timestamp"] = time.time()
            with open(self.session_file, "wb") as handle:
                pickle.dump(session_data, handle)
        except Exception as exc:
            logger.error("Không thể lưu session: %s", exc)

    def load_session(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, "rb") as handle:
                    session_data = pickle.load(handle)
                if time.time() - session_data.get("timestamp", 0) < 86400:
                    return session_data
        except Exception as exc:
            logger.error("Không thể load session: %s", exc)
        return None

    def is_session_valid(self) -> bool:
        session = self.load_session()
        if not session:
            return False
        cookies = self.load_cookies()
        return bool(cookies)

    def clear_session(self) -> None:
        try:
            if os.path.exists(self.cookies_file):
                os.remove(self.cookies_file)
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
        except Exception as exc:
            logger.error("Không thể xóa session: %s", exc)

    def get_session_info(self) -> Dict[str, Any]:
        session = self.load_session()
        cookies = self.load_cookies()
        return {
            "session_exists": session is not None,
            "cookies_exists": cookies is not None,
            "session_age": time.time() - session.get("timestamp", 0)
            if session
            else None,
        }

    # ------------------------------------------------------------------
    # Selenium helpers
    # ------------------------------------------------------------------
    def _setup_browser(self):
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium chưa được cài đặt trong môi trường này")

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--headless=new")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    def _ensure_session(self, driver) -> Tuple[bool, str]:
        """Load session có sẵn hoặc đăng nhập mới."""
        if self.is_session_valid():
            try:
                cookies = self.load_cookies()
                if cookies:
                    driver.get(self.base_url)
                    for cookie in cookies:
                        # Selenium yêu cầu bỏ domain bắt đầu bằng .
                        cookie = cookie.copy()
                        domain = cookie.get("domain")
                        if domain and domain.startswith("."):
                            cookie["domain"] = domain.lstrip(".")
                        try:
                            driver.add_cookie(cookie)
                        except Exception:
                            continue

                    driver.get(self.dashboard_url)
                    time.sleep(1.5)
                    if "/login" not in driver.current_url:
                        session = self.load_session() or {}
                        return True, session.get("cookie_string", "")
            except Exception as exc:
                logger.warning("Session cũ không dùng được, login mới. %s", exc)

        return self._login(driver)

    def _login(self, driver) -> Tuple[bool, str]:
        try:
            driver.get(self.login_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_input = driver.find_element(By.NAME, "username")
            password_input = driver.find_element(By.NAME, "password")

            username_input.clear()
            username_input.send_keys(self.email)
            password_input.clear()
            password_input.send_keys(self.password)

            login_button = driver.find_element(
                By.CSS_SELECTOR, "input[name='login'][type='submit']"
            )
            login_button.click()

            WebDriverWait(driver, 10).until(
                EC.url_contains("/dashboard")
            )

            if "/login" in driver.current_url:
                logger.error("Đăng nhập thất bại, vẫn ở trang login")
                return False, ""

            cookies = driver.get_cookies()
            cookie_string = "; ".join(
                [f"{cookie['name']}={cookie['value']}" for cookie in cookies if "name" in cookie]
            )

            self.save_cookies(cookies)
            self.save_session(
                {
                    "cookie_string": cookie_string,
                }
            )
            return True, cookie_string

        except Exception as exc:
            logger.error("Lỗi khi đăng nhập nhaphangchina: %s", exc)
            return False, ""

    # ------------------------------------------------------------------
    # Extraction flow
    # ------------------------------------------------------------------
    def can_handle(self, url: str) -> bool:
        patterns = [
            r"muahang\.nhaphangchina\.vn",
            r"taobao\.com",
            r"tmall\.com",
            r"1688\.com",
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    def _normalize_response_body(self, body: str) -> str:
        if not body:
            return ""
        text = body.strip()
        if not text:
            return ""

        if text.startswith("{") or text.startswith("[") or text.startswith('"'):
            try:
                loaded = json.loads(text)
                if isinstance(loaded, str):
                    return loaded
                if isinstance(loaded, dict):
                    if "html" in loaded:
                        return str(loaded["html"])
                    if "data" in loaded:
                        return self._normalize_response_body(
                            loaded["data"] if isinstance(loaded["data"], str) else json.dumps(loaded["data"])
                        )
            except Exception:
                return text
        return text

    def _get_response_body(self, driver, request_id: str) -> Optional[str]:
        try:
            body = driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": request_id}
            )
        except Exception as exc:
            logger.warning("Không lấy được response body: %s", exc)
            return None

        content = body.get("body")
        if not content:
            return None

        if body.get("base64Encoded"):
            try:
                content = base64.b64decode(content).decode("utf-8", errors="ignore")
            except Exception:
                pass
        return content

    def _wait_for_detail_response(self, driver) -> Optional[Dict[str, Any]]:
        target_endpoint = "/order/loaddetailajax"

        for attempt in range(self.api_monitor_attempts):
            time.sleep(self.api_monitor_interval)
            try:
                logs = driver.get_log("performance")
            except Exception:
                logs = []

            for entry in logs:
                try:
                    message = json.loads(entry["message"])["message"]
                except Exception:
                    continue

                if message.get("method") != "Network.responseReceived":
                    continue

                response = message.get("params", {}).get("response", {})
                url = response.get("url", "")
                if target_endpoint not in url:
                    continue

                request_id = message["params"]["requestId"]
                status_code = response.get("status", 0)
                body = self._get_response_body(driver, request_id)
                if body:
                    return {
                        "status": "success",
                        "response_status": status_code,
                        "body": body,
                        "method": "network_monitoring",
                    }

        # Fallback: thử lấy trực tiếp từ modal body nếu có
        try:
            html_content = driver.execute_script(
                """
                var modal = document.querySelector('.loadajaxdetail .modal-body');
                return modal ? modal.innerHTML : null;
                """
            )
            if html_content:
                return {
                    "status": "success",
                    "response_status": 200,
                    "body": html_content,
                    "method": "dom_fallback",
                }
        except Exception:
            pass

        return None

    def _call_nhaphangchina_api_selenium(
        self, driver, final_url: str
    ) -> Dict[str, Any]:
        driver.get(self.search_url)
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "keywordSearchProduct"))
            )
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Không tìm thấy input search: {exc}",
                "method": "search_input",
            }

        search_input.clear()
        search_input.send_keys(final_url)

        button_selectors = [
            "button.btn-search",
            ".btn.btn-default.btn-search",
            "button[type='submit']",
        ]

        clicked = False
        for selector in button_selectors:
            try:
                button = driver.find_element(By.CSS_SELECTOR, selector)
                button.click()
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            return {
                "status": "error",
                "message": "Không tìm thấy nút search",
                "method": "search_button",
            }

        response = self._wait_for_detail_response(driver)
        if not response:
            return {
                "status": "error",
                "message": "Không tìm thấy response loaddetailajax",
                "method": "network_monitoring",
            }

        html_content = self._normalize_response_body(response.get("body", ""))
        parsed = (
            self.parser.parse(html_content) if html_content else {"status": "error"}
        )

        response["data"] = {
            "html": html_content,
            "parsed": parsed,
        }
        return response

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, url: str) -> Dict[str, Any]:
        original_url = url
        driver = None
        resolve_result: Dict[str, Any] = {}

        try:
            resolve_result = resolve_product_url(url)
            if not resolve_result.get("success"):
                return self._create_error_response(
                    message="Cannot resolve URL",
                    original_url=original_url,
                    resolve_result=resolve_result,
                )

            final_url = resolve_result.get("final_url") or original_url
            if not self.can_handle(final_url):
                return self._create_error_response(
                    message="Unsupported URL domain",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result,
                )

            driver = self._setup_browser()
            login_success, cookie_string = self._ensure_session(driver)
            if not login_success:
                return self._create_error_response(
                    message="Đăng nhập thất bại",
                    original_url=original_url,
                    final_url=final_url,
                    resolve_result=resolve_result,
                )

            api_result = self._call_nhaphangchina_api_selenium(driver, final_url)
            raw_data = {
                "status": api_result.get("status"),
                "method": api_result.get("method"),
                "response_status": api_result.get("response_status"),
                "data": api_result.get("data"),
                "message": api_result.get("message"),
            }

            parsed_product = (
                api_result.get("data", {}).get("parsed", {}).get("product", {})
                if api_result.get("data")
                else {}
            )

            return {
                "status": "success"
                if api_result.get("status") == "success"
                else "error",
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "nhaphangchina",
                "sourceId": parsed_product.get("source_id")
                or self._extract_source_id(final_url),
                "login_success": login_success,
                "cookie_string": cookie_string,
                "resolve_result": resolve_result,
                "raw_data": raw_data,
            }

        except Exception as exc:
            logger.error("Extractor nhaphangchina lỗi: %s", exc)
            return self._create_error_response(
                message=str(exc),
                original_url=original_url,
                final_url=resolve_result.get("final_url")
                if resolve_result
                else original_url,
                resolve_result=resolve_result,
            )
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _extract_source_id(self, url: str) -> str:
        if not url:
            return ""
        taobao = re.search(r"id=(\d+)", url)
        if taobao:
            return taobao.group(1)
        offer = re.search(r"/offer/(\d+)\.html", url)
        if offer:
            return offer.group(1)
        return ""

    def _create_error_response(
        self,
        message: str,
        original_url: str,
        final_url: Optional[str] = None,
        resolve_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resp: Dict[str, Any] = {
            "status": "error",
            "message": message,
            "original_url": original_url,
            "timestamp": time.time(),
            "sourceType": "nhaphangchina",
        }
        if final_url:
            resp["final_url"] = final_url
        if resolve_result:
            resp["resolve_result"] = resolve_result
        return resp


extractor_nhaphangchina = ExtractorNhaphangchina()


