from typing import Any, Dict, List


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
        
        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        """Trích xuất thông tin SKU properties"""
        out = []
        
        # Thử các đường dẫn khác nhau cho SKU properties
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
                    if isinstance(prop, dict):
                        prop_name = prop.get('name') or prop.get('propertyName') or prop.get('prop')
                        if prop_name:
                            values = []
                            prop_values = prop.get('values', [])
                            if isinstance(prop_values, list):
                                for v in prop_values:
                                    if isinstance(v, dict):
                                        value_name = v.get('name') or v.get('valueName') or v.get('value')
                                        if value_name:
                                            value_item = {'name': value_name}
                                            # Thêm hình ảnh nếu có
                                            for img_key in ['image', 'imageUrl', 'img']:
                                                if img_key in v:
                                                    value_item['image'] = v[img_key]
                                                    break
                                            values.append(value_item)
                                    elif isinstance(v, str):
                                        values.append({'name': v})
                            
                            if values:
                                out.append({
                                    'name': prop_name,
                                    'values': values
                                })
                if out:
                    break
        
        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        """Trích xuất danh sách SKU"""
        sku_list = []
        
        # Thử các đường dẫn khác nhau cho SKU list
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
                        sku_item = {
                            'canBookCount': str(sku.get('canBookCount') or sku.get('stock') or sku.get('quantity') or ''),
                            'price': str(sku.get('price') or sku.get('salePrice') or ''),
                            'specAttrs': str(sku.get('specAttrs') or sku.get('specAttributes') or sku.get('spec') or '')
                        }
                        sku_list.append(sku_item)
                if sku_list:
                    break
        
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
        
        return out

    def extract_max_price(self, data: Dict) -> str:
        """Trích xuất giá cao nhất"""
        # Thử lấy từ range prices trước
        range_prices = self.extract_range_prices(data)
        if range_prices:
            return str(max([p['price'] for p in range_prices]))
        
        # Thử các đường dẫn khác
        price_paths = [
            'data.maxPrice',
            'data.product.maxPrice',
            'data.item.maxPrice',
            'maxPrice',
            'product.maxPrice',
            'item.maxPrice',
            'data.price',
            'data.product.price',
            'data.item.price'
        ]
        
        for path in price_paths:
            price = self.get_nested(data, path)
            if price is not None:
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
        id_paths = [
            'data.sourceId',
            'data.product.sourceId',
            'data.item.sourceId',
            'data.id',
            'data.product.id',
            'data.item.id',
            'sourceId',
            'product.sourceId',
            'item.sourceId',
            'id',
            'product.id',
            'item.id'
        ]
        
        for path in id_paths:
            source_id = self.get_nested(data, path)
            if source_id is not None:
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
        
        # Nếu raw_data có nested data từ API response
        if isinstance(data, dict) and 'data' in data:
            api_data = data['data']
        else:
            api_data = data

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
        
        # Tạo URL từ sourceId nếu cần
        url = raw.get('url') or ''
        if not url and sourceId:
            # Có thể cần điều chỉnh format URL dựa trên source
            url = f"https://pugo.vn/item/{sourceId}"

        return {
            'images': images,
            'skuProperty': skuProperty,
            'properties': skuProperty,  # Alias để tương thích
            'sku': sku,
            'maxPrice': maxPrice,
            'name': name,
            'sourceId': sourceId,
            'sourceType': 'pugo',
            'url': url,
            'rangePrices': rangePrices,
            'description': description,
            'seller': seller_info,
            # Thêm thông tin bổ sung
            'raw_data_keys': list(api_data.keys()) if isinstance(api_data, dict) else [],
            'extraction_timestamp': raw.get('timestamp', 0)
        }


# Tạo instance global
transformer_pugo = TransformerPugo()
