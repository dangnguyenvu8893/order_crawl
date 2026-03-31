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


def _resolve_crawl_new_dir() -> str:
    configured = str(os.environ.get('CRAWL_NEW_DIR') or '').strip()
    if configured:
        return configured

    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_dir = os.path.join(base_dir, 'crawl_new')
    if os.path.isdir(local_dir):
        return local_dir

    return os.path.abspath(os.path.join(base_dir, '..', 'crawl_new'))


def _resolve_crawl_new_config_path(filename: str) -> str:
    return os.path.join(_resolve_crawl_new_dir(), 'config', filename)


def _load_optional_json(path: str) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return None


def _normalize_account_entries(raw_accounts: Any, user_key: str) -> List[Dict[str, str]]:
    if isinstance(raw_accounts, dict):
        raw_accounts = raw_accounts.get('accounts')

    if not isinstance(raw_accounts, list):
        return []

    normalized_accounts: List[Dict[str, str]] = []
    for account in raw_accounts:
        if not isinstance(account, dict):
            continue

        username = str(account.get(user_key) or '').strip()
        password = str(account.get('password') or '').strip()
        if not username or not password:
            continue

        normalized_accounts.append({
            user_key: username,
            'password': password,
        })

    return normalized_accounts


def _load_provider_accounts(filename: str, user_key: str, fallback_accounts: List[Dict[str, str]]) -> List[Dict[str, str]]:
    configured_accounts = _normalize_account_entries(
        _load_optional_json(_resolve_crawl_new_config_path(filename)),
        user_key,
    )
    if configured_accounts:
        return configured_accounts

    return _normalize_account_entries(fallback_accounts, user_key)

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

_DEFAULT_HANGVE_ACCOUNTS = [
    {'username': '0905687687', 'password': '687687687'},
    {'username': '0905252513', 'password': '0905252513'},
    {'username': '0909521903', 'password': '0909521903'},
    {'username': '0977685685', 'password': '0977685685'},
    {'username': '0808131313', 'password': '0808131313'},
]

_DEFAULT_PANDAMALL_ACCOUNTS = [
    {'phone': '0905687687', 'password': 'Abc@0905687687'},
    {'phone': '0905252513', 'password': 'Abc@0905252513'},
    {'phone': '0909521903', 'password': 'Abc@0909521903'},
]

HANGVE_ACCOUNTS = _load_provider_accounts(
    'hangve.accounts.json',
    'username',
    _DEFAULT_HANGVE_ACCOUNTS,
)

PANDAMALL_ACCOUNTS = _load_provider_accounts(
    'pandamall.accounts.json',
    'phone',
    _DEFAULT_PANDAMALL_ACCOUNTS,
)

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


def _normalize_numeric_identifier(value: Any) -> Optional[str]:
    normalized = _normalize_string(value)
    if not normalized or not re.fullmatch(r'\d+', normalized):
        return None
    return normalized


def _normalize_source_identifier_for_marketplace(value: Any, marketplace: str) -> Optional[str]:
    normalized = _normalize_string(value)
    if not normalized:
        return None

    if marketplace == '1688':
        return _normalize_numeric_identifier(normalized)

    return normalized


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
    return _resolve_crawl_new_dir()


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


def _serialize_spec_attrs_for_backend(value: Any) -> str:
    normalized = _normalize_spec_attrs(value)
    if not normalized:
        return ''

    parts = []
    for segment in normalized.split('|'):
        current = _normalize_string(segment)
        if not current:
            continue

        if '--' in current:
            current = _normalize_string(current.split('--', 1)[1])

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


def _build_gianghuy_spec_attrs(value: Any, prop_names: List[str]) -> str:
    text = _normalize_string(value)
    if not text:
        return ''

    value_parts = [segment.strip() for segment in text.split(';') if segment.strip()]
    if prop_names and len(prop_names) == len(value_parts):
        return '|'.join(f'{prop}--{segment}' for prop, segment in zip(prop_names, value_parts))

    return '|'.join(value_parts)


def _get_nested_value(data: Any, path: str) -> Any:
    current = data
    for segment in path.split('.'):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
            continue
        return None
    return current


