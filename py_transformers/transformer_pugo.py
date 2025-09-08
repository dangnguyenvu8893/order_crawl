from typing import Any, Dict, List
import re


class TransformerPugo:
    """Chuẩn hoá dữ liệu từ pugo.vn API response."""

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

    def detect_source_type(self, url: str) -> str:
        """Xác định source type thực tế từ URL"""
        if not url:
            return 'pugo'
        
        url_lower = url.lower()
        
        # Kiểm tra Tmall trước (dựa trên parameters trong URL)
        # Tmall thường có spm=a21bo.tmall hoặc domain tmall.com
        if 'spm=a21bo.tmall' in url_lower or 'tmall' in url_lower:
            return 'tmall'
        
        # Mapping các domain patterns - sắp xếp theo độ ưu tiên (specific trước general)
        source_patterns = [
            # 1688 patterns
            ('1688', [
                r'detail\.1688\.com',
                r'offer\.1688\.com',
                r'1688\.com'
            ]),
            # Taobao patterns
            ('taobao', [
                r'item\.taobao\.com',
                r'taobao\.com'
            ]),
            # Pinduoduo patterns
            ('pinduoduo', [
                r'yangkeduo\.com',
                r'pinduoduo\.com',
                r'pdd\.cn'
            ])
        ]
        
        # Kiểm tra từng source theo thứ tự ưu tiên
        for source, patterns in source_patterns:
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return source
        
        # Nếu không match pattern nào, trả về pugo
        return 'pugo'

    def extract_images(self, data: Dict) -> List[str]:
        """Trích xuất danh sách hình ảnh"""
        images = []
        
        # Thử các đường dẫn khác nhau cho hình ảnh
        image_paths = [
            'data.images',
            'data.product.images',
            'data.item.images',
            'images',
            'product.images',
            'item.images'
        ]
        
        for path in image_paths:
            images_data = self.get_nested(data, path, [])
            if isinstance(images_data, list) and images_data:
                for img in images_data:
                    if isinstance(img, dict):
                        # Thử các key khác nhau cho URL ảnh
                        for key in ['url', 'imageUrl', 'src', 'image', 'original']:
                            if key in img and isinstance(img[key], str):
                                images.append(img[key])
                                break
                    elif isinstance(img, str):
                        images.append(img)
                if images:
                    break

        # Fallback: imgThumbs và image phổ biến trong pugo
        if not images:
            thumbs = data.get('imgThumbs') or self.get_nested(data, 'data.imgThumbs', [])
            if isinstance(thumbs, list):
                for t in thumbs:
                    if isinstance(t, str):
                        images.append(t)
        if not images:
            main_img = data.get('image') or self.get_nested(data, 'data.image')
            if isinstance(main_img, str):
                images.append(main_img)

        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất SKU properties theo schema của transformer_1688."""
        out: List[Dict[str, Any]] = []

        # 1) Map trực tiếp từ các cấu trúc skuProperties (nếu có)
        sku_paths = [
            'data.skuProperties',
            'data.product.skuProperties',
            'data.item.skuProperties',
            'skuProperties',
            'product.skuProperties',
            'item.skuProperties'
        ]

        for path in sku_paths:
            sku_props = self.get_nested(data, path, [])
            if isinstance(sku_props, list) and sku_props:
                for prop in sku_props:
                    if not isinstance(prop, dict):
                        continue
                    name = prop.get('name') or prop.get('propertyName') or prop.get('prop') or ''
                    if not name:
                        continue
                    values: List[Dict[str, Any]] = []
                    prop_values = prop.get('values') or prop.get('value') or []
                    if isinstance(prop_values, list):
                        for v in prop_values:
                            if isinstance(v, dict):
                                item = {'name': v.get('name') or v.get('valueName') or v.get('value') or ''}
                                # giữ đồng nhất key 'image' như 1688
                                for img_key in ['image', 'imageUrl', 'img']:
                                    if v.get(img_key):
                                        item['image'] = v.get(img_key)
                                        break
                                values.append(item)
                            elif isinstance(v, str):
                                values.append({'name': v})
                    if values:
                        out.append({'name': name, 'values': values})
                if out:
                    break

        # 2) Fallback: dựng properties từ skuMaps (COLOR/SIZE) nếu có
        if not out:
            item_props = self.get_nested(data, 'data.itemPropertys', []) or self.get_nested(data, 'itemPropertys', [])
            if isinstance(item_props, list) and item_props:
                for prop in item_props:
                    if not isinstance(prop, dict):
                        continue
                    # Ưu tiên title trước name để lấy tên thực tế
                    name = prop.get('title') or prop.get('name') or ''
                    p_type = prop.get('type') or ''
                    values: List[Dict[str, Any]] = []
                    for child in prop.get('childPropertys') or []:
                        if isinstance(child, dict):
                            item = {'name': child.get('title') or child.get('properties') or ''}
                            img = child.get('image') or child.get('bigImage')
                            if img:
                                item['image'] = img
                            values.append(item)
                    if name and values:
                        out.append({'name': name, 'values': values})

        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        """Trích xuất danh sách SKU"""
        sku_list = []
        
        # 1) Map từ các cấu trúc skuList (nếu có) sang schema giống transformer_1688
        sku_paths = [
            'data.skuList',
            'data.product.skuList',
            'data.item.skuList',
            'skuList',
            'product.skuList',
            'item.skuList'
        ]

        for path in sku_paths:
            sku_data = self.get_nested(data, path, [])
            if isinstance(sku_data, list) and sku_data:
                for sku in sku_data:
                    if isinstance(sku, dict):
                        spec_attrs = str(
                            sku.get('specAttrs') or sku.get('specAttributes') or sku.get('spec') or ''
                        )
                        # Đồng bộ hoá định dạng specAttrs như 1688 (thay &gt; thành | nếu có)
                        spec_attrs = spec_attrs.replace('&gt;', '|')
                        sku_list.append({
                            'canBookCount': str(sku.get('canBookCount') or sku.get('stock') or sku.get('quantity') or ''),
                            'price': str(sku.get('price') or sku.get('salePrice') or ''),
                            'specAttrs': spec_attrs
                        })
                if sku_list:
                    break

        # 2) Fallback: map từ skuMaps của Pugo (thường có trên kết quả 1688/Taobao)
        if not sku_list:
            sku_maps = self.get_nested(data, 'data.skuMaps', []) or self.get_nested(data, 'skuMaps', [])
            if isinstance(sku_maps, list) and sku_maps:
                # Chuẩn bị map từ prop code -> title để chuyển propPath thành tên hiển thị
                prop_map = {}
                item_props = self.get_nested(data, 'data.itemPropertys', []) or self.get_nested(data, 'itemPropertys', [])
                if isinstance(item_props, list):
                    for prop in item_props:
                        for child in (prop.get('childPropertys') or []):
                            if isinstance(child, dict):
                                code = child.get('properties')
                                title = child.get('title') or child.get('properties') or ''
                                if code and title:
                                    prop_map[str(code)] = str(title)
                for sku in sku_maps:
                    if isinstance(sku, dict):
                        # specAttrs: ưu tiên lấy tên hiển thị
                        spec_display_parts = []
                        sku_map_str = sku.get('skuMap')
                        prop_path = sku.get('propPath')

                        if isinstance(sku_map_str, str) and sku_map_str.strip():
                            # Ví dụ: "购买规格--1件;香味--【首推爆款】温和脱毛膏200ml" => ["1件", "【首推爆款】温和脱毛膏200ml"]
                            for seg in sku_map_str.split(';'):
                                seg = str(seg).strip()
                                if not seg:
                                    continue
                                if '--' in seg:
                                    seg = seg.split('--', 1)[1]
                                spec_display_parts.append(seg)
                        elif isinstance(prop_path, str) and prop_path.strip():
                            # Ví dụ: "-1:-1;-2:-3" -> map qua prop_map
                            for code in prop_path.split(';'):
                                code = str(code).strip()
                                if not code:
                                    continue
                                spec_display_parts.append(prop_map.get(code, code))
                        else:
                            # Fallback cuối: ghép tất cả field có thể thành chuỗi
                            raw = sku.get('propPath') or sku.get('skuMap') or ''
                            if isinstance(raw, list):
                                spec_display_parts = [str(x) for x in raw]
                            else:
                                raw = str(raw)
                                spec_display_parts = [p for p in raw.replace('&gt;', '|').replace(';', '|').split('|') if p]

                        spec = '|'.join([p for p in spec_display_parts if p])

                        price_value = sku.get('price') or sku.get('discountPrice') or ''
                        sku_list.append({
                            'canBookCount': str(sku.get('canBookCount') or sku.get('stock') or sku.get('quantity') or ''),
                            'price': str(price_value),
                            'specAttrs': spec
                        })
        
        return sku_list

    def extract_range_prices(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất bảng giá theo số lượng"""
        out = []
        
        # Thử các đường dẫn khác nhau cho range prices
        price_paths = [
            'data.rangePrices',
            'data.product.rangePrices',
            'data.item.rangePrices',
            'rangePrices',
            'product.rangePrices',
            'item.rangePrices'
        ]
        
        for path in price_paths:
            price_data = self.get_nested(data, path, [])
            if isinstance(price_data, list) and price_data:
                for i, p in enumerate(price_data):
                    if isinstance(p, dict):
                        begin = int(p.get('beginAmount') or p.get('minQuantity') or 1)
                        price = float(p.get('price') or p.get('unitPrice') or 0)
                        end = int(p.get('endAmount') or p.get('maxQuantity') or 999999)
                        
                        out.append({
                            'beginAmount': begin,
                            'price': price,
                            'endAmount': end,
                            'discountPrice': float(p.get('discountPrice') or price)
                        })
                if out:
                    break
        
        # Nếu không tìm thấy rangePrices, thử tìm wholesales (cấu trúc của pugo)
        if not out:
            wholesales_paths = [
                'data.wholesales',
                'data.product.wholesales',
                'data.item.wholesales',
                'wholesales',
                'product.wholesales',
                'item.wholesales'
            ]
            
            for path in wholesales_paths:
                wholesales_data = self.get_nested(data, path, [])
                if isinstance(wholesales_data, list) and wholesales_data:
                    for w in wholesales_data:
                        if isinstance(w, dict):
                            begin = int(w.get('begin') or w.get('minQuantity') or 1)
                            price = float(w.get('price') or w.get('unitPrice') or 0)
                            end = int(w.get('end') or w.get('maxQuantity') or 0)
                            
                            # Xử lý trường hợp end = 0 (không giới hạn)
                            if end == 0:
                                end = 999999
                            
                            out.append({
                                'beginAmount': begin,
                                'price': price,
                                'endAmount': end,
                                'discountPrice': price  # Trong wholesales thường không có discountPrice riêng
                            })
                    if out:
                        break
        
        # Nếu vẫn không có rangePrices, tạo từ giá cơ bản (cho trường hợp Taobao)
        if not out:
            base_price = None
            # Ưu tiên startPrice (giá cơ bản) trước sellPrice (giá cao nhất)
            price_paths = [
                'data.startPrice', 
                'data.price',
                'startPrice',
                'price',
                'data.sellPrice',
                'sellPrice'
            ]
            
            for path in price_paths:
                price = self.get_nested(data, path)
                if price is not None and float(price) > 0:
                    base_price = float(price)
                    break
            
            if base_price:
                out.append({
                    'beginAmount': 1,
                    'price': base_price,
                    'endAmount': 999999,
                    'discountPrice': base_price
                })
        
        return out

    def extract_max_price(self, data: Dict) -> str:
        """Trích xuất giá cao nhất"""
        # Thử lấy từ range prices trước
        range_prices = self.extract_range_prices(data)
        if range_prices:
            return str(max([p['price'] for p in range_prices]))
        
        # Thử các đường dẫn khác cho giá - ưu tiên startPrice (giá cơ bản) trước sellPrice
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
        ]
        
        for path in price_paths:
            price = self.get_nested(data, path)
            if price is not None and str(price) != '0':
                return str(price)
        
        return '0.00'

    def extract_name(self, data: Dict) -> str:
        """Trích xuất tên sản phẩm"""
        # Thử các đường dẫn khác nhau cho tên sản phẩm
        name_paths = [
            'data.name',
            'data.product.name',
            'data.item.name',
            'data.title',
            'data.product.title',
            'data.item.title',
            'name',
            'product.name',
            'item.name',
            'title',
            'product.title',
            'item.title'
        ]
        
        for path in name_paths:
            name = self.get_nested(data, path)
            if name and isinstance(name, str):
                return name
        
        return ''

    def extract_source_id(self, data: Dict) -> str:
        """Trích xuất source ID"""
        # Thử các đường dẫn khác nhau cho source ID
        # Ưu tiên productId trước vì đây là ID thực của sản phẩm
        id_paths = [
            'data.sourceId',
            'data.product.sourceId',
            'data.item.sourceId',
            'data.productId',  # Ưu tiên productId trước id
            'data.product.productId',
            'data.item.productId',
            'data.id',
            'data.product.id',
            'data.item.id',
            'sourceId',
            'product.sourceId',
            'item.sourceId',
            'productId',
            'product.productId',
            'item.productId',
            'id',
            'product.id',
            'item.id'
        ]
        
        for path in id_paths:
            source_id = self.get_nested(data, path)
            if source_id is not None and str(source_id) != '0':  # Bỏ qua giá trị 0
                return str(source_id)
        
        return ''

    def extract_description(self, data: Dict) -> str:
        """Trích xuất mô tả sản phẩm"""
        # Thử các đường dẫn khác nhau cho mô tả
        desc_paths = [
            'data.description',
            'data.product.description',
            'data.item.description',
            'data.desc',
            'data.product.desc',
            'data.item.desc',
            'description',
            'product.description',
            'item.description',
            'desc',
            'product.desc',
            'item.desc'
        ]
        
        for path in desc_paths:
            desc = self.get_nested(data, path)
            if desc and isinstance(desc, str):
                return desc
        
        return ''

    def extract_seller_info(self, data: Dict) -> Dict[str, Any]:
        """Trích xuất thông tin người bán"""
        seller_info = {}
        
        # Thử các đường dẫn khác nhau cho thông tin seller
        seller_paths = [
            'data.seller',
            'data.product.seller',
            'data.item.seller',
            'seller',
            'product.seller',
            'item.seller'
        ]
        
        for path in seller_paths:
            seller_data = self.get_nested(data, path, {})
            if isinstance(seller_data, dict) and seller_data:
                seller_info = {
                    'name': seller_data.get('name') or seller_data.get('sellerName') or '',
                    'id': seller_data.get('id') or seller_data.get('sellerId') or '',
                    'rating': seller_data.get('rating') or seller_data.get('score') or '',
                    'location': seller_data.get('location') or seller_data.get('address') or ''
                }
                break
        
        return seller_info

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform dữ liệu raw từ pugo.vn extractor thành format chuẩn
        """
        if not raw or 'raw_data' not in raw:
            return {}

        data = raw['raw_data']
        
        # Nếu raw_data có nested data từ API response (pugo: data.data)
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
        sourceId = self.extract_source_id(api_data) or raw.get('sourceId') or ''
        description = self.extract_description(api_data)
        seller_info = self.extract_seller_info(api_data)
        
        # Lấy URL từ dữ liệu pugo (itemUrl) hoặc từ raw data
        url = self.get_nested(api_data, 'itemUrl') or raw.get('url') or ''
        if not url and sourceId:
            # Fallback: tạo URL từ sourceId
            url = f"https://pugo.vn/item/{sourceId}"

        # Xác định source type thực tế từ URL
        actual_source_type = self.detect_source_type(url)

        # Trả về cấu trúc giống transformer_1688.py (đúng các key backend đang nhận)
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
            'sourceType': actual_source_type,  # Sử dụng source type thực tế
            'url': url,
        }


# Tạo instance global
transformer_pugo = TransformerPugo()
