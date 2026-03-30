const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildHangveKeyFacinBase,
  createHangveKeyFacin,
  isHangveOptionEnabled,
  normalizeHangveItemDetailPayload,
  normalizeHangveSource,
  parseHangveMarketplaceUrl,
  resolveHangveDetailItemIds
} = require("../src/hangve-client");

test("normalizeHangveSource maps marketplace aliases", () => {
  assert.equal(normalizeHangveSource("1688"), "sync_1688");
  assert.equal(normalizeHangveSource("sync_1688"), "sync_1688");
  assert.equal(normalizeHangveSource("taobao"), "sync_taobao");
  assert.equal(normalizeHangveSource("tmall"), "sync_taobao");
});

test("buildHangveKeyFacinBase matches frontend arithmetic", () => {
  assert.equal(buildHangveKeyFacinBase(7453753745), 192965594164284);
});

test("createHangveKeyFacin follows the frontend format", () => {
  const keyFacin = createHangveKeyFacin({
    goSlim: 7453753745,
    randomPrefix: () => 12345,
    randomSuffix: () => 67890,
    randomString: () => "abcde12345vwxyz67890"
  });

  assert.equal(keyFacin, "1234519296559416428467890abcde12345vwxyz67890");
});

test("isHangveOptionEnabled handles cli-style values", () => {
  assert.equal(isHangveOptionEnabled(true), true);
  assert.equal(isHangveOptionEnabled("true"), true);
  assert.equal(isHangveOptionEnabled("1"), true);
  assert.equal(isHangveOptionEnabled("false"), false);
  assert.equal(isHangveOptionEnabled("0"), false);
});

test("resolveHangveDetailItemIds prioritizes explicit itemId", () => {
  assert.deepEqual(
    resolveHangveDetailItemIds({
      searchItems: [{ id: 1 }, { id: 2 }],
      itemId: 1471325,
      detailLimit: 5
    }),
    [1471325]
  );
});

test("resolveHangveDetailItemIds derives ids from search results", () => {
  assert.deepEqual(
    resolveHangveDetailItemIds({
      searchItems: [{ id: 1471325 }, { id: 1471326 }, { id: "x" }],
      detailLimit: 2
    }),
    [1471325, 1471326]
  );
});

test("parseHangveMarketplaceUrl detects taobao and tmall as sync_taobao", () => {
  assert.deepEqual(
    parseHangveMarketplaceUrl("https://item.taobao.com/item.htm?id=1016154115457")?.source,
    "sync_taobao"
  );
  assert.deepEqual(
    parseHangveMarketplaceUrl("https://detail.tmall.com/item.htm?id=1013307248141")?.source,
    "sync_taobao"
  );
  assert.deepEqual(
    parseHangveMarketplaceUrl("https://detail.1688.com/offer/892407994374.html")?.source,
    "sync_1688"
  );
});

test("normalizeHangveItemDetailPayload parses 1688 detail strings", () => {
  const normalized = normalizeHangveItemDetailPayload({
    id: 1471325,
    source: "1688",
    num_iid: "892407994374",
    title: "French dress",
    price: 47.98,
    promotion_price: 47.98,
    seller_nick: "Shop 1688",
    detail_url: "https://detail.1688.com/offer/892407994374.html",
    buyder_data: JSON.stringify({
      mpId: 892407994374,
      shopName: "Shop 1688",
      description: "<p>desc</p>",
      minOrderQuantity: 2,
      quantity: 123,
      priceRangeList: [{ startQuantity: 2, price: "47.98" }]
    }),
    sku_properties: JSON.stringify({
      pic_urls: ["https://img-1.jpg", "https://img-2.jpg"],
      properties: [
        {
          prop_name: "Color",
          prop_name_original: "Color",
          prop_values: ["Beige"],
          prop_values_original: ["Beige"],
          prop_values_original_cn: ["Mi se"]
        }
      ],
      details: [
        {
          classification: "Beige;S",
          classification_cn: "Mi se;S",
          quantity: "10",
          price: "47.98",
          promotionPrice: "46.98",
          pic_url: "https://img-1.jpg",
          mp_sku_id: "sku-1"
        }
      ]
    }),
    data: {
      item: {
        num_iid: "892407994374",
        title: "French dress",
        detail_url: "https://detail.1688.com/offer/892407994374.html",
        images: ["https://img-1.jpg"],
        properties: [{ name: "Material", value: "Polyester" }]
      }
    }
  });

  assert.equal(normalized.itemId, 1471325);
  assert.equal(normalized.numIid, "892407994374");
  assert.equal(normalized.imageCount, 2);
  assert.equal(normalized.skuCount, 1);
  assert.equal(normalized.attributeCount, 1);
  assert.equal(normalized.priceRangeCount, 1);
  assert.equal(normalized.descriptionHtml, "<p>desc</p>");
  assert.equal(normalized.variantGroups[0].name, "Color");
  assert.equal(normalized.skus[0].skuId, "sku-1");
  assert.equal(normalized.attributes[0].name, "Material");
});

test("normalizeHangveItemDetailPayload parses taobao detail strings", () => {
  const normalized = normalizeHangveItemDetailPayload({
    id: 2508970,
    source: "taobao",
    num_iid: "1016154115457",
    title: "Lace top",
    price: 151.52,
    promotion_price: 143.95,
    seller_nick: "Ranwear official",
    detail_url: "https://item.taobao.com/item.htm?id=1016154115457",
    buyder_data: JSON.stringify({
      shopName: "Ranwear official",
      description: "<div>detail</div>",
      min_order_quantity: 1,
      quantity: 130,
      price_ranges: [{ beginAmount: 1, price: "151.52" }]
    }),
    sku_properties: JSON.stringify({
      pic_urls: ["https://img-a.jpg"],
      properties: [
        {
          prop_name: "Color",
          prop_name_original: "Color",
          prop_values: ["White"],
          prop_values_original: ["White"],
          prop_values_original_cn: ["Bai"]
        }
      ],
      details: [
        {
          classification: "White;S",
          classification_cn: "Bai;S",
          quantity: 130,
          price: 151.52,
          promotionPrice: 143.95,
          pic_url: "https://img-a.jpg",
          mp_sku_id: "6025255024005",
          sku_id: "6025255024005"
        }
      ]
    }),
    data: {
      item: {
        images: ["https://img-a.jpg", "https://img-b.jpg"],
        properties: [
          {
            quantity: 130,
            price: 15152,
            skuId: "6025255024005"
          }
        ]
      }
    }
  });

  assert.equal(normalized.itemId, 2508970);
  assert.equal(normalized.numIid, "1016154115457");
  assert.equal(normalized.imageCount, 2);
  assert.equal(normalized.skuCount, 1);
  assert.equal(normalized.attributeCount, 0);
  assert.equal(normalized.priceRangeCount, 1);
  assert.equal(normalized.descriptionHtml, "<div>detail</div>");
  assert.equal(normalized.variantGroups[0].values[0], "White");
  assert.equal(normalized.skus[0].price, 151.52);
  assert.equal(normalized.skus[0].promotionPrice, 143.95);
});
