const test = require("node:test");
const assert = require("node:assert/strict");

const { HttpError } = require("../src/core/errors");
const { parseProductUrl } = require("../src/core/url");

test("parseProductUrl canonicalizes marketplace URLs", () => {
  const offer1688 = parseProductUrl(
    "https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751"
  );
  const taobao = parseProductUrl("https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005");
  const tmall = parseProductUrl("https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393");

  assert.equal(offer1688.marketplace, "1688");
  assert.equal(offer1688.canonicalUrl, "https://detail.1688.com/offer/892407994374.html");
  assert.equal(taobao.canonicalUrl, "https://item.taobao.com/item.htm?id=1016154115457");
  assert.equal(tmall.canonicalUrl, "https://detail.tmall.com/item.htm?id=1013307248141");
});

test("parseProductUrl rejects unsupported hosts", () => {
  assert.throws(() => parseProductUrl("https://example.com/product/123"), (error) => {
    assert.ok(error instanceof HttpError);
    assert.equal(error.statusCode, 400);
    assert.equal(error.code, "unsupported_host");
    return true;
  });
});
