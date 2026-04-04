const test = require("node:test");
const assert = require("node:assert/strict");

const { parseProductUrl } = require("../src/core/url");
const { serializeBackendPayload } = require("../src/mappers/backend-payload");
const { mapGianghuyToCanonical } = require("../src/mappers/gianghuy");
const { mapHangveToCanonical } = require("../src/mappers/hangve");
const { mapPandamallToCanonical } = require("../src/mappers/pandamall");
const { mapVipomallToCanonical } = require("../src/mappers/vipomall");
const {
  GIANGHUY_1688_RAW,
  HANGVE_TMALL_NORMALIZED,
  PANDAMALL_TAOBAO_RAW,
  VIPOMALL_TAOBAO_RAW
} = require("./fixtures");

test("GiangHuy mapper serializes backend payload with value-only specAttrs", () => {
  const context = parseProductUrl("https://detail.1688.com/offer/892407994374.html?offerId=892407994374");
  const canonical = mapGianghuyToCanonical(GIANGHUY_1688_RAW, context);
  const payload = serializeBackendPayload(canonical);

  assert.equal(payload.sourceType, "1688");
  assert.equal(payload.sourceId, "892407994374");
  assert.equal(payload.images.length, 2);
  assert.equal(payload.skuProperty[0].sourcePropertyId, null);
  assert.equal(payload.skuProperty[0].values[0].sourceValueId, null);
  assert.equal(payload.sku[0].specAttrs, "Beige|S");
  assert.equal(payload.sku[0].skuId, "sku-1688-1");
  assert.ok(!Object.hasOwn(payload, "properties"));
});

test("PandaMall mapper parses ranges and drops non-numeric source ids", () => {
  const raw = structuredClone(PANDAMALL_TAOBAO_RAW);
  raw.data.classify.skuProperties[0].propValues[0].valueID = "Milkshake White";
  const context = parseProductUrl("https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005");
  const canonical = mapPandamallToCanonical(raw, context);
  const payload = serializeBackendPayload(canonical);

  assert.equal(payload.sourceType, "taobao");
  assert.equal(payload.images.length, 3);
  assert.equal(payload.skuProperty[0].sourcePropertyId, "1627207");
  assert.equal(payload.skuProperty[0].values[0].sourceValueId, null);
  assert.equal(payload.sku[0].specAttrs, "Milkshake White - Còn hàng|S");
  assert.equal(payload.rangePrices.length, 2);
});

test("Hangve mapper preserves marketplace identity and serializes specAttrs correctly", () => {
  const context = parseProductUrl("https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393");
  const canonical = mapHangveToCanonical(HANGVE_TMALL_NORMALIZED, context);
  const payload = serializeBackendPayload(canonical);

  assert.equal(payload.sourceType, "tmall");
  assert.equal(payload.sourceId, "1013307248141");
  assert.equal(payload.url, "https://detail.tmall.com/item.htm?id=1013307248141");
  assert.equal(payload.sku[0].specAttrs, "Red|S");
});

test("VipoMall mapper normalizes media urls and maps sku/value ids conservatively", () => {
  const context = parseProductUrl("https://item.taobao.com/item.htm?id=1010925503027");
  const canonical = mapVipomallToCanonical(VIPOMALL_TAOBAO_RAW, context);
  const payload = serializeBackendPayload(canonical);

  assert.equal(payload.sourceType, "taobao");
  assert.equal(payload.sourceId, "1010925503027");
  assert.equal(payload.images.length, 2);
  assert.equal(payload.images[0], "https://img.alicdn.com/bao/uploaded/i1/example-1.jpg");
  assert.equal(payload.skuProperty[0].sourcePropertyId, "144160005");
  assert.equal(payload.skuProperty[0].values[0].sourceValueId, "42730477369");
  assert.equal(payload.skuProperty[0].values[0].image, "https://img.alicdn.com/bao/uploaded/i4/example-color.jpg");
  assert.equal(payload.skuProperty[0].name, "专辑名称");
  assert.equal(payload.skuProperty[0].values[0].name, "副卡一年（秒发新用户）");
  assert.equal(payload.sku[0].specAttrs, "副卡一年（秒发新用户）");
  assert.equal(payload.rangePrices.length, 1);
  assert.equal(payload.rangePrices[0].price, 93.69);
});