def _extract_pandamall_images(product: Dict[str, Any]) -> List[str]:
    images: List[str] = []

    for thumb in product.get('thumbnails', []):
        if isinstance(thumb, dict):
            src = _normalize_string(thumb.get('src'))
            if src:
                images.append(src)
        elif isinstance(thumb, str):
            src = _normalize_string(thumb)
            if src:
                images.append(src)

    if not images:
        for path in ('images', 'imageList', 'gallery', 'photos', 'imgs', 'data.images', 'item.images', 'product.images'):
            images_data = _get_nested_value(product, path)
            if not isinstance(images_data, list) or not images_data:
                continue

            for item in images_data:
                if isinstance(item, dict):
                    for key in ('url', 'imageUrl', 'src', 'image'):
                        candidate = _normalize_string(item.get(key))
                        if candidate:
                            images.append(candidate)
                            break
                elif isinstance(item, str):
                    candidate = _normalize_string(item)
                    if candidate:
                        images.append(candidate)

            if images:
                break

    main_image = _normalize_string(_first_non_empty(product.get('image'), _get_nested_value(product, 'data.image')))
    if main_image:
        images.insert(0, main_image)

    return _dedupe_strings(images)


def _extract_pandamall_name(product: Dict[str, Any]) -> str:
    for path in ('name', 'title', 'productName', 'itemName', 'data.title', 'data.name', 'item.title', 'item.name'):
        candidate = _normalize_string(_get_nested_value(product, path) if '.' in path else product.get(path))
        if candidate:
            return candidate
    return ''


def _build_pandamall_value_name_map(classify: Dict[str, Any]) -> Dict[str, str]:
    value_name_map: Dict[str, str] = {}

    for prop in classify.get('skuProperties', []):
        if not isinstance(prop, dict):
            continue

        prop_id = _normalize_string(_first_non_empty(prop.get('propID'), prop.get('propId')))
        if not prop_id:
            continue

        for value in prop.get('propValues', []) or prop.get('values', []):
            if not isinstance(value, dict):
                continue

            value_id = _normalize_string(_first_non_empty(value.get('valueID'), value.get('valueId')))
            value_name = _normalize_string(_first_non_empty(value.get('valueName'), value.get('name')))
            if prop_id and value_id and value_name:
                value_name_map[f'{prop_id}:{value_id}'] = value_name

    return value_name_map


def _build_pandamall_spec_attrs(raw_value: Any, mapping_key: str, value_name_map: Dict[str, str]) -> str:
    preferred = _normalize_pandamall_spec_attrs(raw_value)
    if preferred:
        return preferred

    parts: List[str] = []
    for segment in mapping_key.split('@'):
        normalized_segment = _normalize_string(segment)
        if not normalized_segment:
            continue
        parts.append(_normalize_string(value_name_map.get(normalized_segment) or normalized_segment))

    return '|'.join(part for part in parts if part)


def _extract_pandamall_range_prices(product: Dict[str, Any], sku_mappings: Dict[str, Any]) -> List[Dict[str, Any]]:
    price_ranges = _parse_pandamall_price_ranges(product.get('priceRanges'))
    if price_ranges:
        return price_ranges

    nested_price_ranges: List[Dict[str, Any]] = []
    prices: List[float] = []

    for sku_value in sku_mappings.values():
        if not isinstance(sku_value, dict):
            continue

        if isinstance(sku_value.get('priceRanges'), dict):
            nested_price_ranges.extend(_parse_pandamall_price_ranges(sku_value.get('priceRanges')))

        price = _coerce_float(_first_non_empty(sku_value.get('promotionPrice'), sku_value.get('price')))
        if price is not None and price > 0:
            prices.append(price)

    if nested_price_ranges:
        return _normalize_range_list(nested_price_ranges)

    if prices:
        min_price = min(prices)
        return [{
            'minQuantity': 1,
            'maxQuantity': 999999,
            'price': min_price,
        }]

    fallback_price = _coerce_float(_first_non_empty(
        product.get('price'),
        product.get('minPrice'),
        product.get('startPrice'),
        _get_nested_value(product, 'data.price'),
    ))
    if fallback_price is None or fallback_price <= 0:
        return []

    return [{
        'minQuantity': 1,
        'maxQuantity': 999999,
        'price': fallback_price,
    }]


def _merge_images(base: List[str], incoming: List[str]) -> bool:
    merged = _dedupe_strings((base or []) + (incoming or []))
    if merged == (base or []):
        return False
    base[:] = merged
    return True


