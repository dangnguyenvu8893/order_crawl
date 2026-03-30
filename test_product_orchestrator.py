import unittest
from unittest.mock import patch

from product_orchestrator import (
    HANGVE_ACCOUNTS,
    PANDAMALL_ACCOUNTS,
    _adapt_gianghuy,
    _adapt_hangve,
    _adapt_pandamall,
    parse_product_url,
    transform_product_from_url,
)


GIANGHUY_1688_BRIDGE = {
    'ok': True,
    'provider': 'gianghuy',
    'marketplace': '1688',
    'raw': {
        'itemId': 892407994374,
        'title': 'GiangHuy 1688 title',
        'description': '<p>gianghuy</p>',
        'maxPrice': 47.98,
        'medias': [
            {'link': 'https://img-1.jpg', 'isVideo': False},
            {'link': 'https://img-2.jpg', 'isVideo': False},
        ],
        'properties': [
            {
                'name': 'Color',
                'values': [{'name': 'Beige', 'imageUrl': 'https://img-1.jpg'}],
            }
        ],
        'skuInfos': [
            {
                'id': 'sku-1688-1',
                'skuPropertyName': 'Beige;S;',
                'price': 47.98,
                'promotionPrice': 47.98,
                'amountOnSale': 30,
                'imageUrls': 'https://img-1.jpg|',
            }
        ],
        'priceRanges': [
            {'startQuantity': 2, 'price': 47.98},
            {'startQuantity': 500, 'price': 46.68},
        ],
        'sellerNickName': 'Shop 1688',
        'sellerId': 'shop-1688',
        'shopUrl': 'https://shop-1688.example.com',
    },
}

PANDAMALL_TAOBAO_BRIDGE = {
    'ok': True,
    'provider': 'pandamall',
    'marketplace': 'taobao',
    'raw': {
        'status': True,
        'message': 'ok',
        'data': {
            'id': 1016154115457,
            'name': 'Pandamall Taobao title',
            'description': '<p>pandamall</p>',
            'image': 'https://pm-main.jpg',
            'thumbnails': [
                {'type': 'image', 'src': 'https://pm-thumb-1.jpg'},
                {'type': 'image', 'src': 'https://pm-thumb-2.jpg'},
            ],
            'price': 151.52,
            'promotionPrice': 143.95,
            'maxPrice': 151.52,
            'url': 'https://item.taobao.com/item.htm?id=1016154115457',
            'store': {
                'id': 'store-taobao',
                'name': 'Ranwear official',
                'url': 'https://shop497891188.taobao.com',
            },
            'classify': {
                'skuImages': {
                    '1627207:380848629': 'https://pm-color.jpg',
                },
                'skuProperties': [
                    {
                        'propID': 1627207,
                        'propName': 'Phân loại màu sắc',
                        'propValues': [
                            {'valueID': 380848629, 'valueName': 'Milkshake White - Còn hàng'}
                        ],
                    },
                    {
                        'propID': 20509,
                        'propName': 'kích cỡ',
                        'propValues': [
                            {'valueID': 28314, 'valueName': 'S'},
                            {'valueID': 28315, 'valueName': 'M'},
                        ],
                    },
                ],
                'skuMappings': {
                    '1627207:380848629@20509:28314': {
                        'skuID': '6025255024005',
                        'sName': '1627207:Milkshake White - Còn hàng@20509:S',
                        'price': 151.52,
                        'promotionPrice': 143.95,
                        'quantity': 129,
                        'imageURL': 'https://pm-color.jpg',
                    }
                },
            },
            'priceRanges': {
                '1-9': 151.52,
                '10+': 143.95,
            },
        },
    },
}

