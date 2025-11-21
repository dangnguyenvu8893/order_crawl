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

            if not product["source_id"]:
                # Từ js array entries
                for entry in js_array.values():
                    if isinstance(entry, list) and len(entry) >= 7:
                        product["source_id"] = str(entry[6])
                        break

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
        result: List[Dict[str, Any]] = []
        property_rows = soup.select(".detail-taobao-tmall .row")

        for row in property_rows:
            label_node = row.select_one(".c-font-bold")
            select_node = row.select_one("[data-property-select]")
            if not select_node or not label_node:
                continue

            name = label_node.get_text(strip=True)
            values: List[Dict[str, Any]] = []

            for prop in select_node.select(".pd-property"):
                value_name = (
                    prop.get("property-name")
                    or prop.get("namechuan")
                    or prop.get("proptitle")
                    or prop.get_text(strip=True)
                )
                entry: Dict[str, Any] = {"name": value_name.strip() if value_name else ""}
                img = prop.select_one("img")
                if img:
                    entry["image"] = (
                        img.get("data-image") or img.get("ng-src") or img.get("src")
                    )
                values.append(entry)

            if name and values:
                result.append({"name": name, "values": values})

        return result

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
                        logger.info(f"Extracted {len(ranges)} price ranges from JavaScript")
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
                            # Sort theo beginAmount (học từ pattern Vipo)
                            ranges.sort(key=lambda x: x.get("beginAmount", 0))
                            logger.info(f"Extracted {len(ranges)} price ranges from HTML table")
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
                    # Sort theo beginAmount (học từ pattern Vipo)
                    ranges.sort(key=lambda x: x.get("beginAmount", 0))
                    logger.info(f"Extracted {len(ranges)} price ranges from cart_price_table")
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
        if not url:
            return "nhaphangchina"
        url_lower = url.lower()
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


