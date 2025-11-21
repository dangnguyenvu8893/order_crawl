from typing import Any, Dict, List

from parser_nhaphangchina import parser_nhaphangchina


class TransformerNhaphangchina:
    """Chuẩn hoá dữ liệu đã parse từ nhaphangchina."""

    def _ensure_parsed(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Đảm bảo luôn có parsed data."""
        if not raw:
            return {}

        raw_data = raw.get("raw_data") or raw
        data_section = raw_data.get("data") or raw_data

        parsed = data_section.get("parsed")
        html = data_section.get("html") or data_section.get("body")

        if parsed and parsed.get("status") == "success":
            return parsed

        if html:
            return parser_nhaphangchina.parse(html)

        # fallback: nếu raw_data chứa html
        if raw_data.get("html"):
            return parser_nhaphangchina.parse(raw_data["html"])

        return {"status": "error", "message": "Missing html/parsed payload"}

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        parsed = self._ensure_parsed(raw)
        if parsed.get("status") != "success":
            return {
                "success": False,
                "error": parsed.get("message", "Unable to parse nhaphangchina payload"),
            }

        product = parsed.get("product", {})
        sku_properties: List[Dict[str, Any]] = product.get("sku_properties", [])
        sku_list: List[Dict[str, Any]] = product.get("sku_list", [])
        range_prices: List[Dict[str, Any]] = product.get("range_prices", [])
        
        # Ưu tiên: Detect source type từ original_url hoặc final_url (URL sản phẩm thực tế)
        # Không dùng URL đã được resolve vì có thể bị đổi domain (tmall -> taobao)
        detect_url = raw.get("original_url") or raw.get("final_url") or product.get("source_url") or raw.get("url") or ""
        source_type = self._detect_source_type_from_url(detect_url) or product.get("platform", "nhaphangchina")
        
        url = product.get("source_url") or raw.get("url") or ""

        return {
            "images": product.get("images", []),
            "skuProperty": sku_properties,
            "properties": sku_properties,
            "sku": sku_list,
            "rangePrices": range_prices,
            "maxPrice": str(product.get("max_price", "0")),
            "name": product.get("name", ""),
            "sourceId": product.get("source_id", ""),
            "sourceType": source_type,
            "url": url,
            "priceText": product.get("price_text", ""),
            "priceRange": product.get("price_range", {}),
            "seller": product.get("seller", {}),
        }
    
    def _detect_source_type_from_url(self, url: str) -> str:
        """
        Detect source type từ URL (ưu tiên URL sản phẩm thực tế).
        Học từ pattern Pugo: specific patterns trước general.
        """
        if not url:
            return ""
        
        import re
        url_lower = url.lower()
        
        # Kiểm tra Tmall trước (specific patterns trước general)
        tmall_patterns = [
            r'detail\.tmall\.com',  # Ưu tiên: pattern cụ thể
            r'item\.tmall\.com',
            r'm\.tmall\.com',
            r'h5\.tmall\.com',
        ]
        for pattern in tmall_patterns:
            if re.search(pattern, url_lower):
                return "tmall"
        
        # Kiểm tra spm parameter (Tmall thường có spm=a21bo.tmall)
        if 'spm=a21bo.tmall' in url_lower:
            return "tmall"
        
        # Kiểm tra general tmall (fallback)
        if "tmall" in url_lower:
            return "tmall"
        
        # Kiểm tra Taobao
        if re.search(r'item\.taobao\.com', url_lower) or "taobao" in url_lower:
            return "taobao"
        
        # Kiểm tra 1688
        if re.search(r'detail\.1688\.com|offer\.1688\.com', url_lower) or "1688" in url_lower:
            return "1688"
        
        return ""


transformer_nhaphangchina = TransformerNhaphangchina()


