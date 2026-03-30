import json
import logging
import os
import random
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

PROVIDER_CHAINS = {
    '1688': [
        {'provider': 'gianghuy', 'action': 'gianghuy_1688_detail'},
        {'provider': 'pandamall', 'action': 'pandamall_detail'},
        {'provider': 'hangve', 'action': 'hangve_full'},
    ],
    'taobao': [
        {'provider': 'gianghuy', 'action': 'gianghuy_taobao_detail'},
        {'provider': 'pandamall', 'action': 'pandamall_detail'},
        {'provider': 'hangve', 'action': 'hangve_full'},
    ],
    'tmall': [
        {'provider': 'hangve', 'action': 'hangve_full'},
        {'provider': 'pandamall', 'action': 'pandamall_detail'},
    ],
}

PROVIDER_TIMEOUTS_MS = {
    'gianghuy': int(os.environ.get('CRAWL_GIANGHUY_TIMEOUT_MS', '15000')),
    'pandamall': int(os.environ.get('CRAWL_PANDAMALL_TIMEOUT_MS', '20000')),
    'hangve': int(os.environ.get('CRAWL_HANGVE_TIMEOUT_MS', '25000')),
}

HANGVE_ACCOUNTS = [
    {'username': '0905687687', 'password': '687687687'},
    {'username': '0905252513', 'password': '0905252513'},
    {'username': '0909521903', 'password': '0909521903'},
    {'username': '0977685685', 'password': '0977685685'},
    {'username': '0808131313', 'password': '0808131313'},
]

PANDAMALL_ACCOUNTS = [
    {'phone': '0905687687', 'password': 'Abc@0905687687'},
    {'phone': '0905252513', 'password': 'Abc@0905252513'},
    {'phone': '0909521903', 'password': 'Abc@0909521903'},
]

HANGVE_MAX_ACCOUNT_ATTEMPTS = 3
PANDAMALL_MAX_ACCOUNT_ATTEMPTS = 3

PROVIDER_ACCOUNT_ROTATIONS = {
    'hangve': {
        'accounts': HANGVE_ACCOUNTS,
        'maxAttempts': HANGVE_MAX_ACCOUNT_ATTEMPTS,
        'payloadUserKey': 'username',
        'payloadPasswordKey': 'password',
        'accountUserKey': 'username',
        'label': 'Hangve',
    },
    'pandamall': {
        'accounts': PANDAMALL_ACCOUNTS,
        'maxAttempts': PANDAMALL_MAX_ACCOUNT_ATTEMPTS,
        'payloadUserKey': 'phone',
        'payloadPasswordKey': 'password',
        'accountUserKey': 'phone',
        'label': 'PandaMall',
    },
}


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def _normalize_string(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ''):
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    normalized = _normalize_string(value)
    if not normalized:
        return None

    normalized = normalized.replace(',', '')

    try:
        return float(normalized)
    except ValueError:
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value in (None, ''):
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    normalized = _normalize_string(value)
    if not normalized:
        return None

    normalized = normalized.replace(',', '')

    try:
        return int(float(normalized))
    except ValueError:
        return None


def _format_price_string(value: Any) -> str:
    number = _coerce_float(value)
    if number is None:
        return ''
    return f'{number:.2f}'


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []

    for value in values:
        normalized = _normalize_string(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)

    return output


def _mask_account_username(username: str) -> str:
    normalized = _normalize_string(username)

    if len(normalized) <= 4:
        return normalized

    return f'{"*" * (len(normalized) - 4)}{normalized[-4:]}'


def _select_provider_accounts(provider: str) -> List[Dict[str, str]]:
    config = PROVIDER_ACCOUNT_ROTATIONS.get(provider)
    if not config:
        return []

    account_user_key = config['accountUserKey']
    accounts = [
        dict(account)
        for account in config['accounts']
        if _normalize_string(account.get(account_user_key)) and _normalize_string(account.get('password'))
    ]
    random.shuffle(accounts)
    return accounts[:config['maxAttempts']]


