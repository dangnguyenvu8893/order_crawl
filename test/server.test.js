const test = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");

const { HttpError } = require("../src/core/errors");
const { transformProductFromUrl } = require("../src/core/orchestrator");
const { resetOrchestratorRuntimeState } = require("../src/core/orchestrator-state");
const { resetProviderExecutionGuardState } = require("../src/core/provider-guard");
const { createServer } = require("../src/server/app");

function buildCanonicalProduct(sourceType, sourceId) {
  return {
    provider: "fake",
    sourceType,
    sourceId,
    inputUrl: "",
    url: `https://item.taobao.com/item.htm?id=${sourceId}`,
    name: "Server fake product",
    images: ["https://img.example.com/1.jpg"],
    variantGroups: [],
    variants: [
      {
        skuId: "sku-1",
        specAttrs: "Red|M",
        quantity: 8,
        price: 20,
        promotionPrice: 18,
        image: null
      }
    ],
    priceRanges: [{ minQuantity: 1, maxQuantity: 5, price: 18 }],
    maxPrice: "18.00",
    descriptionHtml: ""
  };
}

async function withServer(transform, callback) {
  const server = createServer({ transform });
  server.listen(0);
  await once(server, "listening");
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  try {
    await callback(baseUrl);
  } finally {
    server.close();
    await once(server, "close");
  }
}

test.beforeEach(() => {
  resetOrchestratorRuntimeState();
  resetProviderExecutionGuardState();
});

test("GET /health returns ok", async () => {
  await withServer(async () => ({}), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/health`);
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(payload, { status: "ok" });
  });
});

test("GET /health echoes X-Request-Id header", async () => {
  await withServer(async () => ({}), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/health`, {
      headers: {
        "x-request-id": "req-xyz"
      }
    });

    assert.equal(response.headers.get("x-request-id"), "req-xyz");
  });
});

test("POST /transform-product-from-url returns transformed payload", async () => {
  const providers = {
    gianghuy: { async resolveProduct() { throw new Error("gianghuy failed"); } },
    hangve: { async resolveProduct() { throw new Error("hangve failed"); } },
    pandamall: {
      async resolveProduct() {
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  await withServer(
    (url, options) => transformProductFromUrl(url, { ...options, providers }),
    async (baseUrl) => {
      const response = await fetch(`${baseUrl}/transform-product-from-url`, {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          url: "https://item.taobao.com/item.htm?id=1016154115457",
          debug: true
        })
      });
      const payload = await response.json();

      assert.equal(response.status, 200);
      assert.equal(payload.sourceType, "taobao");
      assert.equal(payload._meta.providerUsed, "pandamall");
    }
  );
});

test("POST /transform-product-from-url returns 400 for unsupported URL", async () => {
  await withServer((url, options) => transformProductFromUrl(url, options), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/transform-product-from-url`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        url: "https://example.com/not-supported"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 400);
    assert.equal(payload.error, "Unsupported marketplace host: example.com");
  });
});

test("POST /transform-product-from-url returns 502 when provider chain fails", async () => {
  await withServer(async () => {
    throw new HttpError("Could not fetch product data from any provider", 502, "provider_chain_failed");
  }, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/transform-product-from-url`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        url: "https://item.taobao.com/item.htm?id=1016154115457"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 502);
    assert.equal(payload.error, "Could not fetch product data from any provider");
  });
});
