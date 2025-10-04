#!/usr/bin/env python3
"""
Taobao Price Extractor - Script chính để extract giá khuyến mãi
Sẵn sàng sử dụng - chỉ cần nhập URL và lấy giá
"""

import logging
import urllib.parse
import json
import time
import re
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaobaoPriceExtractor:
    def __init__(self):
        self.driver = None

    def extract_price_from_utparam(self, url: str) -> Optional[str]:
        """Extract giá từ utparam parameter trong URL"""
        try:
            logger.info("Đang extract giá từ utparam parameter...")
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            utparam_encoded = query_params.get('utparam')
            if not utparam_encoded:
                logger.info("Không tìm thấy utparam trong URL")
                return None
            
            utparam_encoded = utparam_encoded[0]
            
            try:
                utparam_decoded = urllib.parse.unquote(utparam_encoded)
                utparam_json = json.loads(utparam_decoded)
                
                item_price = utparam_json.get('item_price')
                if item_price:
                    logger.info(f"✓ Tìm thấy giá trong utparam: {item_price}")
                    return str(item_price)
                else:
                    logger.info("Không tìm thấy item_price trong utparam JSON")
                    return None
            except json.JSONDecodeError as e:
                logger.warning(f"Lỗi khi decode utparam JSON: {e}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi extract giá từ utparam: {e}")
            return None

    def setup_browser(self):
        """Setup Chrome browser"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✓ Browser setup thành công")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi khi setup browser: {e}")
            return False

    def load_taobao_page(self, url: str) -> bool:
        """Load trang Taobao"""
        try:
            logger.info(f"Đang load trang: {url}")
            self.driver.get(url)
            
            time.sleep(3)
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info("✓ Page đã load cơ bản")
            except TimeoutException:
                logger.warning("⚠️ Timeout khi chờ page load")
                return False
            
            current_title = self.driver.title
            current_url = self.driver.current_url
            logger.info(f"Current title: {current_title}")
            logger.info(f"Current URL: {current_url}")
            
            # Kiểm tra redirect
            if "login" in current_url.lower() or "block" in current_url.lower() or "verify" in current_url.lower():
                logger.warning("⚠️ Bị redirect đến trang đăng nhập hoặc bị chặn")
                return False
            
            # Chờ JavaScript load
            logger.info("Chờ JavaScript load...")
            time.sleep(15)
            
            # Kiểm tra skeleton loading
            skeleton_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='Skeleton']")
            if skeleton_elements:
                logger.info(f"Tìm thấy {len(skeleton_elements)} skeleton elements - chờ thêm...")
                time.sleep(20)
            
            # Thử scroll để trigger JavaScript
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(3)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Lỗi khi scroll: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi load trang: {e}")
            return False

    def extract_price_from_html(self) -> Optional[str]:
        """Extract giá từ HTML của trang hiện tại"""
        try:
            logger.info("Đang tìm kiếm giá trong HTML...")
            
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Tìm elements có class highlightPrice
            highlight_elements = soup.find_all(attrs={"class": re.compile(r"highlightPrice")})
            logger.info(f"Tìm thấy {len(highlight_elements)} elements có class highlightPrice")
            
            for element in highlight_elements:
                # Tìm text elements bên trong
                text_elements = element.find_all(attrs={"class": re.compile(r"text--")})
                for text_elem in text_elements:
                    text_value = text_elem.get_text(strip=True)
                    if text_value and re.match(r'^\d+\.?\d*$', text_value):
                        try:
                            price_float = float(text_value)
                            if 1 <= price_float <= 10000:  # Giá hợp lệ
                                logger.info(f"✓ Tìm thấy giá khuyến mãi: {text_value}")
                                return text_value
                        except ValueError:
                            pass
            
            # Tìm tất cả text elements có class text--
            text_elements = soup.find_all(attrs={"class": re.compile(r"text--")})
            logger.info(f"Tìm thấy {len(text_elements)} text elements")
            
            for element in text_elements:
                text_value = element.get_text(strip=True)
                if text_value and re.match(r'^\d+\.?\d*$', text_value):
                    try:
                        price_float = float(text_value)
                        if 1 <= price_float <= 10000:
                            logger.info(f"✓ Tìm thấy giá có thể là khuyến mãi: {text_value}")
                            return text_value
                    except ValueError:
                        pass
            
            logger.warning("Không tìm thấy giá khuyến mãi trong HTML")
            return None
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi extract giá từ HTML: {e}")
            return None

    def extract_price(self, url: str) -> Dict[str, Any]:
        """Extract giá chính - method chính để sử dụng"""
        try:
            logger.info(f"Bắt đầu extract giá từ: {url}")
            
            # Thử extract từ utparam trước (nhanh nhất)
            price_from_utparam = self.extract_price_from_utparam(url)
            if price_from_utparam:
                return {
                    'status': 'success',
                    'price': price_from_utparam,
                    'source': 'utparam_parameter',
                    'method': 'url_parsing'
                }
            
            # Nếu không có utparam, thử load trang
            logger.info("Không có utparam, thử load trang...")
            
            if not self.setup_browser():
                return {
                    'status': 'error',
                    'message': 'Không thể setup browser'
                }
            
            try:
                if not self.load_taobao_page(url):
                    return {
                        'status': 'error',
                        'message': 'Không thể load trang hoặc bị chặn'
                    }
                
                price_from_html = self.extract_price_from_html()
                if price_from_html:
                    return {
                        'status': 'success',
                        'price': price_from_html,
                        'source': 'html_parsing',
                        'method': 'selenium_beautifulsoup'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'Không tìm thấy giá trong HTML'
                    }
            
            finally:
                self.close_browser()
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi extract giá: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def close_browser(self):
        """Đóng browser"""
        if self.driver:
            self.driver.quit()
            logger.info("✓ Browser đã đóng")

def main():
    """Test function - sẵn sàng sử dụng"""
    print("="*60)
    print("TAOBAO PRICE EXTRACTOR")
    print("="*60)
    
    # Nhập URL từ user
    url = input("Nhập URL Taobao: ").strip()
    
    if not url:
        print("❌ Vui lòng nhập URL!")
        return
    
    # Tạo extractor và extract giá
    extractor = TaobaoPriceExtractor()
    result = extractor.extract_price(url)
    
    # Hiển thị kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ")
    print("="*60)
    
    if result['status'] == 'success':
        print(f"✅ THÀNH CÔNG!")
        print(f"💰 Giá khuyến mãi: {result['price']}")
        print(f"📊 Source: {result['source']}")
        print(f"🔧 Method: {result['method']}")
    else:
        print(f"❌ THẤT BẠI!")
        print(f"💬 Lỗi: {result['message']}")
    
    print("="*60)

if __name__ == "__main__":
    main()



