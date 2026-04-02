const test = require("node:test");
const assert = require("node:assert/strict");

const { HttpError } = require("../src/core/errors");
const { parseProductUrl } = require("../src/core/url");
const {
  buildProductContextFromInput,
  convertDeepLinkToDesktopUrl,
  extractBestUrlFromText,
  resolveProductUrlInput
} = require("../src/core/url-resolver");

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

test("extractBestUrlFromText prefers marketplace product URLs", () => {
  const extracted = extractBestUrlFromText(
    "Xem giúp tôi: abc https://example.com/skip và https://item.taobao.com/item.htm?id=1016154115457 nhé"
  );

  assert.equal(extracted, "https://item.taobao.com/item.htm?id=1016154115457");
});

test("convertDeepLinkToDesktopUrl converts app deep links to desktop detail URLs", () => {
  assert.equal(
    convertDeepLinkToDesktopUrl("taobao://item.taobao.com/item.htm?id=1016154115457"),
    "https://item.taobao.com/item.htm?id=1016154115457"
  );
  assert.equal(
    convertDeepLinkToDesktopUrl("wireless1688://detail.1688.com/offer/1016816643290.html?offerId=1016816643290"),
    "https://detail.1688.com/offer/1016816643290.html"
  );
});

test("resolveProductUrlInput normalizes text and mobile URLs without network", async () => {
  const fromText = await resolveProductUrlInput(
    "Link sản phẩm đây https://item.taobao.com/item.htm?id=1033960738640 vui lòng crawl"
  );
  const fromMobile = await resolveProductUrlInput("https://m.tmall.com/detail/detail.html?id=950151754161");

  assert.equal(fromText.resolvedUrl, "https://item.taobao.com/item.htm?id=1033960738640");
  assert.equal(fromText.extractedFromText, true);
  assert.equal(fromText.networkAttempted, false);
  assert.equal(fromMobile.resolvedUrl, "https://detail.tmall.com/item.htm?id=950151754161");
  assert.equal(fromMobile.networkAttempted, false);
});

test("resolveProductUrlInput resolves short links through redirect fallback", async () => {
  let calls = 0;
  const resolved = await resolveProductUrlInput("https://e.tb.cn/h.randomShort", {
    fetchImpl: async () => {
      calls += 1;
      return {
        url: "https://item.taobao.com/item.htm?id=1033960738640",
        body: null,
        async text() {
          return "";
        }
      };
    }
  });

  assert.equal(calls, 1);
  assert.equal(resolved.resolvedUrl, "https://item.taobao.com/item.htm?id=1033960738640");
  assert.equal(resolved.networkAttempted, true);
});

test("buildProductContextFromInput preserves original input and exposes resolver metadata", async () => {
  const context = await buildProductContextFromInput(
    "Lấy giúp https://detail.1688.com/offer/1016816643290.html?offerId=1016816643290"
  );

  assert.equal(context.originalInput, "Lấy giúp https://detail.1688.com/offer/1016816643290.html?offerId=1016816643290");
  assert.equal(context.inputUrl, "https://detail.1688.com/offer/1016816643290.html");
  assert.equal(context.canonicalUrl, "https://detail.1688.com/offer/1016816643290.html");
  assert.equal(context.resolution.method, "text_extract_direct");
});
