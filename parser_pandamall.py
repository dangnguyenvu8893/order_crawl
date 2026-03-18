import re
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProductPandamallParser:
    """Parser để trích xuất thông tin sản phẩm từ Pandamall /item/details API response"""

    def __init__(self):
        self.patterns = {
            'taobao_id': r'id=(\d+)',
            '1688_id': r'/offer/(\d+)\.html',
            'url_pattern': r'https?://[^\s]+'
        }

    def can_handle_url(self, url: str) -> bool:
        """Kiểm tra xem URL có thể được xử lý bởi parser này không"""
        return bool(
            re.search(r'pandamall\.vn', url) or
            re.search(r'item\.taobao\.com', url) or
            re.search(r'detail\.1688\.com', url) or
            re.search(r'detail\.tmall\.com', url)
        )

    def extract_product_id(self, url: str) -> Optional[str]:
        """Trích xuất product ID từ source URL"""
        if "1688.com" in url:
            match = re.search(self.patterns['1688_id'], url)
        else:
            match = re.search(self.patterns['taobao_id'], url)
        return match.group(1) if match else None

    def parse_api_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response từ Pandamall /item/details API"""
        try:
            if not isinstance(response_data, dict):
                return {
                    "status": "error",
                    "message": "Invalid response data format"
                }

            # Pandamall response: data nằm trong response gốc
            # Thử lấy data từ các vị trí khác nhau
            data = response_data
            if 'data' in response_data and isinstance(response_data['data'], dict):
                data = response_data['data']

            parsed_info = {
                "status": "success",
                "parsed_data": {
                    "name": self._extract_name(data),
                    "images": self._extract_images(data),
                    "price_info": self._extract_price_info(data),
                    "sku_info": self._extract_sku_info(data),
                    "seller_info": self._extract_seller_info(data),
                    "description": self._extract_description(data)
                }
            }

            return parsed_info

        except Exception as e:
            logger.error(f"Lỗi khi parse API response: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def _extract_name(self, data: Dict[str, Any]) -> str:
        """Trích xuất tên sản phẩm"""
        # Pandamall response fields (từ sample thực tế + multi-path fallback)
        name_paths = [
            'title', 'name', 'productName', 'itemName',
            'item.title', 'item.name', 'product.title', 'product.name'
        ]

        for path in name_paths:
            value = self._get_nested_value(data, path)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return ""

    def _extract_images(self, data: Dict[str, Any]) -> List[str]:
        """Trích xuất danh sách hình ảnh"""
        images = []

        image_paths = [
            'images', 'imageList', 'gallery', 'photos', 'imgs',
            'item.images', 'product.images'
        ]

        for path in image_paths:
            images_data = self._get_nested_value(data, path)
            if isinstance(images_data, list):
                for img in images_data:
                    if isinstance(img, str):
                        images.append(img)
                    elif isinstance(img, dict):
                        for key in ['url', 'src', 'imageUrl', 'image']:
                            if key in img and isinstance(img[key], str):
                                images.append(img[key])
                                break
                if images:
                    break

        return images

    def _extract_price_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất thông tin giá"""
        price_info = {
            "max_price": "",
            "min_price": "",
            "currency": "CNY",
            "price_ranges": []
        }

        # Pandamall: giá nằm trong từng SKU entry của skuMappings (dict)
        classify = data.get('classify') or {}
        sku_mappings = classify.get('skuMappings') or {}

        if isinstance(sku_mappings, dict) and sku_mappings:
            prices = []
            for sku_key, sku_val in sku_mappings.items():
                if isinstance(sku_val, dict):
                    price = sku_val.get('price') or sku_val.get('promotionPrice') or 0
                    try:
                        prices.append(float(price))
                    except (ValueError, TypeError):
                        pass
            if prices:
                price_info["max_price"] = str(max(prices))
                price_info["min_price"] = str(min(prices))
            return price_info

        # Fallback: tìm giá ở các vị trí khác
        for path in ['price', 'minPrice', 'startPrice', 'item.price']:
            val = self._get_nested_value(data, path)
            if val:
                price_info["min_price"] = str(val)
                price_info["max_price"] = str(val)
                break

        return price_info

    def _extract_sku_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất thông tin SKU"""
        sku_info = {
            "properties": [],
            "variants": []
        }

        classify = data.get('classify') or {}

        # SKU properties: classify.skuProperties
        sku_properties = classify.get('skuProperties') or []
        if isinstance(sku_properties, list):
            for prop in sku_properties:
                if not isinstance(prop, dict):
                    continue
                prop_name = prop.get('propName') or prop.get('name') or ''
                prop_id = prop.get('propID') or prop.get('propId') or ''
                values = []
                for val in (prop.get('propValues') or prop.get('values') or []):
                    if isinstance(val, dict):
                        values.append({
                            'name': val.get('valueName') or val.get('name') or '',
                            'valueID': str(val.get('valueID') or val.get('valueId') or ''),
                            'image': val.get('image') or val.get('imageUrl') or ''
                        })
                if prop_name and values:
                    sku_info['properties'].append({
                        'name': prop_name,
                        'propID': str(prop_id),
                        'values': values
                    })

        # SKU variants: classify.skuMappings (dict format)
        sku_mappings = classify.get('skuMappings') or {}
        if isinstance(sku_mappings, dict):
            for mapping_key, sku_val in sku_mappings.items():
                if isinstance(sku_val, dict):
                    sku_info['variants'].append({
                        'skuID': str(sku_val.get('skuID') or sku_val.get('skuId') or ''),
                        'mappingKey': mapping_key,
                        'price': str(sku_val.get('price') or ''),
                        'promotionPrice': str(sku_val.get('promotionPrice') or ''),
                        'stock': str(sku_val.get('stock') or sku_val.get('quantity') or '')
                    })

        return sku_info

    def _extract_seller_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất thông tin người bán"""
        seller_info = {
            "name": "",
            "id": "",
            "rating": "",
            "location": ""
        }

        for path in ['seller', 'shop', 'merchant', 'item.seller']:
            seller_data = self._get_nested_value(data, path)
            if isinstance(seller_data, dict) and seller_data:
                seller_info.update({
                    "name": seller_data.get('name') or seller_data.get('sellerName') or '',
                    "id": seller_data.get('id') or seller_data.get('sellerId') or '',
                    "rating": seller_data.get('rating') or seller_data.get('score') or '',
                    "location": seller_data.get('location') or seller_data.get('address') or ''
                })
                break

        return seller_info

    def _extract_description(self, data: Dict[str, Any]) -> str:
        """Trích xuất mô tả sản phẩm"""
        for path in ['description', 'desc', 'detail', 'content', 'item.description']:
            desc = self._get_nested_value(data, path)
            if isinstance(desc, str) and desc.strip():
                return desc.strip()
        return ""

    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Lấy giá trị từ object theo đường dẫn nested"""
        try:
            if '.' in path:
                keys = path.split('.')
                current = obj
                for key in keys:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return None
                return current
            else:
                return obj.get(path)
        except Exception:
            return None

    def get_formatted_product_info(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Lấy thông tin sản phẩm đã được format"""
        try:
            parsed_info = self.parse_api_response(response_data)

            if parsed_info["status"] != "success":
                return parsed_info

            parsed_data = parsed_info["parsed_data"]

            formatted_info = {
                "status": "success",
                "product": {
                    "name": parsed_data.get("name", ""),
                    "images": parsed_data.get("images", []),
                    "price_info": parsed_data.get("price_info", {}),
                    "sku_info": parsed_data.get("sku_info", {}),
                    "seller_info": parsed_data.get("seller_info", {}),
                    "description": parsed_data.get("description", "")
                },
                "raw_data": {
                    "has_name": bool(parsed_data.get("name")),
                    "images_count": len(parsed_data.get("images", [])),
                    "has_price": bool(parsed_data.get("price_info", {}).get("max_price")),
                    "has_sku": bool(parsed_data.get("sku_info", {}).get("properties"))
                }
            }

            return formatted_info

        except Exception as e:
            logger.error(f"Lỗi khi format product info: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# Tạo instance global
parser_pandamall = ProductPandamallParser()
