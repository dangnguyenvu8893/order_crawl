from typing import Any, Dict, List


class Transformer1688:
    """Chuẩn hoá dữ liệu theo logic backend data_transformer.js (flatten)."""

    def get_nested(self, obj: Dict, path: str, default=None):
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
        images = []
        images_data = self.get_nested(data, 'result.data.Root.fields.dataJson.images', [])
        if isinstance(images_data, list):
            for img in images_data:
                if isinstance(img, dict):
                    if img.get('fullPathImageURI'):
                        images.append(img['fullPathImageURI'])
                    elif img.get('imageURI'):
                        uri = img['imageURI']
                        if isinstance(uri, str) and uri.startswith('img/'):
                            images.append(f'https://cbu01.alicdn.com/{uri}')
                        else:
                            images.append(uri)
                elif isinstance(img, str):
                    images.append(img)
        return images

    def extract_sku_props(self, data: Dict) -> List[Dict[str, Any]]:
        out = []
        sku_props = self.get_nested(data, 'result.data.Root.fields.dataJson.skuModel.skuProps', [])
        if isinstance(sku_props, list):
            for prop in sku_props:
                if isinstance(prop, dict) and prop.get('prop') and isinstance(prop.get('value'), list):
                    values = []
                    for v in prop['value']:
                        if isinstance(v, dict):
                            item = {'name': v.get('name') or ''}
                            if v.get('imageUrl'):
                                item['image'] = v['imageUrl']
                            values.append(item)
                    out.append({'name': prop['prop'], 'values': values})
        return out

    def extract_sku_list(self, data: Dict) -> List[Dict[str, str]]:
        sku_list = []
        sku_map = self.get_nested(data, 'result.data.Root.fields.dataJson.skuModel.skuInfoMap', {})
        if isinstance(sku_map, dict):
            for _, info in sku_map.items():
                if isinstance(info, dict):
                    sku_list.append({
                        'canBookCount': str(info.get('canBookCount') or ''),
                        'price': '',
                        'specAttrs': str(info.get('specAttrs') or '').replace('&gt;', '|')
                    })
        return sku_list

    def extract_range_prices(self, data: Dict) -> List[Dict[str, Any]]:
        out = []
        arr = self.get_nested(data, 'result.data.Root.fields.dataJson.orderParamModel.orderParam.skuParam.skuRangePrices', [])
        if isinstance(arr, list):
            for i, p in enumerate(arr):
                begin = int(p.get('beginAmount') or 1)
                price = float(p.get('price') or 0)
                end = 999999
                if i + 1 < len(arr):
                    end = int(arr[i + 1].get('beginAmount') or 999999) - 1
                out.append({'beginAmount': begin, 'price': price, 'endAmount': end, 'discountPrice': price})
        return out

    def extract_max_price(self, data: Dict) -> str:
        arr = self.get_nested(data, 'result.data.Root.fields.dataJson.orderParamModel.orderParam.skuParam.skuRangePrices', [])
        if isinstance(arr, list) and arr:
            return str(arr[0].get('price') or '0.00')
        return '0.00'

    def extract_name(self, data: Dict) -> str:
        temp = self.get_nested(data, 'result.data.Root.fields.dataJson.tempModel', {})
        if isinstance(temp, dict):
            return str(temp.get('offerTitle') or '')
        return ''

    def extract_source_id(self, data: Dict) -> str:
        temp = self.get_nested(data, 'result.data.Root.fields.dataJson.tempModel', {})
        if isinstance(temp, dict):
            v = temp.get('offerId')
            return str(v) if v is not None else ''
        return ''

    def transform(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # raw: { status, raw_data, url, sourceId, ... }
        if not raw or 'raw_data' not in raw:
            return {}

        data = raw['raw_data']
        images = self.extract_images(data)
        skuProperty = self.extract_sku_props(data)
        sku = self.extract_sku_list(data)
        rangePrices = self.extract_range_prices(data)
        maxPrice = self.extract_max_price(data)
        name = self.extract_name(data)
        sourceId = self.extract_source_id(data) or raw.get('sourceId') or ''
        url = raw.get('url') or (f"https://detail.1688.com/offer/{sourceId}.html" if sourceId else '')

        return {
            'images': images,
            'skuProperty': skuProperty,
            # Alias để tương thích backend ProductService expects `properties`
            'properties': skuProperty,
            'sku': sku,
            'maxPrice': maxPrice,
            'name': name,
            'sourceId': sourceId,
            'sourceType': '1688',
            'url': url,
            'rangePrices': rangePrices,
        }


transformer_1688 = Transformer1688()
