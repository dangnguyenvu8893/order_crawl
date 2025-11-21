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

        return {
            "images": product.get("images", []),
            "skuProperty": sku_properties,
            "properties": sku_properties,
            "sku": sku_list,
            "rangePrices": range_prices,
            "maxPrice": str(product.get("max_price", "0")),
            "name": product.get("name", ""),
            "sourceId": product.get("source_id", ""),
            "sourceType": product.get("platform", "nhaphangchina"),
            "url": product.get("source_url") or raw.get("url"),
            "priceText": product.get("price_text", ""),
            "priceRange": product.get("price_range", {}),
            "seller": product.get("seller", {}),
        }


transformer_nhaphangchina = TransformerNhaphangchina()


