"""
URL Resolver Utility
Xử lý việc resolve URL redirect để lấy URL cuối cùng từ short links
"""
import requests
import logging
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class URLResolver:
    def __init__(self):
        self.timeout = 10
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://m.taobao.com/'
        }
        
        # Các domain cần resolve
        self.short_domains = [
            'e.tb.cn',
            'tb.cn', 
            's.tb.cn',
            'm.tb.cn',
            's.click.taobao.com',
            'uland.taobao.com',
            'qr.1688.com'  # Thêm hỗ trợ 1688 QR links
        ]
        
        # Các domain đích hợp lệ
        self.target_domains = [
            'detail.tmall.com',
            'item.taobao.com',
            'detail.1688.com'
        ]
        
        # Regex patterns để extract URL từ text
        # Cải thiện để xử lý URL có ký tự thừa ở cuối
        self.url_extraction_patterns = [
            # Pattern chính: URL với domain và path, dừng ở ký tự không hợp lệ
            r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?',
            # Pattern cho short links (qr.1688.com, e.tb.cn, etc.)
            r'https?://(?:qr\.1688\.com|e\.tb\.cn|tb\.cn|s\.tb\.cn|m\.tb\.cn|s\.click\.taobao\.com|uland\.taobao\.com)/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*',
            # Pattern cho full product URLs
            r'https?://(?:detail\.tmall\.com|item\.taobao\.com|detail\.1688\.com)/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*',
            # Fallback pattern cho các URL khác
            r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/[^\s]*',
        ]
        
        # Compiled patterns để tăng performance
        self.compiled_url_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.url_extraction_patterns]
    
    def is_short_url(self, url: str) -> bool:
        """Kiểm tra có phải short URL không"""
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc.lower() for domain in self.short_domains)
        except:
            return False
    
    def is_valid_target_url(self, url: str) -> bool:
        """Kiểm tra URL đích có hợp lệ không"""
        try:
            parsed = urlparse(url)
            return any(domain in parsed.netloc.lower() for domain in self.target_domains)
        except:
            return False
    
    def extract_urls_from_text(self, text: str) -> List[str]:
        """Trích xuất tất cả URL từ text có chữ trước"""
        urls = []
        
        for pattern in self.compiled_url_patterns:
            matches = pattern.findall(text)
            urls.extend(matches)
        
        # Loại bỏ duplicate và clean up
        unique_urls = list(set(urls))
        cleaned_urls = [self._clean_url(url) for url in unique_urls]
        
        return [url for url in cleaned_urls if url]
    
    def _clean_url(self, url: str) -> str:
        """Clean up URL (loại bỏ ký tự thừa ở cuối)"""
        # Loại bỏ ký tự không hợp lệ ở cuối URL
        url = url.rstrip('.,;!?）】」 ')
        
        # Loại bỏ các ký tự không phải URL character ở cuối
        import re
        url = re.sub(r'[^a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]+$', '', url)
        
        # Đảm bảo URL kết thúc hợp lệ
        if url.endswith('/'):
            url = url[:-1]
            
        return url
    
    def extract_best_url_from_text(self, text: str) -> Optional[str]:
        """Trích xuất URL tốt nhất từ text (ưu tiên URL có vẻ là sản phẩm)"""
        urls = self.extract_urls_from_text(text)
        
        if not urls:
            return None
        
        # Ưu tiên URL có chứa từ khóa sản phẩm
        product_keywords = ['taobao', 'tmall', '1688', 'item', 'detail', 'offer']
        
        for url in urls:
            if any(keyword in url.lower() for keyword in product_keywords):
                return url
        
        # Nếu không có URL nào chứa từ khóa, trả về URL đầu tiên
        return urls[0]
    
    def get_final_url(self, short_url: str) -> Dict[str, Any]:
        """
        Resolve short URL thành final URL
        Hỗ trợ cả URL thuần túy và text có chữ trước URL
        
        Args:
            short_url: URL cần resolve hoặc text chứa URL
            
        Returns:
            Dict chứa thông tin resolve result
        """
        try:
            logger.info(f"🔍 Resolving URL: {short_url}")
            
            # Kiểm tra xem input có phải là text chứa URL không
            extracted_url = None
            if not short_url.startswith(('http://', 'https://')):
                # Có thể là text chứa URL, thử extract
                extracted_url = self.extract_best_url_from_text(short_url)
                if extracted_url:
                    logger.info(f"📝 Extracted URL from text: {extracted_url}")
                    short_url = extracted_url
                else:
                    return {
                        'success': False,
                        'original_url': short_url,
                        'final_url': None,
                        'error': 'Không tìm thấy URL hợp lệ trong text',
                        'method': 'no_url_found'
                    }
            
            # Nếu đã là URL hợp lệ, return luôn
            if self.is_valid_target_url(short_url):
                return {
                    'success': True,
                    'original_url': short_url,
                    'final_url': short_url,
                    'redirect_count': 0,
                    'method': 'no_redirect_needed',
                    'extracted_from_text': extracted_url is not None
                }
            
            # Nếu không phải short URL, nhưng cũng không phải target URL
            if not self.is_short_url(short_url):
                return {
                    'success': False,
                    'original_url': short_url,
                    'final_url': None,
                    'error': 'URL không được hỗ trợ',
                    'method': 'unsupported_domain',
                    'extracted_from_text': extracted_url is not None
                }
            
            # Resolve short URL với multiple strategies
            final_url, redirect_count = self._resolve_with_strategies(short_url)
            
            logger.info(f"✅ Resolved: {short_url} → {final_url} ({redirect_count} redirects)")
            
            # Kiểm tra final URL có hợp lệ không
            if not self.is_valid_target_url(final_url):
                # Nếu không có redirect, có thể link đã hết hạn
                if redirect_count == 0:
                    error_msg = 'Link rút gọn có thể đã hết hạn hoặc không hoạt động. Vui lòng thử link đầy đủ từ trang sản phẩm.'
                else:
                    error_msg = f'Link redirect đến trang không được hỗ trợ: {final_url}'
                
                return {
                    'success': False,
                    'original_url': short_url,
                    'final_url': final_url,
                    'redirect_count': redirect_count,
                    'error': error_msg,
                    'method': 'invalid_final_url'
                }
            
            return {
                'success': True,
                'original_url': short_url,
                'final_url': final_url,
                'redirect_count': redirect_count,
                'method': 'redirect_resolved',
                'extracted_from_text': extracted_url is not None
            }
            
        except requests.Timeout:
            logger.error(f"❌ Timeout khi resolve URL: {short_url}")
            return {
                'success': False,
                'original_url': short_url,
                'final_url': None,
                'error': 'Timeout khi resolve URL',
                'method': 'timeout'
            }
            
        except requests.RequestException as e:
            logger.error(f"❌ Lỗi request khi resolve URL {short_url}: {e}")
            return {
                'success': False,
                'original_url': short_url,
                'final_url': None,
                'error': f'Lỗi request: {str(e)}',
                'method': 'request_error'
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi không xác định khi resolve URL {short_url}: {e}")
            return {
                'success': False,
                'original_url': short_url,
                'final_url': None,
                'error': f'Lỗi không xác định: {str(e)}',
                'method': 'unknown_error'
            }
    
    def _resolve_with_strategies(self, short_url: str) -> tuple:
        """
        Resolve URL: Thử HTTP redirect trước, nếu không có thì parse content
        Returns: (final_url, redirect_count)
        """
        try:
            logger.info(f"🔍 Resolving: {short_url}")
            
            # Strategy 1: Thử HTTP redirect trước
            response = requests.head(
                short_url, 
                headers=self.headers, 
                allow_redirects=True, 
                timeout=self.timeout
            )
            
            final_url = response.url
            redirect_count = len(response.history)
            
            # Nếu có redirect, return ngay
            if redirect_count > 0 or self.is_valid_target_url(final_url):
                logger.info(f"✅ HTTP redirect: {short_url} → {final_url} ({redirect_count} redirects)")
                return final_url, redirect_count
            
            # Strategy 2: Nếu không có HTTP redirect, parse content
            logger.info("No HTTP redirect, trying content parsing...")
            return self._parse_content_for_url(short_url)
            
        except requests.RequestException as e:
            logger.error(f"❌ Request failed: {e}")
            return short_url, 0
    
    def _parse_content_for_url(self, short_url: str) -> tuple:
        """
        Parse HTML content để tìm URL đích
        Returns: (final_url, redirect_count)
        """
        try:
            # GET request để lấy content
            response = requests.get(
                short_url, 
                headers=self.headers, 
                timeout=self.timeout
            )
            
            content = response.text
            logger.info(f"Got content: {len(content)} bytes")
            
            # Tìm product URLs trong content
            product_patterns = [
                r'href=["\']([^"\']*detail\.tmall\.com[^"\']*)["\']',
                r'href=["\']([^"\']*item\.taobao\.com[^"\']*)["\']',
                r'href=["\']([^"\']*detail\.1688\.com[^"\']*)["\']',
                r'url=["\']([^"\']*detail\.tmall\.com[^"\']*)["\']',
                r'url=["\']([^"\']*item\.taobao\.com[^"\']*)["\']',
                r'url=["\']([^"\']*detail\.1688\.com[^"\']*)["\']',
                r'["\']([^"\']*detail\.tmall\.com[^"\']*)["\']',
                r'["\']([^"\']*item\.taobao\.com[^"\']*)["\']',
                r'["\']([^"\']*detail\.1688\.com[^"\']*)["\']'
            ]
            
            import re
            for pattern in product_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # Filter valid URLs (có id= và đủ dài)
                    valid_matches = [m for m in matches if 'id=' in m and len(m) > 20]
                    if valid_matches:
                        final_url = valid_matches[0]
                        logger.info(f"✅ Content parsing: {short_url} → {final_url}")
                        return final_url, 1  # Simulate 1 redirect
            
            # Nếu không tìm thấy, tìm product ID
            id_patterns = [
                r'itemId["\']?\s*:\s*["\']?(\d+)["\']?',
                r'item_id["\']?\s*:\s*["\']?(\d+)["\']?',
                r'id["\']?\s*:\s*["\']?(\d{9,13})["\']?',
                r'productId["\']?\s*:\s*["\']?(\d+)["\']?',
                r'offerId=(\d+)',  # Thêm pattern cho 1688 offerId
                r'offer\.id=(\d+)',  # Thêm pattern khác cho 1688
                r'offer/(\d+)\.html'  # Thêm pattern từ URL path
            ]
            
            for pattern in id_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    product_id = matches[0]
                    
                    # Xác định domain dựa trên short_url
                    if 'qr.1688.com' in short_url or '1688.com' in short_url:
                        # Construct 1688 URL
                        final_url = f"https://detail.1688.com/offer/{product_id}.html"
                        logger.info(f"✅ 1688 ID extraction: {short_url} → {final_url}")
                    else:
                        # Construct URL (default to Taobao)
                        final_url = f"https://item.taobao.com/item.htm?id={product_id}"
                        logger.info(f"✅ ID extraction: {short_url} → {final_url}")
                    
                    return final_url, 1
            
            logger.warning("No product URL or ID found in content")
            return short_url, 0
            
        except Exception as e:
            logger.error(f"❌ Content parsing failed: {e}")
            return short_url, 0
    
    

    def extract_product_id(self, url: str) -> Optional[str]:
        """Trích xuất product ID từ URL"""
        try:
            parsed = urlparse(url)
            
            # Thử lấy từ query parameter 'id'
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            if 'id' in query_params:
                return query_params['id'][0]
            
            # Thử tìm pattern số trong URL
            import re
            match = re.search(r'(?:id=|/item/)(\d+)', url)
            if match:
                return match.group(1)
                
            return None
            
        except Exception as e:
            logger.error(f"Lỗi khi extract product ID từ {url}: {e}")
            return None

# Tạo instance global để sử dụng
url_resolver = URLResolver()

def resolve_product_url(url: str) -> Dict[str, Any]:
    """
    Hàm tiện ích để resolve URL sản phẩm
    Hỗ trợ cả URL thuần túy và text chứa URL
    
    Args:
        url: URL cần resolve hoặc text chứa URL
        
    Returns:
        Dict chứa thông tin resolve result
    """
    return url_resolver.get_final_url(url)

def extract_urls_from_text(text: str) -> List[str]:
    """
    Hàm tiện ích để extract URLs từ text
    
    Args:
        text: Text chứa URL
        
    Returns:
        List các URL được extract
    """
    return url_resolver.extract_urls_from_text(text)

def extract_best_url_from_text(text: str) -> Optional[str]:
    """
    Hàm tiện ích để extract URL tốt nhất từ text
    
    Args:
        text: Text chứa URL
        
    Returns:
        URL tốt nhất hoặc None
    """
    return url_resolver.extract_best_url_from_text(text)

def extract_product_id(url: str) -> Optional[str]:
    """
    Hàm tiện ích để extract product ID từ URL
    
    Args:
        url: URL chứa product ID
        
    Returns:
        Product ID string hoặc None
    """
    return url_resolver.extract_product_id(url)

# Test function
if __name__ == "__main__":
    # Test với các URL mẫu
    test_urls = [
        "https://e.tb.cn/h.SVYesMz1CWCGef8?tk=gGCY4DMdCiV",
        "https://detail.tmall.com/item.htm?id=777166626275",
        "https://item.taobao.com/item.htm?id=123456789",
        "https://google.com"  # Invalid URL
    ]
    
    # Test với text chứa URL
    test_texts = [
        "【淘宝】假一赔四 https://e.tb.cn/h.SU96zrxZvJOnr9h?tk=ORBN4yfCXn4 HU926 「纯欲风黑色抹胸连衣裙女2025秋法式轻熟风轻奢收腰性感宴会礼服裙」点击链接直接打开 或者 淘宝搜索直接打开",
        "【淘宝】假一赔四 https://e.tb.cn/h.SfEU0GknEMtJgix?tk=pU7M4yfCR2L tG-#22>lD 「高级感黑色针织挂脖背心女2025夏法式复古名媛风修身显瘦短款上衣」点击链接直接打开 或者 淘宝搜索直接打开",
        "Check out this product: https://detail.1688.com/offer/953742824238.html - great quality!"
    ]
    
    print("=== Test with pure URLs ===")
    for test_url in test_urls:
        result = resolve_product_url(test_url)
        print(f"\nTest URL: {test_url}")
        print(f"Result: {result}")
        
        if result['success'] and result['final_url']:
            product_id = extract_product_id(result['final_url'])
            print(f"Product ID: {product_id}")
    
    print("\n=== Test with text containing URLs ===")
    for test_text in test_texts:
        print(f"\nTest Text: {test_text[:100]}...")
        
        # Test extract URLs
        urls = extract_urls_from_text(test_text)
        print(f"Extracted URLs: {urls}")
        
        # Test extract best URL
        best_url = extract_best_url_from_text(test_text)
        print(f"Best URL: {best_url}")
        
        # Test resolve
        result = resolve_product_url(test_text)
        print(f"Resolve Result: {result}")
        
        if result['success'] and result['final_url']:
            product_id = extract_product_id(result['final_url'])
            print(f"Product ID: {product_id}")
