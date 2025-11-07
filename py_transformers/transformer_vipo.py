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
        """Trích xuất danh sách hình ảnh (học hỏi pattern từ Pugo với fallback paths)"""
        images = []
        
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        image_paths = [
            'main_img_url_list',  # Ưu tiên: Vipo API structure
            'data.main_img_url_list',
            'product.main_img_url_list',
            'images',  # Fallback: generic paths
            'data.images',
            'product.images',
            'item.images',
            'img_list',
            'data.img_list',
            'product.img_list'
        ]
        
        # Thử từng path theo thứ tự ưu tiên
        for path in image_paths:
            images_data = self.get_nested(data, path, [])
            if isinstance(images_data, list) and images_data:
                for img in images_data:
                    if isinstance(img, dict):
                        # Thử các key khác nhau cho URL ảnh (như Pugo)
                        for key in ['url', 'imageUrl', 'src', 'image', 'original', 'img_url']:
                            if key in img and isinstance(img[key], str) and img[key].strip():
                                images.append(img[key].strip())
                                break
                    elif isinstance(img, str) and img.strip():
                        images.append(img.strip())
                if images:
                    break
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        if not images:
            main_images = data.get('main_img_url_list', [])
            if isinstance(main_images, list):
                for img in main_images:
                    if isinstance(img, str) and img.strip():
                        images.append(img.strip())
        
        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất SKU properties (ưu tiên tiếng Trung - original, học hỏi pattern từ Pugo)"""
        out: List[Dict[str, Any]] = []
        
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        prop_paths = [
            'product_prop_list',  # Ưu tiên: Vipo API structure
            'data.product_prop_list',
            'product.product_prop_list',
            'properties',  # Fallback: generic paths
            'data.properties',
            'product.properties',
            'item.properties',
            'skuProperties',  # Fallback: Pugo-like paths
            'data.skuProperties',
            'product.skuProperties'
        ]
        
        product_prop_list = None
        for path in prop_paths:
            prop_data = self.get_nested(data, path, [])
            if isinstance(prop_data, list) and prop_data:
                product_prop_list = prop_data
                break
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        if product_prop_list is None:
            product_prop_list = data.get('product_prop_list', [])
        
        if not isinstance(product_prop_list, list):
            return out
        
        for prop in product_prop_list:
            if not isinstance(prop, dict):
                continue
            
            # ✅ Ưu tiên original_prop_name (tiếng Trung) như Vipo hiện tại
            # ✅ Nhưng có fallback như Pugo
            prop_name = (
                prop.get('original_prop_name') or 
                prop.get('prop_name') or 
                prop.get('name') or 
                prop.get('propertyName') or 
                prop.get('prop') or 
                ''
            )
            if not prop_name:
                continue
            
            # Lấy value_list với fallback paths
            values: List[Dict[str, Any]] = []
            value_list = (
                prop.get('value_list') or 
                prop.get('values') or 
                prop.get('value') or 
                []
            )
            
            if isinstance(value_list, list):
                for value in value_list:
                    if isinstance(value, dict):
                        # ✅ Ưu tiên original_value_name (tiếng Trung) như Vipo hiện tại
                        # ✅ Nhưng có fallback như Pugo
                        value_name = (
                            value.get('original_value_name') or 
                            value.get('value_name') or 
                            value.get('name') or 
                            value.get('valueName') or 
                            value.get('value') or 
                            ''
                        )
                        if not value_name:
                            continue
                        
                        item = {'name': value_name}
                        
                        # ✅ Lấy image với nhiều key options (như Pugo)
                        for img_key in ['img_url', 'image', 'imageUrl', 'img', 'src']:
                            if value.get(img_key):
                                item['image'] = value[img_key]
                                break
                        
                        values.append(item)
                    elif isinstance(value, str):
                        # ✅ Hỗ trợ string values (như Pugo)
                        values.append({'name': value})
            
            if values:
                out.append({'name': prop_name, 'values': values})
        
        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        """Trích xuất danh sách SKU (ưu tiên tiếng Trung - original, học hỏi pattern từ Pugo)"""
        sku_list = []
        
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        sku_paths = [
            'product_sku_info_list',  # Ưu tiên: Vipo API structure
            'data.product_sku_info_list',
            'product.product_sku_info_list',
            'skuList',  # Fallback: Pugo-like paths
            'data.skuList',
            'product.skuList',
            'item.skuList',
            'skus',  # Fallback: generic paths
            'data.skus',
            'product.skus'
        ]
        
        product_sku_info_list = None
        for path in sku_paths:
            sku_data = self.get_nested(data, path, [])
            if isinstance(sku_data, list) and sku_data:
                product_sku_info_list = sku_data
                break
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        if product_sku_info_list is None:
            product_sku_info_list = data.get('product_sku_info_list', [])
        
        if not isinstance(product_sku_info_list, list):
            return sku_list
        
        for sku_item in product_sku_info_list:
            if not isinstance(sku_item, dict):
                continue
            
            # ✅ Ghép tất cả original_value_name từ sku_prop_list bằng | (giữ logic Vipo)
            spec_attrs_parts = []
            sku_prop_list = sku_item.get('sku_prop_list', [])
            
            if isinstance(sku_prop_list, list):
                for prop in sku_prop_list:
                    if isinstance(prop, dict):
                        # ✅ Ưu tiên original_value_name (tiếng Trung) như Vipo hiện tại
                        # ✅ Nhưng có fallback như Pugo
                        original_value_name = (
                            prop.get('original_value_name') or 
                            prop.get('value_name') or 
                            prop.get('name') or 
                            prop.get('value') or 
                            ''
                        )
                        if original_value_name:
                            spec_attrs_parts.append(original_value_name)
            
            # ✅ Ghép bằng | và normalize (như Pugo)
            spec_attrs = '|'.join(spec_attrs_parts) if spec_attrs_parts else ''
            # Đồng bộ hoá định dạng specAttrs (thay &gt; thành | nếu có)
            spec_attrs = spec_attrs.replace('&gt;', '|')
            
            # ✅ Lấy price và stock với fallback options (như Pugo)
            price = (
                sku_item.get('price') or 
                sku_item.get('salePrice') or 
                sku_item.get('unitPrice') or 
                0
            )
            stock = (
                sku_item.get('stock') or 
                sku_item.get('canBookCount') or 
                sku_item.get('quantity') or 
                0
            )
            
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
        """Trích xuất giá cao nhất (học hỏi pattern từ Pugo với fallback paths)"""
        # ✅ Thử lấy từ range prices trước (như Pugo)
        range_prices = self.extract_range_prices(data)
        if range_prices:
            return str(max([p['price'] for p in range_prices]))
        
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        # Ưu tiên sku_price_ranges.max_price (Vipo structure) trước
        sku_price_ranges = data.get('sku_price_ranges') or self.get_nested(data, 'sku_price_ranges', {})
        if isinstance(sku_price_ranges, dict):
            max_price = sku_price_ranges.get('max_price')
            if max_price is not None and float(max_price) > 0:
                return str(max_price)
        
        # ✅ Fallback: Thử các paths khác như Pugo
        price_paths = [
            'data.maxPrice',
            'data.product.maxPrice',
            'data.item.maxPrice',
            'maxPrice',
            'product.maxPrice',
            'item.maxPrice',
            'data.startPrice',  # Ưu tiên startPrice (giá cơ bản) trước
            'data.price',
            'data.product.price',
            'data.item.price',
            'data.sellPrice',  # sellPrice (giá cao nhất) cuối cùng
            'sellPrice',
            'price',
            'startPrice'
        ]
        
        for path in price_paths:
            price = self.get_nested(data, path)
            if price is not None and str(price) != '0' and float(price) > 0:
                return str(price)
        
        # ✅ Fallback: Tìm max từ SKU prices (giữ logic Vipo)
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
        """Trích xuất tên sản phẩm (ưu tiên tiếng Trung - original, học hỏi pattern từ Pugo)"""
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        # ✅ Nhưng vẫn ưu tiên original_product_name (tiếng Trung) như Vipo hiện tại
        name_paths = [
            'original_product_name',  # Ưu tiên: Vipo API structure (tiếng Trung)
            'data.original_product_name',
            'product.original_product_name',
            'product_name',  # Fallback: product_name (đã dịch)
            'data.product_name',
            'product.product_name',
            'name',  # Fallback: generic paths
            'data.name',
            'product.name',
            'item.name',
            'title',  # Fallback: title paths
            'data.title',
            'product.title',
            'item.title',
            'data.product.title',
            'data.item.title'
        ]
        
        for path in name_paths:
            name = self.get_nested(data, path)
            if name and isinstance(name, str) and name.strip():
                return name.strip()
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        original_name = data.get('original_product_name')
        if original_name and isinstance(original_name, str) and original_name.strip():
            return original_name.strip()
        
        product_name = data.get('product_name')
        if product_name and isinstance(product_name, str) and product_name.strip():
            return product_name.strip()
        
        return ''

    def extract_source_id(self, data: Dict) -> str:
        """Trích xuất source ID (học hỏi pattern từ Pugo với fallback paths)"""
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        # Ưu tiên product_id (Vipo structure) trước, sau đó fallback như Pugo
        id_paths = [
            'product_id',  # Ưu tiên: Vipo API structure
            'data.product_id',
            'product.product_id',
            'data.sourceId',  # Fallback: generic paths
            'data.product.sourceId',
            'data.item.sourceId',
            'data.productId',  # Fallback: productId paths
            'data.product.productId',
            'data.item.productId',
            'sourceId',
            'product.sourceId',
            'item.sourceId',
            'productId',
            'product.productId',
            'item.productId',
            'data.id',  # Fallback: generic id
            'data.product.id',
            'data.item.id',
            'id',
            'product.id',
            'item.id'
        ]
        
        for path in id_paths:
            source_id = self.get_nested(data, path)
            if source_id is not None and str(source_id) != '0' and str(source_id).strip():  # Bỏ qua giá trị 0 và empty
                return str(source_id).strip()
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        product_id = data.get('product_id')
        if product_id is not None and str(product_id) != '0' and str(product_id).strip():
            return str(product_id).strip()
        
        return ''

    def extract_url(self, data: Dict) -> str:
        """Trích xuất URL (học hỏi pattern từ Pugo với fallback paths)"""
        # ✅ HỌC HỎI TỪ PUGO: Thử nhiều paths với get_nested() để robust hơn
        url_paths = [
            'original_product_url',  # Ưu tiên: Vipo API structure
            'data.original_product_url',
            'product.original_product_url',
            'url',  # Fallback: generic paths
            'data.url',
            'product.url',
            'item.url',
            'itemUrl',  # Fallback: Pugo-like paths
            'data.itemUrl',
            'product.itemUrl'
        ]
        
        for path in url_paths:
            url = self.get_nested(data, path)
            if url and isinstance(url, str) and url.strip():
                return url.strip()
        
        # ✅ FALLBACK: Thử direct get() nếu get_nested() không tìm thấy (backward compatibility)
        original_url = data.get('original_product_url')
        if original_url and isinstance(original_url, str) and original_url.strip():
            return original_url.strip()
        
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
            # Log error để debug
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Transformer Vipo: raw data không có hoặc thiếu 'raw_data' key")
            logger.error(f"Raw keys: {list(raw.keys()) if isinstance(raw, dict) else 'not a dict'}")
            return {}

        api_result = raw['raw_data']
        
        # Kiểm tra API result có data không
        if not isinstance(api_result, dict):
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Transformer Vipo: api_result không phải dict: {type(api_result)}")
            return {}
        
        # Handle multiple cases:
        # Case 1: api_result = {"status": "success", "data": {...}} (từ _call_vipo_api)
        # Case 2: api_result = {"data": {...}} (không có status key)
        # Case 3: api_result = {"status": "success", "raw_data": {"data": {...}}} (nested - từ extractor response)
        # Case 4: api_result chính là data dict
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Transformer Vipo: api_result keys: {list(api_result.keys()) if isinstance(api_result, dict) else 'not a dict'}")
        
        # Case 3: Nested structure - extract_result có raw_data bên trong (từ extractor response)
        if 'raw_data' in api_result and isinstance(api_result.get('raw_data'), dict):
            logger.info("Transformer Vipo: Detected nested raw_data structure (Case 3)")
            nested_raw_data = api_result['raw_data']
            if 'data' in nested_raw_data:
                data = nested_raw_data.get('data', {})
                logger.info(f"Transformer Vipo: Found data in nested_raw_data, data keys count: {len(list(data.keys())) if isinstance(data, dict) else 0}")
            elif 'status' in nested_raw_data and nested_raw_data.get('status') == 'success':
                data = nested_raw_data.get('data', {})
                logger.info(f"Transformer Vipo: Found data via status check in nested_raw_data")
            else:
                data = nested_raw_data
                logger.info(f"Transformer Vipo: Using nested_raw_data as data")
        elif 'status' in api_result:
            # Case 1: Có status key
            logger.info("Transformer Vipo: Detected status key (Case 1)")
            if api_result.get('status') != 'success':
                logger.error(f"Transformer Vipo: API status không phải 'success': {api_result.get('status')}")
                logger.error(f"API result: {api_result}")
                return {}
            data = api_result.get('data', {})
            logger.info(f"Transformer Vipo: Found data via status, data keys count: {len(list(data.keys())) if isinstance(data, dict) else 0}")
        elif 'data' in api_result:
            # Case 2: Không có status key, có data key
            logger.info("Transformer Vipo: Detected data key without status (Case 2)")
            data = api_result.get('data', {})
            logger.info(f"Transformer Vipo: Found data directly, data keys count: {len(list(data.keys())) if isinstance(data, dict) else 0}")
        else:
            # Case 4: api_result chính là data dict (fallback)
            logger.info("Transformer Vipo: Using api_result as data (Case 4)")
            data = api_result
        
        if not isinstance(data, dict):
            logger.error(f"Transformer Vipo: data không phải dict: {type(data)}")
            return {}
        
        # Log data để debug
        logger.info(f"Transformer Vipo: Final data dict, keys count: {len(list(data.keys())) if isinstance(data, dict) else 0}")
        logger.info(f"Transformer Vipo: data has original_product_name: {'original_product_name' in data if isinstance(data, dict) else False}")
        if isinstance(data, dict) and 'original_product_name' in data:
            logger.info(f"Transformer Vipo: original_product_name length: {len(data['original_product_name']) if data.get('original_product_name') else 0}")
        
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

