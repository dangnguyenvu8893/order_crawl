from typing import Any, Dict, List
import re


class TransformerPandamall:
    """Chuẩn hoá dữ liệu từ Pandamall /item/details API response."""

    def get_nested(self, obj: Dict, path: str, default=None):
        """Lấy giá trị từ object theo đường dẫn nested"""
        try:
            cur = obj
            for k in path.split('.'):
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    return default
            return cur
        except Exception:
            return default

    def detect_source_type(self, url: str, provider: str = '') -> str:
        """Xác định source type thực tế từ URL hoặc provider field"""
        # Provider field từ extractor là đáng tin nhất
        if provider in ('taobao', '1688', 'tmall'):
            return provider

        if not url:
            return 'taobao'

        url_lower = url.lower()

        if 'tmall' in url_lower or 'spm=a21bo.tmall' in url_lower:
            return 'tmall'

        source_patterns = [
            ('1688', [r'detail\.1688\.com', r'offer\.1688\.com', r'1688\.com']),
            ('taobao', [r'item\.taobao\.com', r'taobao\.com']),
        ]

        for source, patterns in source_patterns:
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return source

        return 'taobao'

    def _get_classify(self, data: Dict) -> Dict:
        """Lấy classify block từ response — nơi chứa SKU data thực tế"""
        # Thử các vị trí khác nhau của classify
        for path in ['classify', 'data.classify', 'item.classify']:
            classify = self.get_nested(data, path)
            if isinstance(classify, dict) and classify:
                return classify
        return {}

    def extract_images(self, data: Dict) -> List[str]:
        """Trích xuất danh sách hình ảnh"""
        images = []

        # Pandamall trả về thumbnails[].src — ưu tiên cao nhất
        thumbnails = data.get('thumbnails', [])
        if isinstance(thumbnails, list) and thumbnails:
            for t in thumbnails:
                if isinstance(t, dict):
                    src = t.get('src', '')
                    if src and isinstance(src, str):
                        images.append(src)
                elif isinstance(t, str) and t:
                    images.append(t)

        # Fallback: các paths array phổ biến (images[], imageList[], ...)
        if not images:
            image_paths = [
                'images', 'imageList', 'gallery', 'photos', 'imgs',
                'data.images', 'item.images', 'product.images'
            ]
            for path in image_paths:
                images_data = self.get_nested(data, path, [])
                if isinstance(images_data, list) and images_data:
                    for img in images_data:
                        if isinstance(img, dict):
                            for key in ['url', 'imageUrl', 'src', 'image']:
                                if key in img and isinstance(img[key], str):
                                    images.append(img[key])
                                    break
                        elif isinstance(img, str):
                            images.append(img)
                    if images:
                        break

        # Fallback: single image field (như Pugo pattern)
        if not images:
            main_img = data.get('image') or self.get_nested(data, 'data.image')
            if main_img and isinstance(main_img, str):
                images.append(main_img)

        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        """
        Trích xuất SKU properties từ classify.skuProperties
        Format Pandamall: [{ propID, propName, propValues: [{valueID, valueName, image}] }]
        """
        out: List[Dict[str, Any]] = []

        classify = self._get_classify(data)
        sku_properties = classify.get('skuProperties') or []

        if isinstance(sku_properties, list) and sku_properties:
            for prop in sku_properties:
                if not isinstance(prop, dict):
                    continue

                name = prop.get('propName') or prop.get('name') or ''
                if not name:
                    continue

                values: List[Dict[str, Any]] = []
                for val in (prop.get('propValues') or prop.get('values') or []):
                    if not isinstance(val, dict):
                        continue
                    item: Dict[str, Any] = {
                        'name': val.get('valueName') or val.get('name') or '',
                        # sourcePropertyId và sourceValueId theo pattern codebase (từ aaba769)
                        'sourcePropertyId': str(prop.get('propID') or prop.get('propId') or ''),
                        'sourceValueId': str(val.get('valueID') or val.get('valueId') or '')
                    }
                    # Thêm image nếu có
                    img = val.get('image') or val.get('imageUrl') or val.get('img') or ''
                    if img:
                        item['image'] = img
                    if item['name']:
                        values.append(item)

                if values:
                    out.append({'name': name, 'values': values})

        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        """
        Trích xuất danh sách SKU từ classify.skuMappings
        Format Pandamall: dict với key "propID:valueID@propID:valueID" → {skuID, price, promotionPrice, stock}
        """
        sku_list = []

        classify = self._get_classify(data)
        sku_mappings = classify.get('skuMappings') or {}

        if not isinstance(sku_mappings, dict) or not sku_mappings:
            return sku_list

        # Build lookup: propID:valueID → valueName (để tạo specAttrs dạng tên)
        value_name_map: Dict[str, str] = {}
        sku_properties = classify.get('skuProperties') or []
        if isinstance(sku_properties, list):
            for prop in sku_properties:
                if not isinstance(prop, dict):
                    continue
                for val in (prop.get('propValues') or prop.get('values') or []):
                    if isinstance(val, dict):
                        prop_id = str(prop.get('propID') or prop.get('propId') or '')
                        val_id = str(val.get('valueID') or val.get('valueId') or '')
                        val_name = val.get('valueName') or val.get('name') or ''
                        if prop_id and val_id and val_name:
                            value_name_map[f"{prop_id}:{val_id}"] = val_name

        # Parse từng entry trong skuMappings dict
        # Key format: "propID:valueID@propID:valueID"
        for mapping_key, sku_val in sku_mappings.items():
            if not isinstance(sku_val, dict):
                continue

            # Parse mapping key → specAttrs (dùng tên hiển thị nếu có)
            spec_parts = []
            for segment in mapping_key.split('@'):
                segment = segment.strip()
                # Tìm tên hiển thị trong value_name_map
                display_name = value_name_map.get(segment, segment)
                spec_parts.append(display_name)

            spec_attrs = '|'.join([p for p in spec_parts if p])

            # Giá: ưu tiên promotionPrice nếu có và khác 0
            price_val = sku_val.get('promotionPrice') or sku_val.get('price') or ''
            if price_val == 0 or price_val == '0':
                price_val = sku_val.get('price') or ''

            sku_id = str(sku_val.get('skuID') or sku_val.get('skuId') or '')
            stock = str(sku_val.get('stock') or sku_val.get('quantity') or sku_val.get('canBookCount') or '')

            sku_entry: Dict[str, str] = {
                'canBookCount': stock,
                'price': str(price_val),
                'specAttrs': spec_attrs
            }

            if sku_id:
                sku_entry['skuId'] = sku_id

            sku_list.append(sku_entry)

        return sku_list

    def extract_range_prices(self, data: Dict) -> List[Dict[str, Any]]:
        """
        Pandamall không có rangePrices array như 1688.
        Giá nằm trong từng SKU entry của skuMappings.
        → Tổng hợp min/max price từ tất cả SKU entries để tạo 1 range duy nhất.
        """
        classify = self._get_classify(data)
        sku_mappings = classify.get('skuMappings') or {}

        prices = []
        if isinstance(sku_mappings, dict):
            for sku_val in sku_mappings.values():
                if isinstance(sku_val, dict):
                    price = sku_val.get('promotionPrice') or sku_val.get('price') or 0
                    try:
                        p = float(price)
                        if p > 0:
                            prices.append(p)
                    except (ValueError, TypeError):
                        pass

        if prices:
            return [{
                'beginAmount': 1,
                'price': min(prices),
                'endAmount': 999999,
                'discountPrice': min(prices)
            }]

        # Fallback: tìm giá ở vị trí khác
        for path in ['price', 'minPrice', 'startPrice', 'data.price']:
            val = self.get_nested(data, path)
            if val:
                try:
                    p = float(val)
                    if p > 0:
                        return [{
                            'beginAmount': 1,
                            'price': p,
                            'endAmount': 999999,
                            'discountPrice': p
                        }]
                except (ValueError, TypeError):
                    pass

        return []

    def extract_max_price(self, data: Dict) -> str:
        """Trích xuất giá cao nhất"""
        range_prices = self.extract_range_prices(data)
        if range_prices:
            return str(max([p['price'] for p in range_prices]))

        # Fallback
        for path in ['price', 'maxPrice', 'sellPrice', 'data.price']:
            price = self.get_nested(data, path)
            if price is not None and str(price) != '0':
                return str(price)

        return '0.00'

    def extract_name(self, data: Dict) -> str:
        """Trích xuất tên sản phẩm"""
        name_paths = [
            'title', 'name', 'productName', 'itemName',
            'data.title', 'data.name', 'item.title', 'item.name'
        ]
        for path in name_paths:
            name = self.get_nested(data, path)
            if name and isinstance(name, str):
                return name
        return ''

    def extract_source_id(self, data: Dict) -> str:
        """Trích xuất source ID (item ID của platform gốc)"""
        id_paths = [
            'itemId', 'item_id', 'sourceId', 'id',
            'data.itemId', 'data.item_id', 'data.sourceId', 'data.id',
            'item.itemId', 'item.id'
        ]
        for path in id_paths:
            source_id = self.get_nested(data, path)
            if source_id is not None and str(source_id) not in ('0', ''):
                return str(source_id)
        return ''

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform dữ liệu raw từ extractor_pandamall thành format chuẩn.
        Tương thích với schema mà backend ProductService expects.
        """
        if not raw or 'raw_data' not in raw:
            return {
                'status': 'error',
                'message': raw.get('message', 'Extract failed — no raw_data') if raw else 'Empty response from extractor',
                'sourceType': raw.get('sourceType', 'pandamall') if raw else 'pandamall',
            }

        data = raw['raw_data']

        # Unwrap nested data từ API response
        api_data = data
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict):
            inner = data['data']
            api_data = inner.get('data', inner)

        # Trích xuất các thông tin
        images = self.extract_images(api_data)
        skuProperty = self.extract_sku_props(api_data)
        sku = self.extract_sku_list(api_data)
        rangePrices = self.extract_range_prices(api_data)
        maxPrice = self.extract_max_price(api_data)
        name = self.extract_name(api_data)

        # sourceId: ưu tiên từ extractor (item_id đã parse từ URL), fallback từ response
        sourceId = raw.get('sourceId') or self.extract_source_id(api_data)

        # provider từ extractor để detect source type chính xác
        provider = raw.get('provider', '')
        # Ưu tiên URL sạch từ API response (như Pugo pattern), fallback về input URL
        url = self.get_nested(api_data, 'url') or self.get_nested(api_data, 'itemUrl') or raw.get('url') or ''
        actual_source_type = self.detect_source_type(url, provider)

        # Trả về cấu trúc giống transformer_pugo.py (đúng các key backend đang nhận)
        return {
            'images': images,
            'skuProperty': skuProperty,
            # Alias để tương thích backend ProductService expects `properties`
            'properties': skuProperty,
            'sku': sku,
            'rangePrices': rangePrices,
            'maxPrice': maxPrice,
            'name': name,
            'sourceId': sourceId,
            'sourceType': actual_source_type,
            'url': url,
        }


# Tạo instance global
transformer_pandamall = TransformerPandamall()
