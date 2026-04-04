const test = require("node:test");
const assert = require("node:assert/strict");

const { HttpError } = require("../src/core/errors");
const {
  parseContentForProductUrl,
  resolveDirectProductUrlCandidate,
  resolveProductUrlInput
} = require("../src/core/url-resolver");

test("resolveDirectProductUrlCandidate unwraps nested product URLs from query params", () => {
  const resolved = resolveDirectProductUrlCandidate(
    "https://uland.taobao.com/coupon/edetail?targetUrl=https%3A%2F%2Fitem.taobao.com%2Fitem.htm%3Fid%3D1033960738640"
  );

  assert.equal(resolved, "https://item.taobao.com/item.htm?id=1033960738640");
});

test("resolveDirectProductUrlCandidate canonicalizes intermediate marketplace hosts with item ids", () => {
  const resolved = resolveDirectProductUrlCandidate(
    "https://tmallx.tmall.com/app/tmallx-src/goods-detail-weex/goods_detail_tm?id=918125731542&sourceType=item"
  );

  assert.equal(resolved, "https://detail.tmall.com/item.htm?id=918125731542");
});

test("parseContentForProductUrl extracts desktop URLs from HTML fragments", () => {
  const html = `
    <html>
      <body>
        <a href="https://detail.tmall.com/item.htm?id=950151754161">detail</a>
      </body>
    </html>
  `;

  assert.equal(
    parseContentForProductUrl(html, "https://m.tmall.com/anything"),
    "https://detail.tmall.com/item.htm?id=950151754161"
  );
});

test("resolveProductUrlInput parses deep links embedded in text", async () => {
  const resolved = await resolveProductUrlInput(
    "app share: taobao://item.taobao.com/item.htm?id=1033960738640"
  );

  assert.equal(resolved.resolvedUrl, "https://item.taobao.com/item.htm?id=1033960738640");
  assert.equal(resolved.extractedFromText, true);
});

test("resolveProductUrlInput prioritizes desktop html parsing for ambiguous short hosts", async () => {
  const calls = [];
  const resolved = await resolveProductUrlInput("https://e.tb.cn/h.randomShort", {
    fetchImpl: async (_url, options) => {
      calls.push({
        method: options.method,
        referer: options.headers?.referer
      });

      return {
        url: "https://e.tb.cn/h.randomShort",
        body: null,
        async text() {
          return '<script>location.href="https://detail.tmall.com/item.htm?id=950151754161"</script>';
        }
      };
    }
  });

  assert.deepEqual(calls, [
    {
      method: "GET",
      referer: "https://www.taobao.com/"
    }
  ]);
  assert.equal(resolved.resolvedUrl, "https://detail.tmall.com/item.htm?id=950151754161");
  assert.equal(resolved.method, "redirect_get_desktop_content");
});

test("resolveProductUrlInput rejects unsupported hosts after text extraction", async () => {
  await assert.rejects(
    resolveProductUrlInput("test https://example.com/product/123"),
    (error) => {
      assert.ok(error instanceof HttpError);
      assert.equal(error.statusCode, 400);
      assert.equal(error.code, "unsupported_host");
      return true;
    }
  );
});
