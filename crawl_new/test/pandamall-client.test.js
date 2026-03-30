const test = require("node:test");
const assert = require("node:assert/strict");
const {
  createPandamallDpopProof,
  mutateUuidForJti,
  normalizePandamallProvider,
  parsePandamallMarketplaceUrl,
  normalizeRequestPath
} = require("../src/pandamall-client");

function decodeBase64UrlJson(segment) {
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return JSON.parse(Buffer.from(padded, "base64").toString("utf8"));
}

test("mutateUuidForJti follows the bundle format", () => {
  const result = mutateUuidForJti("abcd-ef", () => 1);

  assert.equal(result.origin, "abcd-ef");
  assert.equal(result.encoded, "axcd-ex");
  assert.equal(result.signature, "011029801103102");
});

test("normalizeRequestPath keeps only pathname", () => {
  assert.equal(
    normalizeRequestPath("https://api.pandamall.vn/api/pandamall/auth/login?foo=bar"),
    "/api/pandamall/auth/login"
  );

  assert.equal(
    normalizeRequestPath("/api/pandamall/auth/login"),
    "/api/pandamall/auth/login"
  );
});

test("normalizePandamallProvider maps supported marketplaces", () => {
  assert.equal(normalizePandamallProvider("1688"), "alibaba");
  assert.equal(normalizePandamallProvider("alibaba"), "alibaba");
  assert.equal(normalizePandamallProvider("taobao"), "taobao");
  assert.equal(normalizePandamallProvider("tmall"), "taobao");
});

test("parsePandamallMarketplaceUrl detects tmall url", () => {
  const result = parsePandamallMarketplaceUrl(
    "https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393"
  );

  assert.equal(result.marketplace, "tmall");
  assert.equal(result.provider, "taobao");
  assert.equal(result.normalizedProvider, "taobao");
  assert.equal(result.itemId, "1013307248141");
});

test("parsePandamallMarketplaceUrl detects taobao url", () => {
  const result = parsePandamallMarketplaceUrl(
    "https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005"
  );

  assert.equal(result.marketplace, "taobao");
  assert.equal(result.provider, "taobao");
  assert.equal(result.normalizedProvider, "taobao");
  assert.equal(result.itemId, "1016154115457");
});

test("parsePandamallMarketplaceUrl detects 1688 url", () => {
  const result = parsePandamallMarketplaceUrl(
    "https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751"
  );

  assert.equal(result.marketplace, "1688");
  assert.equal(result.provider, "alibaba");
  assert.equal(result.normalizedProvider, "alibaba");
  assert.equal(result.itemId, "892407994374");
});

test("createPandamallDpopProof builds expected claims", async () => {
  const proof = await createPandamallDpopProof({
    url: "https://api.pandamall.vn/api/pandamall/auth/login?foo=bar",
    method: "post",
    uuid: "abcd-ef",
    now: Date.UTC(2026, 2, 30, 0, 0, 0),
    pickIndex: () => 1
  });

  const [encodedHeader, encodedPayload, encodedSignature] = proof.token.split(".");
  const decodedHeader = decodeBase64UrlJson(encodedHeader);
  const decodedPayload = decodeBase64UrlJson(encodedPayload);

  assert.equal(decodedHeader.typ, "dpop");
  assert.equal(decodedHeader.alg, "ES256");
  assert.equal(decodedHeader.jwk.crv, "P-256");

  assert.equal(decodedPayload.iat, Math.ceil(Date.UTC(2026, 2, 30, 0, 0, 0) / 1000));
  assert.equal(decodedPayload.jti, "axcd-ex");
  assert.equal(decodedPayload.htu, "/api/pandamall/auth/login");
  assert.equal(decodedPayload.htm, "POST");
  assert.equal(decodedPayload.jis, "011029801103102");
  assert.ok(encodedSignature.length > 0);
});