def _build_bridge_exception_response(provider: str, marketplace: str, exc: Exception) -> Dict[str, Any]:
    return {
        'ok': False,
        'provider': provider,
        'marketplace': marketplace,
        'message': str(exc),
        'error': {'name': exc.__class__.__name__, 'message': str(exc)},
    }


def _extract_bridge_message(bridge_response: Dict[str, Any]) -> str:
    error = bridge_response.get('error', {})
    error_message = error.get('message') if isinstance(error, dict) else ''
    return _normalize_string(_first_non_empty(bridge_response.get('message'), error_message))


def parse_product_url(url: str) -> Dict[str, str]:
    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ''
    query = parse_qs(parsed.query)
    item_id = ''
    marketplace = ''

    if hostname.endswith('1688.com'):
        marketplace = '1688'
        match = re.search(r'/offer/(\d+)(?:\.html)?', parsed.path)
        item_id = _first_non_empty(match.group(1) if match else '', query.get('offerId', [''])[0], query.get('id', [''])[0]) or ''
    elif hostname.endswith('tmall.com'):
        marketplace = 'tmall'
        item_id = query.get('id', [''])[0]
    elif hostname.endswith('taobao.com'):
        marketplace = 'taobao'
        item_id = query.get('id', [''])[0]
    else:
        raise ValueError(f'Unsupported marketplace host: {hostname or "unknown"}')

    item_id = _normalize_string(item_id)
    if not item_id or not re.fullmatch(r'\d+', item_id):
        raise ValueError(f'Could not extract product id from URL: {url}')

    if marketplace == '1688':
        canonical_url = f'https://detail.1688.com/offer/{item_id}.html'
    elif marketplace == 'tmall':
        canonical_url = f'https://detail.tmall.com/item.htm?id={item_id}'
    else:
        canonical_url = f'https://item.taobao.com/item.htm?id={item_id}'

    return {
        'inputUrl': _normalize_string(url),
        'hostname': hostname,
        'marketplace': marketplace,
        'itemId': item_id,
        'canonicalUrl': canonical_url,
    }


def _get_crawl_new_dir() -> str:
    configured = _normalize_string(os.environ.get('CRAWL_NEW_DIR'))
    if configured:
        return configured

    base_dir = os.path.dirname(os.path.abspath(__file__))
    sibling_dir = os.path.abspath(os.path.join(base_dir, '..', 'crawl_new'))
    return sibling_dir


def _get_bridge_script_path() -> str:
    return os.path.join(_get_crawl_new_dir(), 'src', 'bridge.js')


def run_node_bridge(action: str, payload: Dict[str, Any], provider: str, marketplace: str) -> Dict[str, Any]:
    crawl_new_dir = _get_crawl_new_dir()
    bridge_script = _get_bridge_script_path()

    if not os.path.exists(bridge_script):
        raise RuntimeError(f'Node bridge script not found: {bridge_script}')

    command = ['node', bridge_script]
    input_payload = json.dumps({'action': action, 'payload': payload})
    timeout_seconds = max(PROVIDER_TIMEOUTS_MS.get(provider, 15000), 1000) / 1000

    try:
        result = subprocess.run(
            command,
            cwd=crawl_new_dir,
            input=input_payload,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            'ok': False,
            'provider': provider,
            'marketplace': marketplace,
            'message': f'Bridge timeout after {int(timeout_seconds * 1000)}ms',
            'error': {'name': exc.__class__.__name__, 'message': str(exc)},
        }

    stdout = _normalize_string(result.stdout)
    stderr = _normalize_string(result.stderr)

    if not stdout:
        return {
            'ok': False,
            'provider': provider,
            'marketplace': marketplace,
            'message': stderr or f'Bridge returned empty stdout with exit code {result.returncode}',
            'error': {'name': 'BridgeEmptyOutput', 'message': stderr or 'No output'},
        }

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            'ok': False,
            'provider': provider,
            'marketplace': marketplace,
            'message': f'Bridge returned invalid JSON: {exc}',
            'error': {'name': exc.__class__.__name__, 'message': str(exc)},
        }

    if result.returncode != 0 and parsed.get('ok') is not False:
        parsed['ok'] = False
        parsed['message'] = parsed.get('message') or stderr or f'Bridge exited with code {result.returncode}'

    return parsed


