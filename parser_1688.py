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
        # Regex đa dòng để bắt object context truyền vào function
        self.context_full_regex = re.compile(
            r"window\\.context\\s*=\\s*\\(function\\([^)]*\\)\\s*{[\\s\\S]*?}\\s*\\)\\s*\\([^,]+,\\s*({[\\s\\S]*?})\\s*\\);",
            re.DOTALL
        )
    
    def extract_window_context(self, html_content: str) -> Optional[Dict]:
        """Trích xuất window.context object từ HTML content"""
        try:
            # Thử bắt theo regex đa dòng trước
            try:
                m = self.context_full_regex.search(html_content)
                if m:
                    json_str = m.group(1)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        # Thử dùng Node để eval object literal
                        try:
                            import subprocess
                            import tempfile
                            import os
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                                f.write(f'''
try {{
  const data = {json_str};
  console.log(JSON.stringify(data));
}} catch (e) {{
  console.error("Error:" + e.message);
  process.exit(1);
}}
''')
                                temp_file = f.name
                            result = subprocess.run(['node', temp_file], capture_output=True, text=True, timeout=10)
                            os.unlink(temp_file)
                            if result.returncode == 0:
                                return json.loads(result.stdout.strip())
                            else:
                                logger.error(f"JavaScript parse error: {result.stderr}")
                        except Exception as e:
                            logger.debug(f"Node eval failed: {e}")
            except Exception as e:
                logger.debug(f"Regex đa dòng không parse được: {e}")

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
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
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
                "offerMaxPrice": "result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.offerMaxPrice",
                "offerPriceRanges": "result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.offerPriceRanges"
            }
            
            # Trích xuất thông tin cơ bản
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
            
            # Tìm kiếm skuMap ở nhiều vị trí khác nhau
            sku_map_paths = [
                "result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.skuMapOriginal",
                "result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.skuMap",
                "result.data.Root.fields.dataJson.skuModel.skuMap",
                "result.data.mainPrice.fields.finalPriceModel.skuMap"
            ]
            
            sku_map = None
            for path in sku_map_paths:
                sku_map = self.get_nested_value(context, path)
                if sku_map is not None:
                    logger.info(f"Đã tìm thấy skuMap tại path: {path}")
                    break
            
            product_info["parsed_data"]["skuMap"] = sku_map
            
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
                image_urls = re.findall(r'"([^\"]+)"', images_str)
                result["parsed_data"]["images"] = image_urls
                logger.info(f"Đã trích xuất {len(image_urls)} ảnh bằng regex")
            
            # Trích xuất offerPriceRanges (fallback nếu không parse được context)
            ranges_pattern = r'"offerPriceRanges"\s*:\s*\[(.*?)\]'
            ranges_match = re.search(ranges_pattern, html_content, re.DOTALL)
            if ranges_match:
                ranges_str = ranges_match.group(1)
                # Tách các object trong mảng
                raw_objs = re.findall(r'\{[^\}]*\}', ranges_str)
                offer_ranges = []
                for obj in raw_objs:
                    price_match = re.search(r'"price"\s*:\s*"([^"]+)"', obj)
                    discount_match = re.search(r'"discountPrice"\s*:\s*"([^"]+)"', obj)
                    begin_match = re.search(r'"beginAmount"\s*:\s*(\d+)', obj)
                    end_match = re.search(r'"endAmount"\s*:\s*(\d+)', obj)
                    offer_ranges.append({
                        "price": price_match.group(1) if price_match else "",
                        "beginAmount": int(begin_match.group(1)) if begin_match else 0,
                        "discountPrice": discount_match.group(1) if discount_match else "",
                        "endAmount": int(end_match.group(1)) if end_match else 0,
                    })
                result["parsed_data"]["offerPriceRanges"] = offer_ranges
                logger.info(f"Đã trích xuất offerPriceRanges bằng regex: {len(offer_ranges)} mức")
            
            # Trích xuất SKU properties
            sku_pattern = r'"skuProps":\[(.*?)\]'
            sku_match = re.search(sku_pattern, html_content, re.DOTALL)
            if sku_match:
                sku_str = sku_match.group(1)
                # Parse SKU properties đơn giản
                sku_props = []
                prop_matches = re.findall(r'\{[^\}]+\}', sku_str)
                for prop_match in prop_matches:
                    # Trích xuất tên property và fid
                    prop_name_match = re.search(r'"prop":"([^"]+)"', prop_match)
                    fid_match = re.search(r'"fid":(\d+)', prop_match)
                    
                    if prop_name_match:
                        prop_name = prop_name_match.group(1)
                        fid = fid_match.group(1) if fid_match else ""
                        
                        # Trích xuất các giá trị với vid
                        value_matches = re.findall(r'\{[^\}]+\}', prop_match)
                        values = []
                        for value_match in value_matches:
                            name_match = re.search(r'"name":"([^"]+)"', value_match)
                            vid_match = re.search(r'"vid":(\d+)', value_match)
                            image_match = re.search(r'"imageUrl":"([^\"]*)"', value_match)
                            
                            if name_match:
                                value = {
                                    "name": name_match.group(1),
                                    "vid": vid_match.group(1) if vid_match else "",
                                    "image_url": image_match.group(1) if image_match else ""
                                }
                                values.append(value)
                        
                        sku_props.append({
                            "property_name": prop_name,
                            "property_id": fid,
                            "values": values
                        })
                
                result["parsed_data"]["skuProps"] = sku_props
                logger.info(f"Đã trích xuất {len(sku_props)} SKU properties bằng regex")
            
            # Trích xuất SKU Map Original
            sku_map_pattern = r'"skuMapOriginal":\[(.*?)\]'
            sku_map_match = re.search(sku_map_pattern, html_content, re.DOTALL)
            if sku_map_match:
                sku_map_str = sku_map_match.group(1)
                logger.info(f"Found skuMapOriginal string: {sku_map_str[:200]}...")
                
                # Parse SKU Map đơn giản
                sku_map = []
                # Tìm tất cả các object trong array
                sku_entries = re.findall(r'\{[^}]+\}', sku_map_str)
                logger.info(f"Found {len(sku_entries)} SKU entries")
                
                for entry in sku_entries:
                    # Trích xuất thông tin cơ bản từ SKU Map entry
                    sku_id_match = re.search(r'"skuId":(\d+)', entry)
                    spec_attrs_match = re.search(r'"specAttrs":"([^"]+)"', entry)
                    price_match = re.search(r'"price":"([^"]+)"', entry)
                    can_book_count_match = re.search(r'"canBookCount":(\d+)', entry)
                    sale_count_match = re.search(r'"saleCount":(\d+)', entry)
                    spec_id_match = re.search(r'"specId":"([^"]+)"', entry)
                    
                    if sku_id_match:
                        sku_entry = {
                            "skuId": sku_id_match.group(1),
                            "specAttrs": spec_attrs_match.group(1) if spec_attrs_match else "",
                            "price": price_match.group(1) if price_match else "",
                            "canBookCount": can_book_count_match.group(1) if can_book_count_match else "0",
                            "saleCount": sale_count_match.group(1) if sale_count_match else "0",
                            "specId": spec_id_match.group(1) if spec_id_match else ""
                        }
                        sku_map.append(sku_entry)
                
                result["parsed_data"]["skuMap"] = sku_map
                logger.info(f"Đã trích xuất SKU Map Original với {len(sku_map)} entries bằng regex")
            else:
                # Thử tìm kiếm với pattern khác
                logger.warning("Không tìm thấy skuMapOriginal với pattern đầu tiên, thử pattern khác...")
                sku_map_pattern2 = r'skuMapOriginal":\[(.*?)\]'
                sku_map_match2 = re.search(sku_map_pattern2, html_content, re.DOTALL)
                if sku_map_match2:
                    sku_map_str = sku_map_match2.group(1)
                    logger.info(f"Found skuMapOriginal with pattern2: {sku_map_str[:200]}...")
                    
                    # Parse tương tự như trên
                    sku_map = []
                    sku_entries = re.findall(r'\{[^}]+\}', sku_map_str)
                    logger.info(f"Found {len(sku_entries)} SKU entries with pattern2")
                    
                    for entry in sku_entries:
                        sku_id_match = re.search(r'"skuId":(\d+)', entry)
                        spec_attrs_match = re.search(r'"specAttrs":"([^"]+)"', entry)
                        price_match = re.search(r'"price":"([^"]+)"', entry)
                        can_book_count_match = re.search(r'"canBookCount":(\d+)', entry)
                        sale_count_match = re.search(r'"saleCount":(\d+)', entry)
                        spec_id_match = re.search(r'"specId":"([^"]+)"', entry)
                        
                        if sku_id_match:
                            sku_entry = {
                                "skuId": sku_id_match.group(1),
                                "specAttrs": spec_attrs_match.group(1) if spec_attrs_match else "",
                                "price": price_match.group(1) if price_match else "",
                                "canBookCount": can_book_count_match.group(1) if can_book_count_match else "0",
                                "saleCount": sale_count_match.group(1) if sale_count_match else "0",
                                "specId": spec_id_match.group(1) if spec_id_match else ""
                            }
                            sku_map.append(sku_entry)
                    
                    result["parsed_data"]["skuMap"] = sku_map
                    logger.info(f"Đã trích xuất SKU Map Original với {len(sku_map)} entries bằng pattern2")
                else:
                    logger.warning("Không tìm thấy skuMapOriginal trong HTML")
            
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
                        "image_url": value.get("imageUrl", ""),
                        "vid": value.get("vid", "")  # Thêm vid cho mỗi value
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
                    "sku_properties": self.parse_sku_info(parsed_data.get("skuProps", [])),
                    "sku_map": parsed_data.get("skuMap", {}),
                    "offer_price_ranges": parsed_data.get("offerPriceRanges", [])
                },
                "raw_data": {
                    "images_count": len(parsed_data.get("images", [])),
                    "sku_props_count": len(parsed_data.get("skuProps", [])),
                    "has_name": bool(parsed_data.get("name")),
                    "has_price": bool(parsed_data.get("offerMaxPrice")),
                    "has_sku_map": bool(parsed_data.get("skuMap"))
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
