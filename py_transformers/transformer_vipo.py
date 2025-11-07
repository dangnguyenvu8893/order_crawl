from typing import Any, Dict, List
import re


class TransformerVipo:
    """Chuẩn hoá dữ liệu từ vipomall.vn API response."""

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

    def detect_source_type(self, platform_type: int, url: str = '') -> str:
        """Xác định source type thực tế từ platform_type hoặc URL"""
        # Mapping platform_type
        platform_type_map = {
            21: 'taobao',
            22: 'tmall',
            23: '1688'
        }
        
        if platform_type in platform_type_map:
            return platform_type_map[platform_type]
        
        # Fallback: detect từ URL
        if not url:
            return 'taobao'  # Default
        
        url_lower = url.lower()
        
        # Kiểm tra Tmall trước
        if 'spm=a21bo.tmall' in url_lower or 'tmall' in url_lower:
            return 'tmall'
        
        # Mapping các domain patterns
        source_patterns = [
            ('1688', [
                r'detail\.1688\.com',
                r'offer\.1688\.com',
                r'1688\.com'
            ]),
            ('taobao', [
                r'item\.taobao\.com',
                r'taobao\.com'
            ]),
            ('pinduoduo', [
                r'yangkeduo\.com',
                r'pinduoduo\.com',
                r'pdd\.cn'
            ])
        ]
        
        for source, patterns in source_patterns:
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return source
        
        return 'taobao'  # Default

    def extract_images(self, data: Dict) -> List[str]:
        """Trích xuất danh sách hình ảnh"""
        images = []
        
        # Lấy từ main_img_url_list
        main_images = data.get('main_img_url_list', [])
        if isinstance(main_images, list):
            for img in main_images:
                if isinstance(img, str) and img.strip():
                    images.append(img)
        
        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất SKU properties (ưu tiên tiếng Trung - original)"""
        out: List[Dict[str, Any]] = []
        
        product_prop_list = data.get('product_prop_list', [])
        if not isinstance(product_prop_list, list):
            return out
        
        for prop in product_prop_list:
            if not isinstance(prop, dict):
                continue
            
            # Lấy original_prop_name (tiếng Trung)
            prop_name = prop.get('original_prop_name') or prop.get('prop_name') or ''
            if not prop_name:
                continue
            
            # Lấy value_list
            values: List[Dict[str, Any]] = []
            value_list = prop.get('value_list', [])
            
            if isinstance(value_list, list):
                for value in value_list:
                    if not isinstance(value, dict):
                        continue
                    
                    # Lấy original_value_name (tiếng Trung)
                    value_name = value.get('original_value_name') or value.get('value_name') or ''
                    if not value_name:
                        continue
                    
                    item = {'name': value_name}
                    
                    # Lấy img_url nếu có
                    img_url = value.get('img_url')
                    if img_url:
                        item['image'] = img_url
                    
                    values.append(item)
            
            if values:
                out.append({'name': prop_name, 'values': values})
        
        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        """Trích xuất danh sách SKU (ưu tiên tiếng Trung - original)"""
        sku_list = []
        
        product_sku_info_list = data.get('product_sku_info_list', [])
        if not isinstance(product_sku_info_list, list):
            return sku_list
        
        for sku_item in product_sku_info_list:
            if not isinstance(sku_item, dict):
                continue
            
            # Ghép tất cả original_value_name từ sku_prop_list bằng |
            spec_attrs_parts = []
            sku_prop_list = sku_item.get('sku_prop_list', [])
            
            if isinstance(sku_prop_list, list):
                for prop in sku_prop_list:
                    if isinstance(prop, dict):
                        # Lấy original_value_name (tiếng Trung)
                        original_value_name = prop.get('original_value_name') or prop.get('value_name') or ''
                        if original_value_name:
                            spec_attrs_parts.append(original_value_name)
            
            # Ghép bằng |
            spec_attrs = '|'.join(spec_attrs_parts) if spec_attrs_parts else ''
            
            # Lấy price và stock
            price = sku_item.get('price', 0)
            stock = sku_item.get('stock', 0)
            
            sku_list.append({
                'canBookCount': str(stock),
                'price': str(price),
                'specAttrs': spec_attrs
            })
        
        return sku_list

    def extract_range_prices(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất bảng giá theo số lượng"""
        out = []
        
        # Ưu tiên: data.price_ranges (global)
        price_ranges = data.get('price_ranges', [])
        if isinstance(price_ranges, list) and price_ranges:
            for p in price_ranges:
                if isinstance(p, dict):
                    begin = int(p.get('beginAmount') or p.get('start_quantity') or 1)
                    price = float(p.get('price') or 0)
                    end = int(p.get('endAmount') or p.get('maxQuantity') or 999999)
                    
                    out.append({
                        'beginAmount': begin,
                        'price': price,
                        'endAmount': end,
                        'discountPrice': float(p.get('discountPrice') or price)
                    })
        
        # Fallback: Extract từ SKU price_ranges
        if not out:
            product_sku_info_list = data.get('product_sku_info_list', [])
            if isinstance(product_sku_info_list, list):
                # Collect unique price ranges từ tất cả SKUs
                seen_ranges = set()
                
                for sku_item in product_sku_info_list:
                    if not isinstance(sku_item, dict):
                        continue
                    
                    sku_price_ranges = sku_item.get('price_ranges', [])
                    if isinstance(sku_price_ranges, list):
                        for p in sku_price_ranges:
                            if not isinstance(p, dict):
                                continue
                            
                            start_qty = int(p.get('start_quantity') or 1)
                            price = float(p.get('price') or 0)
                            
                            # Tạo key để check duplicate
                            range_key = (start_qty, price)
                            if range_key not in seen_ranges:
                                seen_ranges.add(range_key)
                                out.append({
                                    'beginAmount': start_qty,
                                    'price': price,
                                    'endAmount': 999999,  # Default
                                    'discountPrice': price
                                })
        
        # Nếu vẫn không có, tạo từ sku_price_ranges (min/max)
        if not out:
            sku_price_ranges = data.get('sku_price_ranges', {})
            if isinstance(sku_price_ranges, dict):
                min_price = float(sku_price_ranges.get('min_price') or 0)
                if min_price > 0:
                    out.append({
                        'beginAmount': 1,
                        'price': min_price,
                        'endAmount': 999999,
                        'discountPrice': min_price
                    })
        
        return out

    def extract_max_price(self, data: Dict) -> str:
        """Trích xuất giá cao nhất"""
        # Ưu tiên: sku_price_ranges.max_price
        sku_price_ranges = data.get('sku_price_ranges', {})
        if isinstance(sku_price_ranges, dict):
            max_price = sku_price_ranges.get('max_price')
            if max_price is not None and float(max_price) > 0:
                return str(max_price)
        
        # Fallback: Tìm max từ range prices
        range_prices = self.extract_range_prices(data)
        if range_prices:
            return str(max([p['price'] for p in range_prices]))
        
        # Fallback: Tìm max từ SKU prices
        product_sku_info_list = data.get('product_sku_info_list', [])
        if isinstance(product_sku_info_list, list):
            prices = []
            for sku_item in product_sku_info_list:
                if isinstance(sku_item, dict):
                    price = sku_item.get('price')
                    if price is not None and float(price) > 0:
                        prices.append(float(price))
            if prices:
                return str(max(prices))
        
        return '0.00'

    def extract_name(self, data: Dict) -> str:
        """Trích xuất tên sản phẩm (ưu tiên tiếng Trung - original)"""
        # Ưu tiên: original_product_name (tiếng Trung)
        original_name = data.get('original_product_name')
        if original_name and isinstance(original_name, str) and original_name.strip():
            return original_name.strip()
        
        # Fallback: product_name (đã dịch)
        product_name = data.get('product_name')
        if product_name and isinstance(product_name, str) and product_name.strip():
            return product_name.strip()
        
        return ''

    def extract_source_id(self, data: Dict) -> str:
        """Trích xuất source ID"""
        product_id = data.get('product_id')
        if product_id is not None:
            return str(product_id)
        return ''

    def extract_url(self, data: Dict) -> str:
        """Trích xuất URL"""
        original_url = data.get('original_product_url')
        if original_url and isinstance(original_url, str):
            return original_url
        return ''

    def extract_platform_type(self, data: Dict) -> int:
        """Trích xuất platform_type"""
        platform_type = data.get('platform_type')
        if platform_type is not None:
            return int(platform_type)
        return 21  # Default: taobao

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform dữ liệu raw từ vipomall.vn extractor thành format chuẩn
        """
        if not raw or 'raw_data' not in raw:
            return {}

        api_result = raw['raw_data']
        
        # Kiểm tra API result có data không
        if not isinstance(api_result, dict) or api_result.get('status') != 'success':
            return {}
        
        data = api_result.get('data', {})
        if not isinstance(data, dict):
            return {}
        
        # Trích xuất các thông tin
        images = self.extract_images(data)
        skuProperty = self.extract_sku_props(data)
        sku = self.extract_sku_list(data)
        rangePrices = self.extract_range_prices(data)
        maxPrice = self.extract_max_price(data)
        name = self.extract_name(data)
        sourceId = self.extract_source_id(data) or raw.get('sourceId') or ''
        url = self.extract_url(data) or raw.get('url') or ''
        platform_type = self.extract_platform_type(data)
        
        # Xác định source type thực tế
        actual_source_type = self.detect_source_type(platform_type, url)

        # Trả về cấu trúc giống transformer_1688.py và transformer_pugo.py
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
transformer_vipo = TransformerVipo()

