"""
URL Resolver Utility
Xử lý việc resolve URL redirect để lấy URL cuối cùng từ short links
"""
import requests
import logging
from typing import Optional, Dict, Any
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
    
    def get_final_url(self, short_url: str) -> Dict[str, Any]:
        """
        Resolve short URL thành final URL
        
        Args:
            short_url: URL cần resolve
            
        Returns:
            Dict chứa thông tin resolve result
        """
        try:
            logger.info(f"🔍 Resolving URL: {short_url}")
            
            # Nếu đã là URL hợp lệ, return luôn
            if self.is_valid_target_url(short_url):
                return {
                    'success': True,
                    'original_url': short_url,
                    'final_url': short_url,
                    'redirect_count': 0,
                    'method': 'no_redirect_needed'
                }
            
            # Nếu không phải short URL, nhưng cũng không phải target URL
            if not self.is_short_url(short_url):
                return {
                    'success': False,
                    'original_url': short_url,
                    'final_url': None,
                    'error': 'URL không được hỗ trợ',
                    'method': 'unsupported_domain'
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
                'method': 'redirect_resolved'
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
    
    Args:
        url: URL cần resolve
        
    Returns:
        Dict chứa thông tin resolve result
    """
    return url_resolver.get_final_url(url)

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
    
    for test_url in test_urls:
        result = resolve_product_url(test_url)
        print(f"\n🔍 Test URL: {test_url}")
        print(f"✅ Result: {result}")
        
        if result['success'] and result['final_url']:
            product_id = extract_product_id(result['final_url'])
            print(f"🆔 Product ID: {product_id}")
