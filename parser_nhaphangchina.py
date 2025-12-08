import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ParserNhaphangchina:
    """Parser chuyên xử lý response của nhaphangchina loaddetailajax."""

    def parse(self, payload: Any) -> Dict[str, Any]:
        """
        Parse dữ liệu trả về từ endpoint /order/loaddetailajax.
        Payload có thể là:
            - Chuỗi JSON (bao bọc HTML)
            - Chuỗi HTML thuần
            - Dict có key html/data
        """
        html = self._extract_html(payload)
        if not html:
            return {
                "status": "error",
                "message": "Empty response",
                "html": "",
            }

        soup = BeautifulSoup(html, "html.parser")
        product = {
            "name": self._extract_name(soup),
            "source_url": self._extract_source_url(soup),
            "platform": None,
            "price_text": self._extract_price_text(soup),
            "price_range": {},
            "range_prices": [],
            "max_price": "0",
            "images": self._extract_images(soup),
            "sku_properties": self._extract_sku_properties(soup),
            "sku_list": [],
            "seller": self._extract_seller_info(soup),
            "qty_hint": self._extract_quantity_hint(soup),
            "source_id": None,
            "html": html,
        }

        product["platform"] = self._detect_platform(product["source_url"])
        product["price_range"], product["max_price"] = self._parse_price_range(
            product["price_text"]
        )

        js_array, exchange_rate = self._extract_js_array(html)
        
        # Ưu tiên: Extract price ranges từ HTML/JavaScript (có quantity thresholds)
        range_prices_from_html = self._extract_range_prices_from_html(soup, html, exchange_rate)
        if range_prices_from_html:
            product["range_prices"] = range_prices_from_html
            # Update max_price từ range_prices
            if range_prices_from_html:
                try:
                    product["max_price"] = str(
                        max(float(rp.get("price", 0)) for rp in range_prices_from_html)
                    )
                except Exception:
                    pass
        
        # Extract properties từ js_array và images từ HTML, sau đó merge lại
        if js_array:
            sku_properties_from_js = self._extract_sku_properties_from_js_array(js_array)
            if sku_properties_from_js:
                # Extract images từ HTML và merge vào properties
                image_map = self._extract_property_value_images(soup, html)
                if image_map:
                    self._enrich_properties_with_images(sku_properties_from_js, image_map)
                
                # ✅ NEW: Extract sourcePropertyId/sourceValueId từ HTML và merge vào properties
                property_value_map = self._extract_property_value_ids(soup, html)
                if property_value_map:
                    self._enrich_properties_with_ids(sku_properties_from_js, property_value_map)
                
                product["sku_properties"] = sku_properties_from_js
        
        # Fallback: Dùng HTML method nếu chưa có
        if not product["sku_properties"]:
            product["sku_properties"] = self._extract_sku_properties(soup)
        
        if js_array:
            sku_list = self._build_sku_list(js_array, exchange_rate)
            product["sku_list"] = sku_list
            
            # Fallback: Build từ SKU list nếu chưa có range_prices từ HTML
            if not product["range_prices"]:
                product["range_prices"] = self._build_range_prices_from_skus(
                    sku_list, exchange_rate
                )
            
            if not product["max_price"] and sku_list:
                try:
                    product["max_price"] = str(
                        max(float(sku["price"]) for sku in sku_list if sku["price"])
                    )
                except Exception:
                    product["max_price"] = "0"

            # Note: entry[6] trong js_array là property path (ví dụ "0:0;1:0"), không phải source_id
            # Không lấy source_id từ js_array

        # Ưu tiên: Extract source_id từ URL (chính xác hơn)
        if not product["source_id"]:
            product["source_id"] = self._extract_source_id_from_source_url(
                product["source_url"]
            )

        return {
            "status": "success",
            "html": html,
            "product": product,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_html(self, payload: Any) -> str:
        if payload is None:
            return ""

        if isinstance(payload, dict):
            if "html" in payload and isinstance(payload["html"], str):
                return payload["html"]
            if "data" in payload:
                return self._extract_html(payload["data"])
            if "body" in payload:
                return self._extract_html(payload["body"])

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")

        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return ""

            # Nếu là JSON string bao bọc HTML (ví dụ "\"<div>...</div>\"")
            if text.startswith("{") or text.startswith("[") or text.startswith('"'):
                try:
                    loaded = json.loads(text)
                    if isinstance(loaded, str):
                        return loaded
                    if isinstance(loaded, dict):
                        return self._extract_html(loaded)
                except (json.JSONDecodeError, TypeError):
                    pass
            return text

        return str(payload)

    def _extract_name(self, soup: BeautifulSoup) -> str:
        title = soup.select_one(".c-product-meta h3 a")
        if title and title.text:
            return title.text.strip()
        h3 = soup.select_one(".c-product-meta h3")
        if h3:
            return h3.text.strip()
        return ""

    def _extract_source_url(self, soup: BeautifulSoup) -> str:
        link = soup.select_one(".c-product-meta h3 a")
        if link:
            return link.get("href", "").strip()
        return ""

    def _extract_price_text(self, soup: BeautifulSoup) -> str:
        price_node = soup.select_one(".pricetb")
        return price_node.get_text(separator=" ", strip=True) if price_node else ""

    def _parse_price_range(self, price_text: str) -> Tuple[Dict[str, Any], str]:
        if not price_text:
            return ({}, "0")

        price_range = {}
        max_price = "0"

        # VND values "313,814đ - 552,163đ"
        vnd_matches = re.findall(r'([\d.,]+)\s*đ', price_text, flags=re.IGNORECASE)
        if vnd_matches:
            vnd_values = [self._normalize_number(v) for v in vnd_matches]
            price_range["min_vnd"] = min(vnd_values)
            price_range["max_vnd"] = max(vnd_values)
            max_price = str(price_range["max_vnd"])

        # Yuan values "¥80.88 - ¥142.31"
        cny_matches = re.findall(r'¥\s*([\d.]+)', price_text)
        if cny_matches:
            cny_values = [self._normalize_float(v) for v in cny_matches]
            price_range["min_cny"] = min(cny_values)
            price_range["max_cny"] = max(cny_values)
            max_price = str(price_range["max_cny"])

        return (price_range, str(max_price))

    def _normalize_number(self, value: str) -> float:
        clean = value.replace(".", "").replace(",", ".")
        try:
            return float(clean)
        except ValueError:
            return 0.0

    def _normalize_float(self, value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        images: List[str] = []
        selectors = [
            ".c-product-gallery-content img",
            ".c-product-gallery-thumbnail img",
            ".c-product-thumb img",
        ]
        for selector in selectors:
            for img in soup.select(selector):
                src = (
                    img.get("data-zoom-image")
                    or img.get("data-image")
                    or img.get("ng-src")
                    or img.get("src")
                )
                if src and src not in images:
                    images.append(src)
        return images

    def _extract_sku_properties(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract SKU properties từ HTML (ưu tiên tiếng Trung như Vipo).
        Hỗ trợ cả .detail-taobao-tmall và .detail-1688 structure.
        """
        result: List[Dict[str, Any]] = []
        
        # Method 1: Extract từ .detail-taobao-tmall .row (Taobao/Tmall structure)
        property_rows = soup.select(".detail-taobao-tmall .row")
        for row in property_rows:
            label_node = row.select_one(".c-font-bold")
            select_node = row.select_one("[data-property-select]")
            if not select_node or not label_node:
                continue

            name = label_node.get_text(strip=True)
            values: List[Dict[str, Any]] = []

            # ✅ FIX: Tìm .pd-property trong .pd-text hoặc trực tiếp trong select_node
            pd_properties = select_node.select(".pd-property")
            if not pd_properties:
                # Fallback: Tìm trong .pd-text
                pd_text = select_node.select_one(".pd-text")
                if pd_text:
                    pd_properties = pd_text.select(".pd-property")
            
            for prop in pd_properties:
                # Ưu tiên tiếng Trung: namechuan (tiếng Trung) > proptitle > property-name > text
                value_name = (
                    prop.get("namechuan")  # Ưu tiên: tiếng Trung
                    or prop.get("proptitle")  # Fallback: có thể có tiếng Trung
                    or prop.get("property-name")
                    or prop.get_text(strip=True)
                )
                entry: Dict[str, Any] = {"name": value_name.strip() if value_name else ""}
                
                # ✅ NEW: Extract property-value để lấy prop_id:value_id
                property_value = prop.get("property-value")
                if property_value:
                    # Format: "1627207:41168072016" -> prop_id:value_id
                    parts = property_value.split(":")
                    if len(parts) == 2:
                        try:
                            prop_id = int(parts[0])
                            value_id = int(parts[1])
                            entry["sourcePropertyId"] = prop_id
                            entry["sourceValueId"] = value_id
                        except (ValueError, TypeError):
                            pass  # Ignore nếu không parse được
                
                # ✅ FIX: Tìm img trong .img-detail hoặc bất kỳ img nào trong prop
                img = prop.select_one("img.img-detail") or prop.select_one("img")
                if img:
                    # ✅ FIX: Ưu tiên ng-src (AngularJS), sau đó data-image, cuối cùng src
                    image_url = (
                        img.get("ng-src") or 
                        img.get("data-image") or 
                        img.get("src")
                    )
                    if image_url:
                        # ✅ FIX: Clean URL - remove CORS proxy nếu có
                        if "cors-anywhere" in image_url:
                            # Extract original URL từ CORS proxy
                            import re
                            match = re.search(r'url=([^&]+)', image_url)
                            if match:
                                import urllib.parse
                                image_url = urllib.parse.unquote(match.group(1))
                        entry["image"] = image_url
                values.append(entry)

            if name and values:
                result.append({"name": name, "values": values})
        
        # Method 2: Extract từ .detail-1688 table (1688 structure - từ HTML user cung cấp)
        if not result:
            detail_1688 = soup.select_one(".detail-1688")
            if detail_1688:
                # Tìm table protable
                protable = detail_1688.select_one("table.protable")
                if protable:
                    # Extract từ table rows - mỗi row là một SKU variant
                    # Properties được extract từ js_array thay vì table
                    # Table chỉ hiển thị SKU variants, không phải properties list
                    pass  # Properties sẽ được extract từ js_array trong _build_sku_list
        
        # Method 3: Extract từ js_array nếu có (fallback - properties trong spec_display)
        # Note: js_array đã được dùng trong _build_sku_list, nhưng properties structure
        # cần được extract riêng từ HTML selectors hoặc từ js_array structure khác
        
        return result

    def _extract_sku_properties_from_js_array(
        self, js_array: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract SKU properties từ js_array (ưu tiên tiếng Trung như Vipo).
        Format: "0:0:颜色:白色;1:0:尺码:S" -> properties: [颜色: [白色], 尺码: [S, M, L, XL]]
        """
        result: List[Dict[str, Any]] = []
        properties_map: Dict[str, Dict[str, Any]] = {}  # {property_name: {values: set, index: int}}
        
        for key, value in js_array.items():
            if not isinstance(value, list) or len(value) < 3:
                continue
            
            spec_display = value[2] if len(value) > 2 else ""
            if not spec_display:
                continue
            
            # Parse spec_display: "0:0:颜色:白色;1:0:尺码:S"
            for chunk in spec_display.split(";"):
                chunk = chunk.strip()
                if not chunk or ":" not in chunk:
                    continue
                
                parts = chunk.split(":")
                if len(parts) >= 4:
                    # Format: "0:0:颜色:白色"
                    prop_index = parts[0]  # "0"
                    value_index = parts[1]  # "0"
                    prop_name = parts[2]  # "颜色" (tiếng Trung)
                    value_name = parts[3]  # "白色" (tiếng Trung)
                    
                    if prop_name not in properties_map:
                        properties_map[prop_name] = {
                            "name": prop_name,
                            "values": set(),
                            "index": int(prop_index) if prop_index.isdigit() else 999
                        }
                    
                    properties_map[prop_name]["values"].add(value_name)
        
        # Convert to list và sort theo index
        for prop_name, prop_data in sorted(
            properties_map.items(), key=lambda x: x[1]["index"]
        ):
            values_list = [
                {"name": val} for val in sorted(prop_data["values"])
            ]
            result.append({
                "name": prop_data["name"],
                "values": values_list
            })
        
        return result

    def _extract_property_value_images(self, soup: BeautifulSoup, html_str: str = "") -> Dict[str, str]:
        """
        Extract image URLs cho property values từ HTML.
        Returns: {value_name: image_url} mapping
        
        Dùng regex trực tiếp vì BeautifulSoup có thể không parse đúng
        structure phức tạp của AngularJS templates.
        """
        image_map: Dict[str, str] = {}
        
        # Dùng regex trực tiếp để extract namechuan + ng-src pairs
        # Structure: <div class="pd-property" namechuan="..." ...> ... <img ng-src="..." />
        if not html_str:
            html_str = str(soup) if hasattr(soup, '__str__') else str(soup.prettify())
        
        pattern = r'<div[^>]*class=\"[^\"]*pd-property[^\"]*\"[^>]*namechuan=\"([^\"]+)\"[^>]*>.*?<img[^>]*ng-src=\"([^\"]+)\"'
        matches = re.findall(pattern, html_str, re.DOTALL | re.IGNORECASE)
        
        for namechuan, ng_src in matches:
            if not namechuan or not ng_src:
                continue
            
            # Clean URL - remove CORS proxy nếu có
            image_url = ng_src
            if "cors-anywhere" in image_url or "jancargo.com" in image_url:
                import urllib.parse
                # Extract URL từ query parameter
                match = re.search(r'url=([^&]+)', image_url)
                if match:
                    image_url = urllib.parse.unquote(match.group(1))
                else:
                    # Fallback: Try to extract from path
                    parsed = urllib.parse.urlparse(image_url)
                    if parsed.path and "url=" in parsed.path:
                        match = re.search(r'url=([^&]+)', parsed.path)
                        if match:
                            image_url = urllib.parse.unquote(match.group(1))
            
            # Normalize name
            normalized_name = namechuan.strip()
            
            # Store both original and normalized for flexible matching
            image_map[normalized_name] = image_url
            image_map[normalized_name.lower()] = image_url
        
        # Fallback: Dùng BeautifulSoup nếu regex không tìm thấy gì
        if not image_map:
            select_nodes = soup.select("[data-property-select]")
            
            if not select_nodes:
                property_rows = soup.select(".detail-taobao-tmall .row")
                if not property_rows:
                    property_rows = soup.select(".row")
                
                for row in property_rows:
                    if row.get("data-property-select"):
                        select_nodes.append(row)
            
            for select_node in select_nodes:
                pd_text = select_node.select_one(".pd-text")
                if pd_text:
                    pd_properties = pd_text.select(".pd-property")
                else:
                    pd_properties = select_node.select(".pd-property")
                
                for prop in pd_properties:
                    value_name = (
                        prop.get("namechuan") or
                        prop.get("proptitle") or
                        prop.get("property-name") or
                        prop.get_text(strip=True)
                    )
                    
                    if not value_name:
                        continue
                    
                    normalized_name = value_name.strip()
                    item_image = prop.select_one(".item-image img") or prop.select_one(".pd-item-search img")
                    img = item_image or prop.select_one("img.img-detail") or prop.select_one("img")
                    
                    if img:
                        image_url = (
                            img.get("ng-src") or 
                            img.get("data-image") or 
                            img.get("src")
                        )
                        if image_url:
                            if "cors-anywhere" in image_url or "jancargo.com" in image_url:
                                import urllib.parse
                                match = re.search(r'url=([^&]+)', image_url)
                                if match:
                                    image_url = urllib.parse.unquote(match.group(1))
                            
                            image_map[normalized_name] = image_url
                            image_map[normalized_name.lower()] = image_url
        
        return image_map

    def _enrich_properties_with_images(
        self, 
        properties: List[Dict[str, Any]], 
        image_map: Dict[str, str]
    ) -> None:
        """
        Enrich properties với images từ image_map.
        Modifies properties in-place.
        """
        matched_count = 0
        for prop in properties:
            if not isinstance(prop, dict) or "values" not in prop:
                continue
            
            for value in prop.get("values", []):
                if not isinstance(value, dict) or "name" not in value:
                    continue
                
                value_name = value.get("name", "").strip()
                if not value_name:
                    continue
                
                # Try exact match first
                if value_name in image_map:
                    value["image"] = image_map[value_name]
                    matched_count += 1
                    continue
                
                # Try case-insensitive match
                value_name_lower = value_name.lower()
                if value_name_lower in image_map:
                    value["image"] = image_map[value_name_lower]
                    matched_count += 1
                    continue
                
                # Try partial match (for values with extra text)
                # Example: "白色【大标款】" might match "白色"
                # Only match if one is a substring of the other (avoid false positives)
                best_match = None
                best_match_len = 0
                for map_key, map_image in image_map.items():
                    # Skip lowercase keys (already tried above)
                    if map_key.islower() and map_key != value_name_lower:
                        continue
                    # Check if one contains the other (but prefer longer matches)
                    if value_name in map_key or map_key in value_name:
                        match_len = min(len(value_name), len(map_key))
                        if match_len > best_match_len:
                            best_match = map_image
                            best_match_len = match_len
                
                if best_match:
                    value["image"] = best_match
                    matched_count += 1

    def _extract_property_value_ids(self, soup: BeautifulSoup, html_str: str = "") -> Dict[str, Dict[str, int]]:
        """
        Extract sourcePropertyId và sourceValueId từ HTML property-value attribute.
        Returns: {value_name: {sourcePropertyId: int, sourceValueId: int}} mapping
        
        Format: property-value="1627207:41168072016" -> prop_id:value_id
        """
        id_map: Dict[str, Dict[str, int]] = {}
        
        if not html_str:
            html_str = str(soup) if hasattr(soup, '__str__') else str(soup.prettify())
        
        # Dùng regex để extract namechuan + property-value pairs
        # Structure: <div class="pd-property" namechuan="..." property-value="1627207:41168072016" ...>
        pattern = r'<div[^>]*class="[^\"]*pd-property[^\"]*"[^>]*namechuan="([^\"]+)"[^>]*property-value="([^\"]+)"'
        matches = re.findall(pattern, html_str, re.DOTALL | re.IGNORECASE)
        
        for namechuan, property_value in matches:
            if not namechuan or not property_value:
                continue
            
            # Parse property-value: "1627207:41168072016"
            parts = property_value.split(":")
            if len(parts) == 2:
                try:
                    prop_id = int(parts[0])
                    value_id = int(parts[1])
                    normalized_name = namechuan.strip()
                    id_map[normalized_name] = {
                        "sourcePropertyId": prop_id,
                        "sourceValueId": value_id
                    }
                    # Also store lowercase for case-insensitive matching
                    id_map[normalized_name.lower()] = {
                        "sourcePropertyId": prop_id,
                        "sourceValueId": value_id
                    }
                except (ValueError, TypeError):
                    continue  # Ignore nếu không parse được
        
        # Fallback: Dùng BeautifulSoup nếu regex không tìm thấy gì
        if not id_map:
            select_nodes = soup.select("[data-property-select]")
            
            if not select_nodes:
                property_rows = soup.select(".detail-taobao-tmall .row")
                if not property_rows:
                    property_rows = soup.select(".row")
                
                for row in property_rows:
                    if row.get("data-property-select"):
                        select_nodes.append(row)
            
            for select_node in select_nodes:
                pd_text = select_node.select_one(".pd-text")
                if pd_text:
                    pd_properties = pd_text.select(".pd-property")
                else:
                    pd_properties = select_node.select(".pd-property")
                
                for prop in pd_properties:
                    value_name = (
                        prop.get("namechuan") or
                        prop.get("proptitle") or
                        prop.get("property-name") or
                        prop.get_text(strip=True)
                    )
                    
                    if not value_name:
                        continue
                    
                    normalized_name = value_name.strip()
                    property_value = prop.get("property-value")
                    
                    if property_value:
                        parts = property_value.split(":")
                        if len(parts) == 2:
                            try:
                                prop_id = int(parts[0])
                                value_id = int(parts[1])
                                id_map[normalized_name] = {
                                    "sourcePropertyId": prop_id,
                                    "sourceValueId": value_id
                                }
                                id_map[normalized_name.lower()] = {
                                    "sourcePropertyId": prop_id,
                                    "sourceValueId": value_id
                                }
                            except (ValueError, TypeError):
                                continue
        
        return id_map

    def _enrich_properties_with_ids(
        self, 
        properties: List[Dict[str, Any]], 
        id_map: Dict[str, Dict[str, int]]
    ) -> None:
        """
        Enrich properties với sourcePropertyId/sourceValueId từ id_map.
        Modifies properties in-place.
        """
        # Extract sourcePropertyId từ property name (lấy từ value đầu tiên của mỗi property)
        for prop in properties:
            if not isinstance(prop, dict) or "values" not in prop:
                continue
            
            # Lấy sourcePropertyId từ value đầu tiên (tất cả values cùng property có cùng prop_id)
            prop_id_set = False
            for value in prop.get("values", []):
                if not isinstance(value, dict) or "name" not in value:
                    continue
                
                value_name = value.get("name", "").strip()
                if not value_name:
                    continue
                
                # Try exact match first
                if value_name in id_map:
                    ids = id_map[value_name]
                    if "sourcePropertyId" in ids:
                        prop["sourcePropertyId"] = ids["sourcePropertyId"]
                        prop_id_set = True
                    if "sourceValueId" in ids:
                        value["sourceValueId"] = ids["sourceValueId"]
                    continue
                
                # Try case-insensitive match
                value_name_lower = value_name.lower()
                if value_name_lower in id_map:
                    ids = id_map[value_name_lower]
                    if "sourcePropertyId" in ids and not prop_id_set:
                        prop["sourcePropertyId"] = ids["sourcePropertyId"]
                        prop_id_set = True
                    if "sourceValueId" in ids:
                        value["sourceValueId"] = ids["sourceValueId"]
                    continue
                
                # Try partial match (for values with extra text)
                best_match = None
                best_match_len = 0
                for map_key, map_ids in id_map.items():
                    # Skip lowercase keys (already tried above)
                    if map_key.islower() and map_key != value_name_lower:
                        continue
                    # Check if one contains the other
                    if value_name in map_key or map_key in value_name:
                        match_len = min(len(value_name), len(map_key))
                        if match_len > best_match_len:
                            best_match = map_ids
                            best_match_len = match_len
                
                if best_match:
                    if "sourcePropertyId" in best_match and not prop_id_set:
                        prop["sourcePropertyId"] = best_match["sourcePropertyId"]
                        prop_id_set = True
                    if "sourceValueId" in best_match:
                        value["sourceValueId"] = best_match["sourceValueId"]

    def _extract_seller_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        seller_info: Dict[str, Any] = {}
        review_block = soup.select_one(".c-product-review")
        if review_block:
            text = review_block.get_text(" ", strip=True)
            if text:
                seller_info["text"] = text

        shop_link = soup.select_one(".c-product-review a[target='_blank']")
        if shop_link:
            seller_info["shop_url"] = shop_link.get("href")
            seller_info["platform_label"] = shop_link.get_text(strip=True)
        return seller_info

    def _extract_quantity_hint(self, soup: BeautifulSoup) -> Optional[str]:
        qty_node = soup.select_one("[morcount]")
        if not qty_node:
            qty_node = soup.select_one(".pd-row [mor]")
        return qty_node.text.strip() if qty_node and qty_node.text else None

    def _extract_js_array(self, html: str) -> Tuple[Dict[str, Any], Optional[float]]:
        js_array_pattern = re.compile(
            r"var\s+js_array\s*=\s*(\{.*?\})\s*;", re.DOTALL | re.IGNORECASE
        )
        match = js_array_pattern.search(html)
        if not match:
            return {}, None

        json_text = match.group(1)
        try:
            js_data = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("Không parse được js_array JSON")
            return {}, None

        rate_match = re.search(r"var\s+tygia\s*=\s*(\d+(?:\.\d+)?)", html)
        exchange_rate = float(rate_match.group(1)) if rate_match else None

        return js_data, exchange_rate

    def _build_sku_list(
        self, js_array: Dict[str, Any], exchange_rate: Optional[float]
    ) -> List[Dict[str, Any]]:
        sku_list: List[Dict[str, Any]] = []
        for key, value in js_array.items():
            if not isinstance(value, list) or len(value) < 5:
                continue

            sku_id = str(value[0])
            spec_display = value[2] if len(value) > 2 else ""
            price = str(value[3])
            stock = str(value[4])

            spec_attrs = self._normalize_spec_display(spec_display)
            entry: Dict[str, Any] = {
                "skuId": sku_id,
                "specAttrs": spec_attrs,
                "price": price,
                "canBookCount": stock,
            }
            if exchange_rate:
                try:
                    entry["price_vnd"] = round(float(price) * exchange_rate, 2)
                except Exception:
                    entry["price_vnd"] = None

            sku_list.append(entry)

        return sku_list

    def _normalize_spec_display(self, spec: str) -> str:
        if not spec:
            return ""

        parts = []
        for chunk in spec.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" in chunk:
                pieces = chunk.split(":")
                # lấy phần text sau tham số cuối cùng
                parts.append(pieces[-1])
            else:
                parts.append(chunk)

        return "|".join(parts)

    def _extract_range_prices_from_html(
        self, soup: BeautifulSoup, html: str, exchange_rate: Optional[float]
    ) -> List[Dict[str, Any]]:
        """
        Extract price ranges từ HTML (wholesale-prices table hoặc JavaScript).
        Ưu tiên: JavaScript variables (priceRange, priceValue) > HTML table > cart_price_table.
        """
        ranges = []
        
        # Method 1: Extract từ JavaScript variables (priceRange, priceValue)
        price_range_pattern = re.compile(
            r'var\s+priceRange\s*=\s*\[(.*?)\];', re.DOTALL | re.IGNORECASE
        )
        price_value_pattern = re.compile(
            r'var\s+priceValue\s*=\s*\[(.*?)\];', re.DOTALL | re.IGNORECASE
        )
        
        price_range_match = price_range_pattern.search(html)
        price_value_match = price_value_pattern.search(html)
        
        if price_range_match and price_value_match:
            try:
                # Parse arrays: [1,200,1000] và [41.0,40.0,39.0]
                price_ranges_str = price_range_match.group(1).strip()
                price_values_str = price_value_match.group(1).strip()
                
                # Extract numbers từ strings
                price_ranges = [
                    int(x.strip()) for x in re.findall(r'\d+', price_ranges_str)
                ]
                price_values = [
                    float(x.strip()) for x in re.findall(r'\d+\.?\d*', price_values_str)
                ]
                
                if len(price_ranges) == len(price_values) and price_ranges:
                    # Sort theo start_quantity (học từ pattern Vipo)
                    sorted_pairs = sorted(zip(price_ranges, price_values))
                    
                    for i, (start_qty, price) in enumerate(sorted_pairs):
                        # Tính endAmount từ start_quantity của item tiếp theo (học từ pattern Vipo)
                        if i + 1 < len(sorted_pairs):
                            next_start = sorted_pairs[i + 1][0]
                            end = next_start - 1
                        else:
                            end = 999999
                        
                        entry = {
                            "beginAmount": start_qty,
                            "endAmount": end,
                            "price": price,
                            "discountPrice": price,
                        }
                        if exchange_rate:
                            entry["price_vnd"] = round(price * exchange_rate, 2)
                        ranges.append(entry)
                    
                    if ranges:
                        return ranges
            except Exception as e:
                logger.warning(f"Failed to parse JavaScript price ranges: {e}")
        
        # Method 2: Extract từ HTML table (wholesale-prices)
        wholesale_table = soup.select_one("table.wholesale-prices")
        if wholesale_table:
            try:
                # Tìm row có quantity conditions
                quantity_row = wholesale_table.select_one("tr:has(td.quantity-1688)")
                price_row = wholesale_table.select_one("tr:has(td.price-1688)")
                
                if quantity_row and price_row:
                    quantity_cells = quantity_row.select("td.quantity-1688 span")
                    price_cells = price_row.select("td.price-1688")
                    
                    if len(quantity_cells) == len(price_cells):
                        for qty_cell, price_cell in zip(quantity_cells, price_cells):
                            qty_text = qty_cell.get_text(strip=True)
                            # Parse: "1 - 199", "200 - 999", "≥ 1000"
                            qty_match = re.search(r'(\d+)\s*-\s*(\d+)', qty_text)
                            if qty_match:
                                begin = int(qty_match.group(1))
                                end = int(qty_match.group(2))
                            elif qty_text.startswith("≥") or qty_text.startswith(">="):
                                begin_match = re.search(r'(\d+)', qty_text)
                                if begin_match:
                                    begin = int(begin_match.group(1))
                                    end = 999999
                                else:
                                    continue
                            else:
                                continue
                            
                            # Extract price từ price_cell (có thể có VND và CNY)
                            price_text = price_cell.get_text(strip=True)
                            # Tìm CNY price: ¥41.00
                            cny_match = re.search(r'¥\s*([\d.]+)', price_text)
                            if cny_match:
                                price = float(cny_match.group(1))
                            else:
                                # Fallback: tìm số đầu tiên
                                num_match = re.search(r'([\d.]+)', price_text)
                                if num_match:
                                    price = float(num_match.group(1))
                                else:
                                    continue
                            
                            entry = {
                                "beginAmount": begin,
                                "endAmount": end,
                                "price": price,
                                "discountPrice": price,
                            }
                            if exchange_rate:
                                entry["price_vnd"] = round(price * exchange_rate, 2)
                            ranges.append(entry)
                        
                        if ranges:
                            ranges.sort(key=lambda x: x.get("beginAmount", 0))
                            return ranges
            except Exception as e:
                logger.warning(f"Failed to parse HTML table price ranges: {e}")
        
        # Method 3: Extract từ cart_price_table string
        cart_price_table_pattern = re.compile(
            r"cart_price_table\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE
        )
        cart_match = cart_price_table_pattern.search(html)
        if cart_match:
            try:
                cart_table_str = cart_match.group(1)
                # Format: '1-199:41.0;200-999:40.0;>=1000:39.0'
                for part in cart_table_str.split(";"):
                    if ":" in part:
                        qty_part, price_part = part.split(":", 1)
                        price = float(price_part.strip())
                        
                        # Parse quantity: "1-199", ">=1000"
                        if "-" in qty_part:
                            begin_str, end_str = qty_part.split("-", 1)
                            begin = int(begin_str.strip())
                            end = int(end_str.strip())
                        elif qty_part.strip().startswith(">="):
                            begin = int(qty_part.replace(">=", "").strip())
                            end = 999999
                        else:
                            continue
                        
                        entry = {
                            "beginAmount": begin,
                            "endAmount": end,
                            "price": price,
                            "discountPrice": price,
                        }
                        if exchange_rate:
                            entry["price_vnd"] = round(price * exchange_rate, 2)
                        ranges.append(entry)
                
                if ranges:
                    ranges.sort(key=lambda x: x.get("beginAmount", 0))
                    return ranges
            except Exception as e:
                logger.warning(f"Failed to parse cart_price_table: {e}")
        
        return []

    def _build_range_prices_from_skus(
        self, sku_list: List[Dict[str, Any]], exchange_rate: Optional[float]
    ) -> List[Dict[str, Any]]:
        """
        Build range prices từ SKU list (fallback khi không có từ HTML).
        Lưu ý: Nhaphangchina không có quantity threshold info từ SKU list,
        nên beginAmount=1, endAmount=999999 cho tất cả (giống Pugo fallback).
        """
        if not sku_list:
            return []

        unique_prices = sorted(
            {
                self._normalize_float(sku["price"])
                for sku in sku_list
                if sku.get("price")
            }
        )
        if not unique_prices:
            return []

        ranges = []
        for price in unique_prices:
            # Nhaphangchina không có quantity threshold info từ SKU list
            # Nên dùng pattern Pugo: beginAmount=1, endAmount=999999 (giống Pugo fallback)
            entry = {
                "beginAmount": 1,
                "endAmount": 999999,
                "price": price,
                "discountPrice": price,
            }
            if exchange_rate:
                entry["price_vnd"] = round(price * exchange_rate, 2)
            ranges.append(entry)
        return ranges

    def _detect_platform(self, url: str) -> str:
        """
        Detect platform từ URL (ưu tiên URL sản phẩm thực tế).
        Kiểm tra specific patterns trước general patterns.
        """
        if not url:
            return "nhaphangchina"
        
        url_lower = url.lower()
        
        # ƯU TIÊN: Kiểm tra domain trước (chính xác nhất)
        # Mapping các domain patterns - sắp xếp theo độ ưu tiên (specific trước general)
        source_patterns = [
            # Tmall patterns (kiểm tra trước Taobao vì có thể có item.taobao.com nhưng là Tmall)
            ('tmall', [
                r'detail\.tmall\.com',  # Ưu tiên: pattern cụ thể
                r'item\.tmall\.com',
                r'm\.tmall\.com',
                r'h5\.tmall\.com',
            ]),
            # 1688 patterns
            ('1688', [
                r'detail\.1688\.com',
                r'offer\.1688\.com',
            ]),
            # Taobao patterns
            ('taobao', [
                r'item\.taobao\.com',
            ]),
        ]
        
        for source, patterns in source_patterns:
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return source
        
        # Fallback: Kiểm tra spm parameter (chỉ khi domain không rõ ràng)
        # Nếu URL là item.taobao.com nhưng có spm=a21bo.tmall → có thể là Tmall
        # Nhưng ưu tiên domain trước, chỉ dùng parameter khi không match domain nào
        if 'spm=a21bo.tmall' in url_lower:
            return "tmall"
        
        # Fallback: General patterns (khi không match specific patterns)
        if "tmall" in url_lower:
            return "tmall"
        if "taobao" in url_lower:
            return "taobao"
        if "1688" in url_lower:
            return "1688"
        
        return "nhaphangchina"

    def _extract_source_id_from_source_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        match = re.search(r"id=(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/offer/(\d+)\.html", url)
        if match:
            return match.group(1)
        return None


parser_nhaphangchina = ParserNhaphangchina()


