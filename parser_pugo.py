import re
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ProductPugoParser:
    """Parser để trích xuất thông tin sản phẩm từ pugo.vn"""

    def __init__(self):
        self.patterns = {
            'product_id': r'pugo\.vn/item/(\d+)',
            'taobao_id': r'id=(\d+)',
            'url_pattern': r'https?://[^\s]+'
        }

    def can_handle_url(self, url: str) -> bool:
        """Kiểm tra xem URL có thể được xử lý bởi parser này không"""
        return bool(re.search(r'pugo\.vn', url) or re.search(r'item\.taobao\.com', url))

    def extract_product_id(self, url: str) -> Optional[str]:
        """Trích xuất product ID từ URL"""
        # Thử extract từ pugo.vn URL
        match = re.search(self.patterns['product_id'], url)
        if match:
            return match.group(1)
        
        # Thử extract từ Taobao URL
        match = re.search(self.patterns['taobao_id'], url)
        if match:
            return match.group(1)
        
        return None

    def parse_api_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response từ pugo.vn API"""
        try:
            if not isinstance(response_data, dict):
                return {
                    "status": "error",
                    "message": "Invalid response data format"
                }

            # Kiểm tra status của response
            if response_data.get('status') != 'success':
                return {
                    "status": "error",
                    "message": f"API response error: {response_data.get('message', 'Unknown error')}"
                }

            # Lấy data từ response
            data = response_data.get('data', {})
            if not data:
                return {
                    "status": "error",
                    "message": "No data in API response"
                }

            # Parse thông tin cơ bản
            parsed_info = {
                "status": "success",
                "parsed_data": {
                    "name": self._extract_name(data),
                    "images": self._extract_images(data),
                    "price_info": self._extract_price_info(data),
                    "sku_info": self._extract_sku_info(data),
                    "seller_info": self._extract_seller_info(data),
                    "description": self._extract_description(data),
                    "specifications": self._extract_specifications(data)
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
        name_paths = [
            'name', 'title', 'productName', 'itemName',
            'product.name', 'item.name', 'product.title', 'item.title'
        ]
        
        for path in name_paths:
            if '.' in path:
                # Nested path
                keys = path.split('.')
                current = data
                try:
                    for key in keys:
                        current = current[key]
                    if isinstance(current, str) and current.strip():
                        return current.strip()
                except (KeyError, TypeError):
                    continue
            else:
                # Direct path
                if path in data and isinstance(data[path], str) and data[path].strip():
                    return data[path].strip()
        
        return ""

    def _extract_images(self, data: Dict[str, Any]) -> List[str]:
        """Trích xuất danh sách hình ảnh"""
        images = []
        
        image_paths = [
            'images', 'imageList', 'gallery', 'photos',
            'product.images', 'item.images', 'product.gallery', 'item.gallery'
        ]
        
        for path in image_paths:
            if '.' in path:
                # Nested path
                keys = path.split('.')
                current = data
                try:
                    for key in keys:
                        current = current[key]
                    if isinstance(current, list):
                        for img in current:
                            if isinstance(img, str):
                                images.append(img)
                            elif isinstance(img, dict):
                                for key in ['url', 'src', 'imageUrl', 'image']:
                                    if key in img and isinstance(img[key], str):
                                        images.append(img[key])
                                        break
                except (KeyError, TypeError):
                    continue
            else:
                # Direct path
                if path in data and isinstance(data[path], list):
                    for img in data[path]:
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
            "currency": "VND",
            "price_ranges": []
        }
        
        # Tìm giá cao nhất
        price_paths = [
            'maxPrice', 'max_price', 'highestPrice', 'price',
            'product.maxPrice', 'item.maxPrice', 'product.price', 'item.price'
        ]
        
        for path in price_paths:
            price = self._get_nested_value(data, path)
            if price:
                price_info["max_price"] = str(price)
                break
        
        # Tìm giá thấp nhất
        min_price_paths = [
            'minPrice', 'min_price', 'lowestPrice',
            'product.minPrice', 'item.minPrice'
        ]
        
        for path in min_price_paths:
            price = self._get_nested_value(data, path)
            if price:
                price_info["min_price"] = str(price)
                break
        
        # Tìm bảng giá theo số lượng
        range_paths = [
            'priceRanges', 'rangePrices', 'bulkPrices',
            'product.priceRanges', 'item.priceRanges'
        ]
        
        for path in range_paths:
            ranges = self._get_nested_value(data, path)
            if isinstance(ranges, list):
                for range_item in ranges:
                    if isinstance(range_item, dict):
                        price_range = {
                            "min_quantity": range_item.get('beginAmount', range_item.get('minQuantity', 1)),
                            "max_quantity": range_item.get('endAmount', range_item.get('maxQuantity', 999999)),
                            "price": range_item.get('price', range_item.get('unitPrice', '')),
                            "discount_price": range_item.get('discountPrice', range_item.get('salePrice', ''))
                        }
                        price_info["price_ranges"].append(price_range)
                break
        
        return price_info

    def _extract_sku_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất thông tin SKU"""
        sku_info = {
            "properties": [],
            "variants": []
        }
        
        # Tìm SKU properties
        prop_paths = [
            'skuProperties', 'properties', 'variants',
            'product.skuProperties', 'item.skuProperties'
        ]
        
        for path in prop_paths:
            props = self._get_nested_value(data, path)
            if isinstance(props, list):
                for prop in props:
                    if isinstance(prop, dict):
                        property_info = {
                            "name": prop.get('name', prop.get('propertyName', '')),
                            "values": []
                        }
                        
                        values = prop.get('values', [])
                        if isinstance(values, list):
                            for value in values:
                                if isinstance(value, dict):
                                    value_info = {
                                        "name": value.get('name', value.get('valueName', '')),
                                        "image": value.get('image', value.get('imageUrl', ''))
                                    }
                                    property_info["values"].append(value_info)
                                elif isinstance(value, str):
                                    property_info["values"].append({"name": value})
                        
                        if property_info["name"] and property_info["values"]:
                            sku_info["properties"].append(property_info)
                break
        
        # Tìm SKU variants
        variant_paths = [
            'skuList', 'variants', 'options',
            'product.skuList', 'item.skuList'
        ]
        
        for path in variant_paths:
            variants = self._get_nested_value(data, path)
            if isinstance(variants, list):
                for variant in variants:
                    if isinstance(variant, dict):
                        variant_info = {
                            "sku_id": variant.get('skuId', variant.get('id', '')),
                            "spec_attrs": variant.get('specAttrs', variant.get('specAttributes', '')),
                            "price": variant.get('price', ''),
                            "stock": variant.get('canBookCount', variant.get('stock', variant.get('quantity', ''))),
                            "sold_count": variant.get('saleCount', variant.get('soldCount', ''))
                        }
                        sku_info["variants"].append(variant_info)
                break
        
        return sku_info

    def _extract_seller_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất thông tin người bán"""
        seller_info = {
            "name": "",
            "id": "",
            "rating": "",
            "location": "",
            "shop_url": ""
        }
        
        seller_paths = [
            'seller', 'shop', 'merchant',
            'product.seller', 'item.seller'
        ]
        
        for path in seller_paths:
            seller = self._get_nested_value(data, path)
            if isinstance(seller, dict):
                seller_info.update({
                    "name": seller.get('name', seller.get('sellerName', '')),
                    "id": seller.get('id', seller.get('sellerId', '')),
                    "rating": seller.get('rating', seller.get('score', '')),
                    "location": seller.get('location', seller.get('address', '')),
                    "shop_url": seller.get('shopUrl', seller.get('url', ''))
                })
                break
        
        return seller_info

    def _extract_description(self, data: Dict[str, Any]) -> str:
        """Trích xuất mô tả sản phẩm"""
        desc_paths = [
            'description', 'desc', 'detail', 'content',
            'product.description', 'item.description'
        ]
        
        for path in desc_paths:
            desc = self._get_nested_value(data, path)
            if isinstance(desc, str) and desc.strip():
                return desc.strip()
        
        return ""

    def _extract_specifications(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Trích xuất thông số kỹ thuật"""
        specifications = []
        
        spec_paths = [
            'specifications', 'specs', 'attributes',
            'product.specifications', 'item.specifications'
        ]
        
        for path in spec_paths:
            specs = self._get_nested_value(data, path)
            if isinstance(specs, list):
                for spec in specs:
                    if isinstance(spec, dict):
                        spec_info = {
                            "name": spec.get('name', spec.get('key', '')),
                            "value": spec.get('value', spec.get('val', ''))
                        }
                        if spec_info["name"] and spec_info["value"]:
                            specifications.append(spec_info)
                break
            elif isinstance(specs, dict):
                for key, value in specs.items():
                    if isinstance(value, str):
                        specifications.append({
                            "name": key,
                            "value": value
                        })
                break
        
        return specifications

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
            
            # Format thông tin theo chuẩn
            formatted_info = {
                "status": "success",
                "product": {
                    "name": parsed_data.get("name", ""),
                    "images": parsed_data.get("images", []),
                    "price_info": parsed_data.get("price_info", {}),
                    "sku_info": parsed_data.get("sku_info", {}),
                    "seller_info": parsed_data.get("seller_info", {}),
                    "description": parsed_data.get("description", ""),
                    "specifications": parsed_data.get("specifications", [])
                },
                "raw_data": {
                    "has_name": bool(parsed_data.get("name")),
                    "images_count": len(parsed_data.get("images", [])),
                    "has_price": bool(parsed_data.get("price_info", {}).get("max_price")),
                    "has_sku": bool(parsed_data.get("sku_info", {}).get("properties")),
                    "has_seller": bool(parsed_data.get("seller_info", {}).get("name"))
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
parser_pugo = ProductPugoParser()
