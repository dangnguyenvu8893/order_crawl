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

test("resolveProductUrlInput parses HTML body when redirect URL is still a short domain", async () => {
  let calls = 0;
  const resolved = await resolveProductUrlInput("https://e.tb.cn/h.randomShort", {
    fetchImpl: async (_url, options) => {
      calls += 1;
      if (options.method === "HEAD") {
        return {
          url: "https://e.tb.cn/h.randomShort",
          body: null,
          async text() {
            return "";
          }
        };
      }

      return {
        url: "https://e.tb.cn/h.randomShort",
        body: null,
        async text() {
          return '<script>location.href="https://detail.tmall.com/item.htm?id=950151754161"</script>';
        }
      };
    }
  });

  assert.equal(calls, 2);
  assert.equal(resolved.resolvedUrl, "https://detail.tmall.com/item.htm?id=950151754161");
  assert.equal(resolved.method, "redirect_get_mobile_content");
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
