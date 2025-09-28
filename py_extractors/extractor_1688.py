"""
1688 Extractor with URL Resolution Support
Hỗ trợ resolve short URLs trước khi extract
"""
import re
import json
import time
import logging
import os
from typing import Dict, Any

# Import URL resolver utility
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.url_resolver import resolve_product_url

logger = logging.getLogger(__name__)

class Extractor1688:
    def __init__(self) -> None:
        pass
    
    def can_handle(self, url: str) -> bool:
        """Kiểm tra xem URL có thể được xử lý bởi 1688 extractor không"""
        # Chấp nhận cả short URLs và 1688 URLs
        return bool(re.search(r"detail\.1688\.com", url) or 
                   re.search(r"e\.tb\.cn", url) or
                   re.search(r"tb\.cn", url) or
                   re.search(r"s\.tb\.cn", url))
    
    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract thông tin từ URL 1688 với hỗ trợ URL resolution
        """
        original_url = url
        
        # 🆕 BƯỚC 1: Resolve URL nếu cần thiết
        logger.info(f"🔍 Starting 1688 extraction for URL: {url}")
        resolve_result = resolve_product_url(url)
        
        if not resolve_result['success']:
            logger.error(f"❌ Cannot resolve URL {url}: {resolve_result.get('error', 'Unknown error')}")
            return {
                "status": "error", 
                "message": f"Cannot resolve URL: {resolve_result.get('error', 'Unknown error')}",
                "original_url": original_url,
                "resolve_result": resolve_result
            }
        
        # Sử dụng final URL để extract
        final_url = resolve_result['final_url']
        logger.info(f"✅ URL resolved: {original_url} → {final_url} ({resolve_result.get('redirect_count', 0)} redirects)")
        
        # Kiểm tra final URL có phải 1688 không
        if not re.search(r"detail\.1688\.com", final_url):
            return {
                "status": "error", 
                "message": "Final URL is not a 1688 product URL",
                "original_url": original_url,
                "final_url": final_url,
                "resolve_result": resolve_result
            }
        
        try:
            # TODO: Implement actual 1688 extraction logic here
            # Hiện tại return mock data để test
            source_id = self._extract_source_id(final_url)
            
            return {
                "status": "success",
                "url": final_url,
                "original_url": original_url,
                "timestamp": time.time(),
                "sourceType": "1688",
                "sourceId": source_id,
                "resolve_result": resolve_result,
                "raw_data": {
                    "result": {
                        "data": {
                            "Root": {
                                "fields": {
                                    "dataJson": {
                                        "name": f"1688 Product {source_id}",
                                        "images": ["https://example.com/image1.jpg"],
                                        "price": "100.00"
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi extract 1688: {e}")
            return {
                "status": "error",
                "message": str(e),
                "original_url": original_url,
                "final_url": final_url
            }
    
    def _extract_source_id(self, url: str) -> str:
        """Trích xuất source ID từ URL"""
        try:
            # Tìm pattern /offer/NUMBER.html
            match = re.search(r'/offer/(\d+)\.html', url)
            if match:
                return match.group(1)
                
            # Fallback: tìm số trong URL
            match = re.search(r'(\d{9,13})', url)
            return match.group(1) if match else ""
        except:
            return ""

# Tạo instance global
extractor_1688 = Extractor1688()