def _merge_variant_groups(base: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> bool:
    if not incoming:
        return False

    if not base:
        base.extend(incoming)
        return True

    changed = False
    group_index = {
        _normalize_string(group.get('name')).lower(): group
        for group in base
        if isinstance(group, dict) and _normalize_string(group.get('name'))
    }

    for incoming_group in incoming:
        if not isinstance(incoming_group, dict):
            continue

        group_key = _normalize_string(incoming_group.get('name')).lower()
        if not group_key:
            continue

        existing_group = group_index.get(group_key)
        if not existing_group:
            base.append(incoming_group)
            group_index[group_key] = incoming_group
            changed = True
            continue

        if not _normalize_string(existing_group.get('sourcePropertyId')) and _normalize_string(incoming_group.get('sourcePropertyId')):
            existing_group['sourcePropertyId'] = incoming_group.get('sourcePropertyId')
            changed = True

        existing_values = existing_group.get('values') or []
        value_index = {
            _normalize_string(value.get('name')).lower(): value
            for value in existing_values
            if isinstance(value, dict) and _normalize_string(value.get('name'))
        }

        for incoming_value in incoming_group.get('values', []):
            if not isinstance(incoming_value, dict):
                continue

            value_key = _normalize_string(incoming_value.get('name')).lower()
            if not value_key:
                continue

            existing_value = value_index.get(value_key)
            if not existing_value:
                existing_values.append(incoming_value)
                value_index[value_key] = incoming_value
                changed = True
                continue

            for field in ('image', 'sourcePropertyId', 'sourceValueId'):
                if not _normalize_string(existing_value.get(field)) and _normalize_string(incoming_value.get(field)):
                    existing_value[field] = incoming_value.get(field)
                    changed = True

        existing_group['values'] = existing_values

    return changed


def _merge_skus(base: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> bool:
    if not incoming:
        return False

    if not base:
        base.extend(incoming)
        return True

    changed = False
    sku_index: Dict[str, Dict[str, Any]] = {}
    for sku in base:
        if not isinstance(sku, dict):
            continue
        key = _normalize_string(_first_non_empty(sku.get('skuId'), sku.get('classification'))).lower()
        if key:
            sku_index[key] = sku

    for incoming_sku in incoming:
        if not isinstance(incoming_sku, dict):
            continue

        key = _normalize_string(_first_non_empty(incoming_sku.get('skuId'), incoming_sku.get('classification'))).lower()
        if not key:
            continue

        existing_sku = sku_index.get(key)
        if not existing_sku:
            base.append(incoming_sku)
            sku_index[key] = incoming_sku
            changed = True
            continue

        for field in ('skuId', 'quantity', 'price', 'promotionPrice', 'image'):
            if existing_sku.get(field) in (None, '') and incoming_sku.get(field) not in (None, ''):
                existing_sku[field] = incoming_sku.get(field)
                changed = True

        existing_classification = _normalize_string(existing_sku.get('classification'))
        incoming_classification = _normalize_string(incoming_sku.get('classification'))
        if (
            incoming_classification
            and (
                not existing_classification
                or ('--' in incoming_classification and '--' not in existing_classification)
            )
        ):
            existing_sku['classification'] = incoming_sku.get('classification')
            changed = True

    return changed


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

    if _merge_images(base.setdefault('images', []), incoming.get('images') or []):
        updated_fields.append('images')

    if _merge_variant_groups(base.setdefault('variantGroups', []), incoming.get('variantGroups') or []):
        updated_fields.append('variantGroups')

    if _merge_skus(base.setdefault('skus', []), incoming.get('skus') or []):
        updated_fields.append('skus')

    incoming_price_ranges = incoming.get('priceRanges') or []
    if incoming_price_ranges and (
        not base.get('priceRanges')
        or len(incoming_price_ranges) > len(base.get('priceRanges') or [])
    ):
        base['priceRanges'] = incoming_price_ranges
        updated_fields.append('priceRanges')

    if incoming.get('seller'):
        seller = base.setdefault('seller', {})
        seller_changed = False
        for field in ('name', 'id', 'url'):
            if not _normalize_string(seller.get(field)) and _normalize_string(incoming.get('seller', {}).get(field)):
                seller[field] = incoming['seller'].get(field)
                seller_changed = True
        if seller_changed:
            base['seller'] = seller
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

        prop_id = _normalize_source_identifier_for_marketplace(prop.get('id'), context['marketplace'])
        values = []
        for item in prop.get('values', []):
            if not isinstance(item, dict):
                continue

            name = _normalize_string(item.get('name'))
            image = _normalize_string(item.get('imageUrl'))
            value_id = _normalize_source_identifier_for_marketplace(item.get('id'), context['marketplace'])
            if not name:
                continue

            value_payload = {'name': name}
            if image:
                value_payload['image'] = image
            value_payload['sourceValueId'] = value_id
            values.append(value_payload)

        group_name = _normalize_string(prop.get('name'))
        if group_name and values:
            variant_groups.append({
                'name': group_name,
                'sourcePropertyId': prop_id,
                'values': values,
            })

    skus = []
    prop_names = [
        _normalize_string(prop.get('name'))
        for prop in raw.get('properties', [])
        if isinstance(prop, dict) and _normalize_string(prop.get('name'))
    ]
    for sku in raw.get('skuInfos', []):
        if not isinstance(sku, dict):
            continue

        image_urls = _normalize_string(sku.get('imageUrls')).split('|')
        skus.append({
            'skuId': _normalize_string(_first_non_empty(sku.get('id'), sku.get('skuId'))),
            'classification': _build_gianghuy_spec_attrs(sku.get('skuPropertyName'), prop_names),
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
        'name': _normalize_string(_first_non_empty(raw.get('title'), raw.get('name'), raw.get('titleTranslate'))),
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
    value_name_map = _build_pandamall_value_name_map(classify)
    images = _extract_pandamall_images(product)

    variant_groups = []
    for prop in classify.get('skuProperties', []):
        if not isinstance(prop, dict):
            continue

        raw_prop_id = _normalize_string(prop.get('propID'))
        prop_id = _normalize_numeric_identifier(prop.get('propID'))
        values = []
        for item in prop.get('propValues', []):
            if not isinstance(item, dict):
                continue

            value_name = _normalize_string(item.get('valueName'))
            raw_value_id = _normalize_string(item.get('valueID'))
            value_id = _normalize_numeric_identifier(item.get('valueID'))
            if not value_name:
                continue

            value_payload = {
                'name': value_name,
                'sourcePropertyId': prop_id,
                'sourceValueId': value_id,
            }
            image = _normalize_string(sku_images.get(f'{raw_prop_id}:{raw_value_id}'))
            if image:
                value_payload['image'] = image
            values.append(value_payload)

        group_name = _normalize_string(prop.get('propName'))
        if group_name and values:
            variant_groups.append({
                'name': group_name,
                'sourcePropertyId': prop_id,
                'values': values,
            })

    skus = []
    sku_mappings = classify.get('skuMappings') if isinstance(classify.get('skuMappings'), dict) else {}
    for mapping_key, item in sku_mappings.items():
        if not isinstance(item, dict):
            continue

        image = _normalize_string(item.get('imageURL'))
        if not image:
            for segment in mapping_key.split('@'):
                candidate = _normalize_string(sku_images.get(_normalize_string(segment)))
                if candidate:
                    image = candidate
                    break
        skus.append({
            'skuId': _normalize_string(_first_non_empty(item.get('skuID'), item.get('skuId'))),
            'classification': _build_pandamall_spec_attrs(
                _first_non_empty(item.get('sName'), item.get('classification')),
                mapping_key,
                value_name_map,
            ),
            'quantity': _coerce_int(_first_non_empty(item.get('quantity'), item.get('amountOnSale'))),
            'price': _coerce_float(item.get('price')),
            'promotionPrice': _coerce_float(item.get('promotionPrice')),
            'image': image,
        })

    price_ranges = _extract_pandamall_range_prices(product, sku_mappings)

    canonical = {
        'marketplace': context['marketplace'],
        'providerUsed': 'pandamall',
        'sourceId': _normalize_string(_first_non_empty(context.get('itemId'), product.get('id'))),
        'inputUrl': context['inputUrl'],
        'resolvedUrl': context['canonicalUrl'],
        'name': _extract_pandamall_name(product),
        'images': images,
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

        group_name = _normalize_string(_first_non_empty(group.get('nameOriginal'), group.get('name')))
        values = []

        for entry in group.get('valueEntries', []):
            if not isinstance(entry, dict):
                continue

            value_name = _normalize_string(_first_non_empty(entry.get('nameOriginalCn'), entry.get('nameOriginal'), entry.get('name')))
            if not value_name:
                continue

            value_payload = {
                'name': value_name,
                'sourcePropertyId': _normalize_string(_first_non_empty(entry.get('sourcePropertyId'), group.get('sourcePropertyId'))) or None,
                'sourceValueId': _normalize_string(entry.get('sourceValueId')) or None,
            }
            image = _normalize_string(entry.get('image'))
            if image:
                value_payload['image'] = image
            values.append(value_payload)

        if not values:
            raw_values = group.get('values') or group.get('valuesOriginal') or group.get('valuesOriginalCn') or []
            values = [{'name': _normalize_string(value)} for value in raw_values if _normalize_string(value)]

        if group_name and values:
            group_payload = {'name': group_name, 'values': values}
            source_property_id = _normalize_string(group.get('sourcePropertyId'))
            if source_property_id:
                group_payload['sourcePropertyId'] = source_property_id
            variant_groups.append(group_payload)

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
            'specAttrs': _serialize_spec_attrs_for_backend(sku.get('classification')),
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
        'itemId': context['itemId'],
        'productUrl': context['canonicalUrl'],
    }

    # GiangHuy dùng field config.url để ký sign với host nhaphang.gianghuy.com.
    # Không được override bằng canonical product URL của marketplace.
    if provider != 'gianghuy':
        payload['url'] = context['canonicalUrl']

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