HANGVE_TMALL_BRIDGE = {
    'ok': True,
    'provider': 'hangve',
    'marketplace': 'tmall',
    'normalized': {
        'source': 'taobao',
        'itemId': 2508970,
        'numIid': '1013307248141',
        'title': 'Hangve Tmall title',
        'sellerNick': 'Hangve seller',
        'detailUrl': 'https://item.taobao.com/item.htm?id=1013307248141',
        'price': 118.6,
        'promotionPrice': 118.6,
        'images': [
            'https://hv-main.jpg',
            'https://hv-2.jpg',
        ],
        'variantGroups': [
            {
                'name': 'Color',
                'values': ['Red'],
            },
            {
                'name': 'Size',
                'values': ['S', 'M'],
            },
        ],
        'skus': [
            {
                'skuId': '6179390398393',
                'classification': 'Red;S',
                'price': 118.6,
                'promotionPrice': 118.6,
                'quantity': 5,
                'image': 'https://hv-main.jpg',
            }
        ],
        'priceRanges': [],
        'descriptionHtml': '<p>hangve</p>',
    },
}


class ProductOrchestratorTests(unittest.TestCase):
    def test_parse_product_url_canonicalizes_marketplace_urls(self):
        tmall = parse_product_url('https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393')
        taobao = parse_product_url('https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005')
        offer1688 = parse_product_url('https://detail.1688.com/offer/892407994374.html?offerId=892407994374')

        self.assertEqual(tmall['canonicalUrl'], 'https://detail.tmall.com/item.htm?id=1013307248141')
        self.assertEqual(taobao['canonicalUrl'], 'https://item.taobao.com/item.htm?id=1016154115457')
        self.assertEqual(offer1688['canonicalUrl'], 'https://detail.1688.com/offer/892407994374.html')

    def test_adapt_gianghuy_maps_legacy_shape_inputs(self):
        context = parse_product_url('https://detail.1688.com/offer/892407994374.html?offerId=892407994374')
        canonical = _adapt_gianghuy(GIANGHUY_1688_BRIDGE, context)

        self.assertEqual(canonical['sourceId'], '892407994374')
        self.assertEqual(canonical['name'], 'GiangHuy 1688 title')
        self.assertEqual(len(canonical['images']), 2)
        self.assertEqual(len(canonical['variantGroups']), 1)
        self.assertEqual(len(canonical['skus']), 1)
        self.assertEqual(len(canonical['priceRanges']), 2)

    def test_adapt_pandamall_parses_price_ranges_and_specs(self):
        context = parse_product_url('https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005')
        canonical = _adapt_pandamall(PANDAMALL_TAOBAO_BRIDGE, context)

        self.assertEqual(canonical['sourceId'], '1016154115457')
        self.assertEqual(canonical['name'], 'Pandamall Taobao title')
        self.assertEqual(len(canonical['images']), 3)
        self.assertEqual(len(canonical['variantGroups']), 2)
        self.assertEqual(canonical['skus'][0]['classification'], 'Milkshake White - Còn hàng|S')
        self.assertEqual(len(canonical['priceRanges']), 2)

    def test_adapt_hangve_preserves_input_marketplace_identity(self):
        context = parse_product_url('https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393')
        canonical = _adapt_hangve(HANGVE_TMALL_BRIDGE, context)

        self.assertEqual(canonical['marketplace'], 'tmall')
        self.assertEqual(canonical['sourceId'], '1013307248141')
        self.assertEqual(canonical['resolvedUrl'], 'https://detail.tmall.com/item.htm?id=1013307248141')
        self.assertEqual(len(canonical['skus']), 1)

    def test_orchestrator_falls_back_after_provider_failure(self):
        calls = []

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider == 'gianghuy':
                return {
                    'ok': False,
                    'provider': 'gianghuy',
                    'marketplace': marketplace,
                    'message': 'first provider failed',
                }
            return PANDAMALL_TAOBAO_BRIDGE

        result = transform_product_from_url(
            'https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005',
            debug=True,
            bridge_runner=fake_runner,
        )

        self.assertEqual(result['sourceType'], 'taobao')
        self.assertEqual(result['sourceId'], '1016154115457')
        self.assertEqual(result['_meta']['providerUsed'], 'pandamall')
        self.assertEqual(calls[:2], ['gianghuy', 'pandamall'])

    def test_orchestrator_enriches_missing_sku_data_from_next_provider(self):
        calls = []
        partial_gianghuy = {
            **GIANGHUY_1688_BRIDGE,
            'raw': {
                **GIANGHUY_1688_BRIDGE['raw'],
                'properties': [],
                'skuInfos': [],
            },
        }

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider == 'gianghuy':
                return partial_gianghuy
            if provider == 'pandamall':
                return {
                    'ok': True,
                    'provider': 'pandamall',
                    'marketplace': marketplace,
                    'raw': {
                        'status': True,
                        'message': 'ok',
                        'data': {
                            'id': 892407994374,
                            'name': 'Pandamall 1688 title',
                            'image': 'https://pm-1688.jpg',
                            'price': 47.98,
                            'maxPrice': 47.98,
                            'classify': {
                                'skuImages': {},
                                'skuProperties': [
                                    {
                                        'propID': 450,
                                        'propName': 'Size',
                                        'propValues': [{'valueID': 'S', 'valueName': 'S'}],
                                    }
                                ],
                                'skuMappings': {
                                    '450:S': {
                                        'skuID': 'sku-pm-1',
                                        'sName': '450:S',
                                        'price': 47.98,
                                        'quantity': 99,
                                    }
                                },
                            },
                            'priceRanges': {'2-9': 47.98},
                        },
                    },
                }
            return {'ok': False, 'provider': provider, 'marketplace': marketplace, 'message': 'should not reach'}

        result = transform_product_from_url(
            'https://detail.1688.com/offer/892407994374.html?offerId=892407994374',
            debug=True,
            bridge_runner=fake_runner,
        )

        self.assertEqual(result['sourceType'], '1688')
        self.assertEqual(result['sourceId'], '892407994374')
        self.assertEqual(result['_meta']['providerUsed'], 'gianghuy')
        self.assertTrue(result['properties'])
        self.assertTrue(result['sku'])
        self.assertEqual(calls[:2], ['gianghuy', 'pandamall'])

    def test_orchestrator_uses_hangve_first_for_tmall_and_keeps_source_type(self):
        calls = []

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider != 'hangve':
                self.fail('tmall chain should stop after hangve when data is complete')
            return HANGVE_TMALL_BRIDGE

        result = transform_product_from_url(
            'https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393',
            debug=True,
            bridge_runner=fake_runner,
        )

        self.assertEqual(result['sourceType'], 'tmall')
        self.assertEqual(result['sourceId'], '1013307248141')
        self.assertEqual(result['url'], 'https://detail.tmall.com/item.htm?id=1013307248141')
        self.assertEqual(result['_meta']['providerUsed'], 'hangve')
        self.assertEqual(calls, ['hangve'])

    def test_hangve_account_rotation_retries_next_account_before_success(self):
        used_accounts = []

        def fake_runner(action, payload, provider, marketplace):
            if provider != 'hangve':
                self.fail('tmall chain should stop after hangve account success')

            used_accounts.append(payload.get('username'))
            if payload.get('username') != HANGVE_ACCOUNTS[1]['username']:
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': 'account died',
                }

            return HANGVE_TMALL_BRIDGE

        with patch('product_orchestrator.random.shuffle', lambda values: None):
            result = transform_product_from_url(
                'https://detail.tmall.com/item.htm?id=1013307248141',
                debug=True,
                bridge_runner=fake_runner,
            )

        self.assertEqual(
            used_accounts,
            [HANGVE_ACCOUNTS[0]['username'], HANGVE_ACCOUNTS[1]['username']],
        )
        self.assertEqual(result['_meta']['providerUsed'], 'hangve')
        self.assertEqual(result['_meta']['attempts'][0]['accountAttempts'][0]['success'], False)
        self.assertEqual(result['_meta']['attempts'][0]['accountAttempts'][1]['success'], True)

    def test_hangve_account_rotation_caps_at_three_before_fallback(self):
        hangve_accounts = []
        calls = []

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider == 'hangve':
                hangve_accounts.append(payload.get('username'))
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': f"failed {payload.get('username')}",
                }

            if provider == 'pandamall':
                return PANDAMALL_TAOBAO_BRIDGE

            self.fail(f'unexpected provider {provider}')

        with patch('product_orchestrator.random.shuffle', lambda values: None):
            result = transform_product_from_url(
                'https://detail.tmall.com/item.htm?id=1013307248141',
                debug=True,
                bridge_runner=fake_runner,
            )

        self.assertEqual(len(hangve_accounts), 3)
        self.assertEqual(hangve_accounts, [account['username'] for account in HANGVE_ACCOUNTS[:3]])
        self.assertEqual(calls[:4], ['hangve', 'hangve', 'hangve', 'pandamall'])
        self.assertEqual(result['_meta']['providerUsed'], 'pandamall')
        self.assertEqual(len(result['_meta']['attempts'][0]['accountAttempts']), 3)

    def test_pandamall_account_rotation_retries_next_account_before_success(self):
        pandamall_accounts = []
        calls = []

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider == 'gianghuy':
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': 'gianghuy failed',
                }

            if provider != 'pandamall':
                self.fail('taobao chain should stop after pandamall account success')

            pandamall_accounts.append(payload.get('phone'))
            if payload.get('phone') != PANDAMALL_ACCOUNTS[1]['phone']:
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': 'pandamall account died',
                }

            return PANDAMALL_TAOBAO_BRIDGE

        with patch('product_orchestrator.random.shuffle', lambda values: None):
            result = transform_product_from_url(
                'https://item.taobao.com/item.htm?id=1016154115457',
                debug=True,
                bridge_runner=fake_runner,
            )

        self.assertEqual(
            pandamall_accounts,
            [PANDAMALL_ACCOUNTS[0]['phone'], PANDAMALL_ACCOUNTS[1]['phone']],
        )
        self.assertEqual(calls[:3], ['gianghuy', 'pandamall', 'pandamall'])
        self.assertEqual(result['_meta']['providerUsed'], 'pandamall')
        self.assertEqual(result['_meta']['attempts'][1]['accountAttempts'][0]['success'], False)
        self.assertEqual(result['_meta']['attempts'][1]['accountAttempts'][1]['success'], True)

    def test_pandamall_account_rotation_caps_at_three_before_fallback(self):
        pandamall_accounts = []
        calls = []

        def fake_runner(action, payload, provider, marketplace):
            calls.append(provider)
            if provider == 'gianghuy':
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': 'gianghuy failed',
                }

            if provider == 'pandamall':
                pandamall_accounts.append(payload.get('phone'))
                return {
                    'ok': False,
                    'provider': provider,
                    'marketplace': marketplace,
                    'message': f"failed {payload.get('phone')}",
                }

            if provider == 'hangve':
                return HANGVE_TMALL_BRIDGE

            self.fail(f'unexpected provider {provider}')

        with patch('product_orchestrator.random.shuffle', lambda values: None):
            result = transform_product_from_url(
                'https://item.taobao.com/item.htm?id=1016154115457',
                debug=True,
                bridge_runner=fake_runner,
            )

        self.assertEqual(
            pandamall_accounts,
            [account['phone'] for account in PANDAMALL_ACCOUNTS[:3]],
        )
        self.assertEqual(calls[:5], ['gianghuy', 'pandamall', 'pandamall', 'pandamall', 'hangve'])
        self.assertEqual(result['_meta']['providerUsed'], 'hangve')
        self.assertEqual(len(result['_meta']['attempts'][1]['accountAttempts']), 3)


if __name__ == '__main__':
    unittest.main()
