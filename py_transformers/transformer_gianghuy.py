from typing import Any, Dict, List, Optional


class TransformerGianghuy:
    """
    Chuẩn hoá dữ liệu từ Gianghuy / Mona Media API response.
    Hỗ trợ 3 platform: 1688, Taobao, Tmall — cùng qua 2 endpoint:
      /Management1688/get-detail-by-id
      /ManagementTaobao/get-detail-by-id
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: dict từ extractor_gianghuy.extract()
          {
            "status": "success",
            "url": "...",
            "original_url": "...",
            "sourceType": "1688"|"taobao"|"tmall",
            "sourceId": "...",
            "raw_data": { "data": { "data": {...}, "statusCode": 200 } }
          }

        Output: format chuẩn hệ thống
          { name, images, maxPrice, rangePrices, sourceId, sourceType, url,
            skuProperty, properties, sku }
        """
        if raw.get("status") == "error":
            return {"success": False, "error": raw.get("message", "Extractor error")}

        raw_data = raw.get("raw_data", {})
        product  = self._unwrap(raw_data)

        if not product:
            return {"success": False, "error": "Không tìm thấy product data trong response"}

        source_type = raw.get("sourceType", "taobao")
        source_id   = str(product.get("itemId", raw.get("sourceId", "")))
        sku_props   = self._extract_sku_props(product)
        sku_list    = self._extract_sku_list(product)

        # Build canonical URL từ sourceId — tránh URL tracking params dài vượt VARCHAR(255)
        _CANONICAL = {
            "1688":   f"https://detail.1688.com/offer/{source_id}.html",
            "tmall":  f"https://detail.tmall.com/item.htm?id={source_id}",
            "taobao": f"https://item.taobao.com/item.htm?id={source_id}",
        }
        canonical_url = _CANONICAL.get(source_type, raw.get("url", ""))

        return {
            "name":        product.get("title", ""),
            "images":      self._extract_images(product),
            "maxPrice":    self._extract_max_price(product),
            "rangePrices": self._extract_range_prices(product),
            "sourceId":    source_id,
            "sourceType":  source_type,
            "url":         canonical_url,
            "skuProperty": sku_props,
            "properties":  sku_props,   # alias cho backend compatibility
            "sku":         sku_list,
        }

    # ------------------------------------------------------------------
    # Unwrap
    # ------------------------------------------------------------------

    def _unwrap(self, raw_data: Any) -> Optional[Dict]:
        """
        API response structure: { "data": { "data": {...product...}, "statusCode": 200 } }
        raw_data là toàn bộ resp.json() từ extractor.
        """
        if not isinstance(raw_data, dict):
            return None
        outer = raw_data.get("data", raw_data)
        if isinstance(outer, dict) and "data" in outer:
            inner = outer["data"]
            if isinstance(inner, dict) and inner.get("itemId"):
                return inner
            # Có thể nested thêm 1 lớp
            if isinstance(inner, dict) and "data" in inner:
                return inner["data"]
            return inner
        return outer

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def _extract_images(self, product: Dict) -> List[str]:
        medias = product.get("medias") or []
        return [
            m["link"] for m in medias
            if isinstance(m, dict) and m.get("link") and not m.get("isVideo", False)
        ]

    # ------------------------------------------------------------------
    # Max price
    # ------------------------------------------------------------------

    def _extract_max_price(self, product: Dict) -> str:
        # 1688 và Tmall có top-level maxPrice
        top_max = product.get("maxPrice")
        if top_max is not None:
            return str(top_max)

        # Taobao: tính từ skuInfos
        sku_infos = product.get("skuInfos") or []
        prices = [float(s.get("price", 0)) for s in sku_infos if s.get("price")]
        if prices:
            return str(max(prices))
        return "0"

    # ------------------------------------------------------------------
    # Range prices
    # ------------------------------------------------------------------

    def _extract_range_prices(self, product: Dict) -> List[Dict]:
        price_ranges = product.get("priceRanges") or []

        if price_ranges:
            # 1688: [{startQuantity, price}] — sắp xếp tăng dần, tính endAmount
            sorted_ranges = sorted(price_ranges, key=lambda x: int(x.get("startQuantity", 1)))
            result = []
            for i, r in enumerate(sorted_ranges):
                begin = int(r.get("startQuantity", 1))
                price = float(r.get("price", 0))
                if i + 1 < len(sorted_ranges):
                    end = int(sorted_ranges[i + 1].get("startQuantity", begin + 1)) - 1
                else:
                    end = None
                result.append({
                    "beginAmount":   begin,
                    "price":         price,
                    "endAmount":     end,
                    "discountPrice": price,
                })
            return result

        # Taobao / Tmall: không có priceRanges → build từ min SKU price
        sku_infos = product.get("skuInfos") or []
        if not sku_infos:
            return []

        prices = []
        for sku in sku_infos:
            promo = sku.get("promotionPrice")
            raw   = sku.get("price", 0)
            p = float(promo) if (promo is not None and float(promo) > 0) else float(raw)
            if p > 0:
                prices.append(p)

        min_price = min(prices) if prices else 0
        return [{
            "beginAmount":   1,
            "price":         min_price,
            "endAmount":     None,
            "discountPrice": min_price,
        }]

    # ------------------------------------------------------------------
    # SKU Properties
    # ------------------------------------------------------------------

    def _extract_sku_props(self, product: Dict) -> List[Dict]:
        """
        properties[] → skuProperty format chuẩn.
        Dùng name (tiếng Trung) — KHÔNG dùng nameTranslate.
        Backend lo dịch qua translationService.
        """
        props = product.get("properties") or []
        result = []
        for prop in props:
            if not isinstance(prop, dict):
                continue
            values = []
            for v in (prop.get("values") or []):
                if not isinstance(v, dict):
                    continue
                values.append({
                    "name":          v.get("name", ""),
                    "sourceValueId": str(v.get("id", "")),
                    "image":         v.get("imageUrl") or None,
                })
            result.append({
                "name":             prop.get("name", ""),
                "sourcePropertyId": str(prop.get("id", "")),
                "values":           values,
            })
        return result

    # ------------------------------------------------------------------
    # SKU List
    # ------------------------------------------------------------------

    def _extract_sku_list(self, product: Dict) -> List[Dict]:
        """
        skuInfos[] → sku list format chuẩn.

        specAttrs build bằng cách:
          skuPropertyName = "颜色--黑色;尺码--M;"
          → split(";") → filter empty → ["颜色--黑色", "尺码--M"]
          → zip với properties[].name → "颜色--颜色--黑色|尺码--尺码--M"  ← sai

        Đúng hơn: skuPropertyName = "黑色;M;" (CHỈ value names, không kèm prop name)
          → zip với properties[].name → "颜色--黑色|尺码--M"

        Verify từ response thực tế:
          properties[0].name = "灯光颜色"
          skuPropertyName    = "升级加亮款60*5cm-18W;白光6000K;"
          → "灯光颜色--升级加亮款60*5cm-18W|功率--白光6000K"
        """
        sku_infos  = product.get("skuInfos") or []
        prop_names = [p.get("name", "") for p in (product.get("properties") or [])]

        result = []
        for sku in sku_infos:
            if not isinstance(sku, dict):
                continue

            spec_attrs = self._build_spec_attrs(
                sku.get("skuPropertyName", ""),
                prop_names
            )

            # Giá: promotionPrice (nếu > 0) → fallback price
            promo = sku.get("promotionPrice")
            raw_p = sku.get("price", 0)
            if promo is not None and float(promo) > 0:
                price = float(promo)
            else:
                price = float(raw_p) if raw_p else 0

            result.append({
                "specAttrs":    spec_attrs,
                "skuId":        str(sku.get("id", "")),
                "price":        str(price),
                "canBookCount": str(sku.get("amountOnSale", 0)),
            })
        return result

    def _build_spec_attrs(self, sku_property_name: str, prop_names: List[str]) -> str:
        """
        "黑色;M;" + ["颜色分类","尺码"] → "颜色分类--黑色|尺码--M"
        Nếu không có prop_names (edge case) → "黑色|M"
        """
        value_parts = [p for p in sku_property_name.split(";") if p.strip()]

        if prop_names and len(prop_names) == len(value_parts):
            return "|".join(f"{prop}--{val}" for prop, val in zip(prop_names, value_parts))

        # Fallback: chỉ ghép values
        return "|".join(value_parts)


transformer_gianghuy = TransformerGianghuy()