def _build_empty_canonical(context: Dict[str, str]) -> Dict[str, Any]:
    return {
        'marketplace': context['marketplace'],
        'providerUsed': '',
        'sourceId': context['itemId'],
        'inputUrl': context['inputUrl'],
        'resolvedUrl': context['canonicalUrl'],
        'name': '',
        'images': [],
        'variantGroups': [],
        'skus': [],
        'priceRanges': [],
        'maxPrice': '',
        'descriptionHtml': '',
        'seller': {},
    }


def _normalize_range_list(ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for item in ranges:
        min_quantity = _coerce_int(item.get('minQuantity'))
        max_quantity = _coerce_int(item.get('maxQuantity'))
        price = _coerce_float(item.get('price'))

        if min_quantity is None or price is None:
            continue

        normalized.append({
            'minQuantity': min_quantity,
            'maxQuantity': max_quantity,
            'price': price,
        })

    normalized.sort(key=lambda current: (current['minQuantity'], current['price']))

    for index, current in enumerate(normalized):
        if current.get('maxQuantity') is not None:
            continue

        if index + 1 < len(normalized):
            next_min = normalized[index + 1]['minQuantity']
            if next_min > current['minQuantity']:
                current['maxQuantity'] = next_min - 1

    return normalized


def _parse_pandamall_price_ranges(price_ranges: Any) -> List[Dict[str, Any]]:
    if not isinstance(price_ranges, dict):
        return []

    normalized: List[Dict[str, Any]] = []

    for raw_key, raw_value in price_ranges.items():
        key = _normalize_string(raw_key)
        price = _coerce_float(raw_value)
        if not key or price is None:
            continue

        between_match = re.fullmatch(r'(\d+)\s*-\s*(\d+)', key)
        plus_match = re.fullmatch(r'(\d+)\s*\+', key)

        if between_match:
            normalized.append({
                'minQuantity': int(between_match.group(1)),
                'maxQuantity': int(between_match.group(2)),
                'price': price,
            })
            continue

        if plus_match:
            normalized.append({
                'minQuantity': int(plus_match.group(1)),
                'maxQuantity': None,
                'price': price,
            })

    return _normalize_range_list(normalized)


def _normalize_spec_attrs(value: Any) -> str:
    text = _normalize_string(value)
    if not text:
        return ''

    parts = []
    for segment in re.split(r'[;|]+', text):
        current = _normalize_string(segment)
        if current:
            parts.append(current)

    return '|'.join(parts)


def _normalize_pandamall_spec_attrs(value: Any) -> str:
    text = _normalize_string(value)
    if not text:
        return ''

    parts = []
    for segment in text.split('@'):
        current = _normalize_string(segment)
        if not current:
            continue

        if ':' in current:
            current = current.split(':', 1)[1]

        current = _normalize_string(current)
        if current:
            parts.append(current)

    return '|'.join(parts)


def _pick_price_signal(canonical: Dict[str, Any]) -> bool:
    if _coerce_float(canonical.get('maxPrice')) is not None:
        return True

    if canonical.get('priceRanges'):
        return True

    for sku in canonical.get('skus', []):
        if _coerce_float(sku.get('price')) is not None or _coerce_float(sku.get('promotionPrice')) is not None:
            return True

    return False


def _compute_max_price(canonical: Dict[str, Any]) -> str:
    existing = _coerce_float(canonical.get('maxPrice'))
    price_candidates: List[float] = []

    if existing is not None:
        price_candidates.append(existing)

    for price_range in canonical.get('priceRanges', []):
        price = _coerce_float(price_range.get('price'))
        if price is not None:
            price_candidates.append(price)

    for sku in canonical.get('skus', []):
        for key in ('price', 'promotionPrice'):
            price = _coerce_float(sku.get(key))
            if price is not None:
                price_candidates.append(price)

    if not price_candidates:
        return ''

    return f'{max(price_candidates):.2f}'


def _is_successful_canonical(canonical: Dict[str, Any]) -> bool:
    return bool(
        _normalize_string(canonical.get('sourceId'))
        and _normalize_string(canonical.get('name'))
        and canonical.get('images')
        and _pick_price_signal(canonical)
    )


def _needs_variant_enrichment(canonical: Dict[str, Any]) -> bool:
    return not canonical.get('variantGroups') or not canonical.get('skus')


def _merge_canonical(base: Dict[str, Any], incoming: Dict[str, Any]) -> List[str]:
    updated_fields: List[str] = []

    for key in ('name', 'descriptionHtml', 'maxPrice'):
        if not _normalize_string(base.get(key)) and _normalize_string(incoming.get(key)):
            base[key] = incoming.get(key)
            updated_fields.append(key)

    for key in ('images', 'variantGroups', 'skus', 'priceRanges'):
        if not base.get(key) and incoming.get(key):
            base[key] = incoming.get(key)
            updated_fields.append(key)

    if not base.get('seller') and incoming.get('seller'):
        base['seller'] = incoming.get('seller')
        updated_fields.append('seller')

    if not _normalize_string(base.get('sourceId')) and _normalize_string(incoming.get('sourceId')):
        base['sourceId'] = incoming.get('sourceId')
        updated_fields.append('sourceId')

    if not _normalize_string(base.get('resolvedUrl')) and _normalize_string(incoming.get('resolvedUrl')):
        base['resolvedUrl'] = incoming.get('resolvedUrl')
        updated_fields.append('resolvedUrl')

    base['maxPrice'] = _compute_max_price(base)
    if 'maxPrice' not in updated_fields and _normalize_string(base.get('maxPrice')):
        updated_fields.append('maxPrice')

    return updated_fields


def _adapt_gianghuy(bridge_response: Dict[str, Any], context: Dict[str, str]) -> Dict[str, Any]:
    raw = bridge_response.get('raw') if isinstance(bridge_response.get('raw'), dict) else {}

    images = _dedupe_strings([
        media.get('link')
        for media in raw.get('medias', [])
        if isinstance(media, dict) and media.get('isVideo') is False
    ])

    variant_groups = []
    for prop in raw.get('properties', []):
        if not isinstance(prop, dict):
            continue

        prop_id = _normalize_string(prop.get('id'))
        values = []
        for item in prop.get('values', []):
            if not isinstance(item, dict):
                continue

            name = _normalize_string(_first_non_empty(item.get('nameTranslate'), item.get('name')))
            image = _normalize_string(item.get('imageUrl'))
            value_id = _normalize_string(item.get('id'))
            if not name:
                continue

            value_payload = {'name': name}
            if image:
                value_payload['image'] = image
            value_payload['sourceValueId'] = value_id
            values.append(value_payload)

        group_name = _normalize_string(_first_non_empty(prop.get('nameTranslate'), prop.get('name')))
        if group_name and values:
            variant_groups.append({
                'name': group_name,
                'sourcePropertyId': prop_id,
                'values': values,
            })

    skus = []
    for sku in raw.get('skuInfos', []):
        if not isinstance(sku, dict):
            continue

        image_urls = _normalize_string(sku.get('imageUrls')).split('|')
        skus.append({
            'skuId': _normalize_string(_first_non_empty(sku.get('id'), sku.get('skuId'))),
            'classification': _normalize_spec_attrs(_first_non_empty(sku.get('skuPropertyNameTranslate'), sku.get('skuPropertyName'))),
            'quantity': _coerce_int(_first_non_empty(sku.get('amountOnSale'), sku.get('quantity'))),
            'price': _coerce_float(sku.get('price')),
            'promotionPrice': _coerce_float(sku.get('promotionPrice')),
            'image': _normalize_string(image_urls[0] if image_urls else ''),
        })

    raw_price_ranges = []
    for price_range in raw.get('priceRanges', []):
        if not isinstance(price_range, dict):
            continue
        raw_price_ranges.append({
            'minQuantity': _coerce_int(price_range.get('startQuantity')),
            'maxQuantity': _coerce_int(price_range.get('endQuantity')),
            'price': _coerce_float(price_range.get('price')),
        })

    canonical = {
        'marketplace': context['marketplace'],
        'providerUsed': 'gianghuy',
        'sourceId': _normalize_string(_first_non_empty(context.get('itemId'), raw.get('itemId'))),
        'inputUrl': context['inputUrl'],
        'resolvedUrl': context['canonicalUrl'],
        'name': _normalize_string(_first_non_empty(raw.get('titleTranslate'), raw.get('title'), raw.get('name'))),
        'images': images,
        'variantGroups': variant_groups,
        'skus': [sku for sku in skus if sku.get('classification') or sku.get('skuId')],
        'priceRanges': _normalize_range_list(raw_price_ranges),
        'maxPrice': _format_price_string(_first_non_empty(raw.get('maxPrice'), raw.get('price'), raw.get('promotionPrice'))),
        'descriptionHtml': _normalize_string(raw.get('description')),
        'seller': {
            'name': _normalize_string(_first_non_empty(raw.get('sellerNickName'), raw.get('sellerId'))),
            'id': _normalize_string(raw.get('sellerId')),
            'url': _normalize_string(raw.get('shopUrl')),
        },
    }

    canonical['maxPrice'] = _compute_max_price(canonical)
    return canonical


def _adapt_pandamall(bridge_response: Dict[str, Any], context: Dict[str, str]) -> Dict[str, Any]:
    raw = bridge_response.get('raw') if isinstance(bridge_response.get('raw'), dict) else {}
    product = raw.get('data') if isinstance(raw.get('data'), dict) else {}
    classify = product.get('classify') if isinstance(product.get('classify'), dict) else {}
    sku_images = classify.get('skuImages') if isinstance(classify.get('skuImages'), dict) else {}

    images = []
    if product.get('image'):
        images.append(product.get('image'))

    for thumb in product.get('thumbnails', []):
        if isinstance(thumb, dict) and thumb.get('type') == 'image':
            images.append(thumb.get('src'))

    variant_groups = []
    for prop in classify.get('skuProperties', []):
        if not isinstance(prop, dict):
            continue

        prop_id = _normalize_string(prop.get('propID'))
        values = []
        for item in prop.get('propValues', []):
            if not isinstance(item, dict):
                continue

            value_name = _normalize_string(item.get('valueName'))
            value_id = _normalize_string(item.get('valueID'))
            if not value_name:
                continue

            value_payload = {
                'name': value_name,
                'sourcePropertyId': prop_id,
                'sourceValueId': value_id,
            }
            image = _normalize_string(sku_images.get(f'{prop_id}:{value_id}'))
            if image:
                value_payload['image'] = image
            values.append(value_payload)

        group_name = _normalize_string(prop.get('propName'))
        if group_name and values:
            variant_groups.append({'name': group_name, 'values': values})

    skus = []
    sku_mappings = classify.get('skuMappings') if isinstance(classify.get('skuMappings'), dict) else {}
    nested_price_ranges: List[Dict[str, Any]] = []

    for item in sku_mappings.values():
        if not isinstance(item, dict):
            continue

        if isinstance(item.get('priceRanges'), dict):
            nested_price_ranges.extend(_parse_pandamall_price_ranges(item.get('priceRanges')))

        skus.append({
            'skuId': _normalize_string(_first_non_empty(item.get('skuID'), item.get('skuId'))),
            'classification': _normalize_pandamall_spec_attrs(_first_non_empty(item.get('sName'), item.get('classification'))),
            'quantity': _coerce_int(_first_non_empty(item.get('quantity'), item.get('amountOnSale'))),
            'price': _coerce_float(item.get('price')),
            'promotionPrice': _coerce_float(item.get('promotionPrice')),
            'image': _normalize_string(item.get('imageURL')),
        })

    price_ranges = _parse_pandamall_price_ranges(product.get('priceRanges'))
    if not price_ranges and nested_price_ranges:
        price_ranges = _normalize_range_list(nested_price_ranges)

    canonical = {
        'marketplace': context['marketplace'],
        'providerUsed': 'pandamall',
        'sourceId': _normalize_string(_first_non_empty(context.get('itemId'), product.get('id'))),
        'inputUrl': context['inputUrl'],
        'resolvedUrl': context['canonicalUrl'],
        'name': _normalize_string(product.get('name')),
        'images': _dedupe_strings(images),
        'variantGroups': variant_groups,
        'skus': [sku for sku in skus if sku.get('classification') or sku.get('skuId')],
        'priceRanges': price_ranges,
        'maxPrice': _format_price_string(_first_non_empty(product.get('maxPrice'), product.get('price'), product.get('promotionPrice'))),
        'descriptionHtml': _normalize_string(product.get('description')),
        'seller': {
            'name': _normalize_string(product.get('store', {}).get('name')) if isinstance(product.get('store'), dict) else '',
            'id': _normalize_string(product.get('store', {}).get('id')) if isinstance(product.get('store'), dict) else '',
            'url': _normalize_string(product.get('store', {}).get('url')) if isinstance(product.get('store'), dict) else '',
        },
    }

    canonical['maxPrice'] = _compute_max_price(canonical)
    return canonical


def _adapt_hangve(bridge_response: Dict[str, Any], context: Dict[str, str]) -> Dict[str, Any]:
    normalized = bridge_response.get('normalized') if isinstance(bridge_response.get('normalized'), dict) else {}

    variant_groups = []
    for group in normalized.get('variantGroups', []):
        if not isinstance(group, dict):
            continue

        group_name = _normalize_string(_first_non_empty(group.get('name'), group.get('nameOriginal')))
        raw_values = group.get('values') or group.get('valuesOriginal') or group.get('valuesOriginalCn') or []
        values = [{'name': _normalize_string(value)} for value in raw_values if _normalize_string(value)]
        if group_name and values:
            variant_groups.append({'name': group_name, 'values': values})

    skus = []
    for sku in normalized.get('skus', []):
        if not isinstance(sku, dict):
            continue

        skus.append({
            'skuId': _normalize_string(sku.get('skuId')),
            'classification': _normalize_spec_attrs(_first_non_empty(sku.get('classification'), sku.get('classificationCn'))),
            'quantity': _coerce_int(sku.get('quantity')),
            'price': _coerce_float(sku.get('price')),
            'promotionPrice': _coerce_float(sku.get('promotionPrice')),
            'image': _normalize_string(sku.get('image')),
        })

    raw_price_ranges = []
    for price_range in normalized.get('priceRanges', []):
        if not isinstance(price_range, dict):
            continue

        raw_price_ranges.append({
            'minQuantity': _coerce_int(price_range.get('minQuantity')),
            'maxQuantity': _coerce_int(price_range.get('maxQuantity')),
            'price': _coerce_float(price_range.get('price')),
        })

    canonical = {
        'marketplace': context['marketplace'],
        'providerUsed': 'hangve',
        'sourceId': _normalize_string(_first_non_empty(context.get('itemId'), normalized.get('numIid'))),
        'inputUrl': context['inputUrl'],
        'resolvedUrl': context['canonicalUrl'],
        'name': _normalize_string(normalized.get('title')),
        'images': _dedupe_strings(normalized.get('images', [])),
        'variantGroups': variant_groups,
        'skus': [sku for sku in skus if sku.get('classification') or sku.get('skuId')],
        'priceRanges': _normalize_range_list(raw_price_ranges),
        'maxPrice': _format_price_string(_first_non_empty(normalized.get('price'), normalized.get('promotionPrice'))),
        'descriptionHtml': _normalize_string(normalized.get('descriptionHtml')),
        'seller': {
            'name': _normalize_string(normalized.get('sellerNick')),
            'id': '',
            'url': '',
        },
    }

    canonical['maxPrice'] = _compute_max_price(canonical)
    return canonical


ADAPTERS = {
    'gianghuy': _adapt_gianghuy,
    'pandamall': _adapt_pandamall,
    'hangve': _adapt_hangve,
}


def serialize_legacy_product(canonical: Dict[str, Any]) -> Dict[str, Any]:
    sku_property = canonical.get('variantGroups') or []
    range_prices = []

    for item in canonical.get('priceRanges', []):
        price = _coerce_float(item.get('price'))
        if price is None:
            continue

        range_prices.append({
            'beginAmount': _coerce_int(item.get('minQuantity')) or 1,
            'endAmount': _coerce_int(item.get('maxQuantity')) or 999999,
            'price': price,
            'discountPrice': price,
        })

    sku_list = []
    for sku in canonical.get('skus', []):
        sku_payload = {
            'canBookCount': _normalize_string(sku.get('quantity')),
            'price': _format_price_string(_first_non_empty(sku.get('promotionPrice'), sku.get('price'))),
            'specAttrs': _normalize_spec_attrs(sku.get('classification')),
        }
        sku_id = _normalize_string(sku.get('skuId'))
        if sku_id:
            sku_payload['skuId'] = sku_id
        sku_list.append(sku_payload)

    return {
        'images': canonical.get('images', []),
        'skuProperty': sku_property,
        'properties': sku_property,
        'sku': sku_list,
        'rangePrices': range_prices,
        'maxPrice': canonical.get('maxPrice') or '',
        'name': canonical.get('name') or '',
        'sourceId': canonical.get('sourceId') or '',
        'sourceType': canonical.get('marketplace') or '',
        'url': canonical.get('resolvedUrl') or '',
    }


def _build_provider_payload(
    provider: str,
    context: Dict[str, str],
    account: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    payload = {
        'marketplace': context['marketplace'],
        'url': context['canonicalUrl'],
        'itemId': context['itemId'],
    }

    if provider == 'pandamall':
        payload['provider'] = 'alibaba' if context['marketplace'] == '1688' else 'taobao'

    account_config = PROVIDER_ACCOUNT_ROTATIONS.get(provider)
    if account_config and account:
        payload[account_config['payloadUserKey']] = _normalize_string(account.get(account_config['accountUserKey']))
        payload[account_config['payloadPasswordKey']] = _normalize_string(account.get('password'))

    return payload


def _run_provider_request(
    runner: Callable[[str, Dict[str, Any], str, str], Dict[str, Any]],
    provider: str,
    action: str,
    context: Dict[str, str],
) -> Dict[str, Any]:
    account_config = PROVIDER_ACCOUNT_ROTATIONS.get(provider)
    if not account_config:
        payload = _build_provider_payload(provider, context)
        try:
            return runner(action, payload, provider, context['marketplace'])
        except Exception as exc:
            return _build_bridge_exception_response(provider, context['marketplace'], exc)

    selected_accounts = _select_provider_accounts(provider)
    account_attempts: List[Dict[str, Any]] = []
    last_response: Dict[str, Any] = {
        'ok': False,
        'provider': provider,
        'marketplace': context['marketplace'],
        'message': f"{account_config['label']} account rotation exhausted",
    }

    for index, account in enumerate(selected_accounts, start=1):
        payload = _build_provider_payload(provider, context, account=account)
        masked_username = _mask_account_username(account.get(account_config['accountUserKey'], ''))

        try:
            response = runner(action, payload, provider, context['marketplace'])
        except Exception as exc:
            response = _build_bridge_exception_response(provider, context['marketplace'], exc)

        message = _extract_bridge_message(response)
        success = bool(response.get('ok'))
        account_attempts.append({
            'attempt': index,
            'usernameMasked': masked_username,
            'success': success,
            'message': message,
        })

        if success:
            enriched_response = dict(response)
            enriched_response['accountAttempts'] = account_attempts
            if not message:
                enriched_response['message'] = f"{account_config['label']} account {masked_username} succeeded on attempt {index}"
            return enriched_response

        last_response = response

    failure_response = dict(last_response)
    failure_response['accountAttempts'] = account_attempts

    failure_messages = [
        f"{attempt['usernameMasked']}: {attempt['message'] or 'request failed'}"
        for attempt in account_attempts
    ]
    failure_response['message'] = (
        '; '.join(failure_messages)
        or _extract_bridge_message(failure_response)
        or f"{account_config['label']} account rotation exhausted"
    )
    return failure_response


def _build_debug_meta(context: Dict[str, str], attempts: List[Dict[str, Any]], started_at: float, provider_used: str) -> Dict[str, Any]:
    failure_reasons = [attempt['message'] for attempt in attempts if not attempt.get('success') and attempt.get('message')]

    return {
        'marketplace': context['marketplace'],
        'providerUsed': provider_used,
        'attempts': attempts,
        'fallbackTriggered': len(attempts) > 1,
        'failureReasons': failure_reasons,
        'latencyMs': int((time.time() - started_at) * 1000),
    }


def transform_product_from_url(
    url: str,
    debug: bool = False,
    bridge_runner: Optional[Callable[[str, Dict[str, Any], str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    context = parse_product_url(url)
    runner = bridge_runner or run_node_bridge
    canonical = _build_empty_canonical(context)
    attempts: List[Dict[str, Any]] = []
    started_at = time.time()

    for chain_item in PROVIDER_CHAINS[context['marketplace']]:
        provider = chain_item['provider']
        action = chain_item['action']
        attempt_started_at = time.time()

        bridge_response = _run_provider_request(runner, provider, action, context)

        success = bool(bridge_response.get('ok'))
        message = _extract_bridge_message(bridge_response)
        updated_fields: List[str] = []

        if success:
            adapter = ADAPTERS[provider]
            incoming = adapter(bridge_response, context)
            updated_fields = _merge_canonical(canonical, incoming)

            if not canonical.get('providerUsed') and _is_successful_canonical(canonical):
                canonical['providerUsed'] = provider
        else:
            logger.warning('Provider %s failed for %s: %s', provider, context['canonicalUrl'], message)

        attempt_entry = {
            'provider': provider,
            'action': action,
            'success': success,
            'message': message,
            'updatedFields': updated_fields,
            'durationMs': int((time.time() - attempt_started_at) * 1000),
        }
        if provider in PROVIDER_ACCOUNT_ROTATIONS and isinstance(bridge_response.get('accountAttempts'), list):
            attempt_entry['accountAttempts'] = bridge_response['accountAttempts']
        attempts.append(attempt_entry)

        if _is_successful_canonical(canonical) and not _needs_variant_enrichment(canonical):
            break

    if not _is_successful_canonical(canonical):
        response = {
            'error': 'Could not fetch product data from any provider',
        }
        if debug:
            response['_meta'] = _build_debug_meta(context, attempts, started_at, canonical.get('providerUsed', ''))
        return response

    response = serialize_legacy_product(canonical)
    if debug:
        response['_meta'] = _build_debug_meta(context, attempts, started_at, canonical.get('providerUsed', ''))
    return response
