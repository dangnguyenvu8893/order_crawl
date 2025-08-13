import re
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class Product1688Parser:
    """Parser để trích xuất thông tin sản phẩm từ trang 1688.com"""
    
    def __init__(self):
        self.patterns = {
            'window_context': r'window\.context\s*=\s*({.*?});',
            'window_context_function': r'window\.context\s*=\s*\(function\([^)]*\)\s*{.*?}\s*\)\s*\([^)]*,\s*({.*?})\);',
            'window_context_complex': r'window\.context\s*=\s*\(function\([^)]*\)\s*{.*?}\s*\)\s*\([^)]*,\s*({.*?})\);'
        }
    
    def extract_window_context(self, html_content: str) -> Optional[Dict]:
        """Trích xuất window.context object từ HTML content"""
        try:
            # Tìm dòng chứa window.context
            lines = html_content.split('\n')
            context_line = None
            
            for line in lines:
                if 'window.context=' in line and 'window.contextPath,' in line:
                    context_line = line.strip()
                    break
            
            if not context_line:
                logger.warning("Không tìm thấy dòng window.context trong HTML")
                return None
            
            # Trích xuất object JSON từ dòng này
            # Pattern: window.context=(function(...){...})(window.contextPath, {...});
            
            # Tìm vị trí bắt đầu của object JSON
            start_marker = 'window.contextPath,'
            start_pos = context_line.find(start_marker)
            
            if start_pos == -1:
                logger.warning("Không tìm thấy marker window.contextPath")
                return None
            
            # Tìm vị trí bắt đầu của object JSON
            json_start = start_pos + len(start_marker)
            
            # Tìm vị trí kết thúc của object JSON bằng cách đếm dấu ngoặc
            brace_count = 0
            json_end = json_start
            in_string = False
            escape_next = False
            
            for i in range(json_start, len(context_line)):
                char = context_line[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
            
            if brace_count != 0:
                logger.warning("Không tìm thấy object JSON hoàn chỉnh")
                return None
            
            # Trích xuất JSON string
            json_str = context_line[json_start:json_end]
            
            # Thử parse JSON với xử lý encoding
            try:
                # Thử parse trực tiếp
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Lỗi JSON decode: {e}, thử xử lý encoding...")
                
                # Thử xử lý encoding issues
                try:
                    # Thay thế các ký tự có thể gây lỗi
                    cleaned_json = json_str
                    
                    # Xử lý các ký tự đặc biệt trong JSON
                    cleaned_json = cleaned_json.replace('\\', '\\\\')
                    cleaned_json = cleaned_json.replace('"', '\\"')
                    
                    # Thử parse lại
                    return json.loads(cleaned_json)
                except json.JSONDecodeError as e2:
                    logger.error(f"Vẫn lỗi sau khi xử lý encoding: {e2}")
                    logger.error(f"JSON string (200 chars): {json_str[:200]}...")
                    
                    # Thử một cách khác - sử dụng JavaScript để parse
                    try:
                        import subprocess
                        import tempfile
                        import os
                        
                        # Tạo file JavaScript tạm thời
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                            f.write(f'''
const fs = require('fs');
try {{
    const data = {json_str};
    console.log(JSON.stringify(data));
}} catch (e) {{
    console.error("Error:", e.message);
    process.exit(1);
}}
''')
                            temp_file = f.name
                        
                        # Chạy JavaScript để parse JSON
                        result = subprocess.run(['node', temp_file], capture_output=True, text=True, timeout=10)
                        
                        # Xóa file tạm thời
                        os.unlink(temp_file)
                        
                        if result.returncode == 0:
                            return json.loads(result.stdout.strip())
                        else:
                            logger.error(f"JavaScript parse error: {result.stderr}")
                            return None
                            
                    except Exception as js_error:
                        logger.error(f"Lỗi khi sử dụng JavaScript: {js_error}")
                        return None
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất window.context: {e}")
            return None
    
    def get_nested_value(self, obj: Dict, path: str, default=None) -> Any:
        """Lấy giá trị từ object theo đường dẫn nested (ví dụ: 'result.data.gallery.fields.offerImgList')"""
        try:
            keys = path.split('.')
            current = obj
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            
            return current
        except Exception as e:
            logger.error(f"Lỗi khi lấy giá trị từ path '{path}': {e}")
            return default
    
    def parse_product_info(self, html_content: str) -> Dict[str, Any]:
        """Parse thông tin sản phẩm từ HTML content"""
        try:
            # Trích xuất window.context
            context = self.extract_window_context(html_content)
            if not context:
                # Thử trích xuất trực tiếp bằng regex
                logger.info("Thử trích xuất trực tiếp bằng regex...")
                return self.extract_direct_info(html_content)
            
            # Định nghĩa các đường dẫn cần trích xuất
            extraction_paths = {
                "images": "result.data.gallery.fields.offerImgList",
                "name": "result.data.Root.fields.dataJson.tempModel.offerTitle",
                "skuProps": "result.data.Root.fields.dataJson.skuModel.skuProps",
                "offerMaxPrice": "result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.offerMaxPrice"
            }
            
            # Trích xuất thông tin
            product_info = {
                "status": "success",
                "parsed_data": {}
            }
            
            for key, path in extraction_paths.items():
                value = self.get_nested_value(context, path)
                product_info["parsed_data"][key] = value
                
                if value is not None:
                    logger.info(f"Đã trích xuất {key}: {type(value).__name__}")
                else:
                    logger.warning(f"Không tìm thấy dữ liệu cho {key} tại path: {path}")
            
            # Thêm thông tin bổ sung
            product_info["parsed_data"]["raw_context_keys"] = list(context.keys()) if context else []
            
            return product_info
            
        except Exception as e:
            logger.error(f"Lỗi khi parse product info: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def extract_direct_info(self, html_content: str) -> Dict[str, Any]:
        """Trích xuất thông tin trực tiếp bằng regex"""
        try:
            result = {
                "status": "success",
                "parsed_data": {}
            }
            
            # Trích xuất tên sản phẩm
            title_pattern = r'"offerTitle":"([^"]+)"'
            title_match = re.search(title_pattern, html_content)
            if title_match:
                result["parsed_data"]["name"] = title_match.group(1)
                logger.info("Đã trích xuất tên sản phẩm bằng regex")
            
            # Trích xuất giá tối đa
            price_pattern = r'"offerMaxPrice":"([^"]+)"'
            price_match = re.search(price_pattern, html_content)
            if price_match:
                result["parsed_data"]["offerMaxPrice"] = price_match.group(1)
                logger.info("Đã trích xuất giá tối đa bằng regex")
            
            # Trích xuất danh sách ảnh
            images_pattern = r'"offerImgList":\[(.*?)\]'
            images_match = re.search(images_pattern, html_content, re.DOTALL)
            if images_match:
                images_str = images_match.group(1)
                # Tách các URL ảnh
                image_urls = re.findall(r'"([^"]+)"', images_str)
                result["parsed_data"]["images"] = image_urls
                logger.info(f"Đã trích xuất {len(image_urls)} ảnh bằng regex")
            
            # Trích xuất SKU properties
            sku_pattern = r'"skuProps":\[(.*?)\]'
            sku_match = re.search(sku_pattern, html_content, re.DOTALL)
            if sku_match:
                sku_str = sku_match.group(1)
                # Parse SKU properties đơn giản
                sku_props = []
                prop_matches = re.findall(r'\{[^}]+\}', sku_str)
                for prop_match in prop_matches:
                    # Trích xuất tên property
                    prop_name_match = re.search(r'"prop":"([^"]+)"', prop_match)
                    if prop_name_match:
                        prop_name = prop_name_match.group(1)
                        # Trích xuất các giá trị
                        values = re.findall(r'"name":"([^"]+)"', prop_match)
                        sku_props.append({
                            "property_name": prop_name,
                            "values": [{"name": v} for v in values]
                        })
                
                result["parsed_data"]["skuProps"] = sku_props
                logger.info(f"Đã trích xuất {len(sku_props)} SKU properties bằng regex")
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất trực tiếp: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def parse_sku_info(self, sku_props: List[Dict]) -> List[Dict]:
        """Parse thông tin SKU từ skuProps"""
        try:
            if not sku_props:
                return []
            
            parsed_skus = []
            for prop in sku_props:
                sku_info = {
                    "property_name": prop.get("prop", ""),
                    "property_id": prop.get("fid", ""),
                    "values": []
                }
                
                for value in prop.get("value", []):
                    sku_value = {
                        "name": value.get("name", ""),
                        "image_url": value.get("imageUrl", "")
                    }
                    sku_info["values"].append(sku_value)
                
                parsed_skus.append(sku_info)
            
            return parsed_skus
            
        except Exception as e:
            logger.error(f"Lỗi khi parse SKU info: {e}")
            return []
    
    def parse_images(self, images: List[str]) -> List[Dict]:
        """Parse thông tin hình ảnh"""
        try:
            if not images:
                return []
            
            parsed_images = []
            for i, img_url in enumerate(images):
                image_info = {
                    "index": i,
                    "url": img_url,
                    "is_main": i == 0  # Ảnh đầu tiên là ảnh chính
                }
                parsed_images.append(image_info)
            
            return parsed_images
            
        except Exception as e:
            logger.error(f"Lỗi khi parse images: {e}")
            return []
    
    def get_formatted_product_info(self, html_content: str) -> Dict[str, Any]:
        """Lấy thông tin sản phẩm đã được format"""
        try:
            # Parse thông tin cơ bản
            product_info = self.parse_product_info(html_content)
            
            if product_info["status"] != "success":
                return product_info
            
            parsed_data = product_info["parsed_data"]
            
            # Format thông tin
            formatted_info = {
                "status": "success",
                "product": {
                    "name": parsed_data.get("name", ""),
                    "max_price": parsed_data.get("offerMaxPrice", ""),
                    "images": self.parse_images(parsed_data.get("images", [])),
                    "sku_properties": self.parse_sku_info(parsed_data.get("skuProps", []))
                },
                "raw_data": {
                    "images_count": len(parsed_data.get("images", [])),
                    "sku_props_count": len(parsed_data.get("skuProps", [])),
                    "has_name": bool(parsed_data.get("name")),
                    "has_price": bool(parsed_data.get("offerMaxPrice"))
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
parser_1688 = Product1688Parser()
