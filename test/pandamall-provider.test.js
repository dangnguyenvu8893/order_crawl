const test = require("node:test");
const assert = require("node:assert/strict");

const { createPandamallProvider } = require("../src/providers/pandamall");

function buildContext(overrides = {}) {
  return {
    marketplace: "taobao",
    itemId: "1033960738640",
    inputUrl: "https://item.taobao.com/item.htm?id=1033960738640",
    canonicalUrl: "https://item.taobao.com/item.htm?id=1033960738640",
    ...overrides
  };
}

function buildCanonical(name, context, overrides = {}) {
  return {
    provider: "pandamall",
    sourceType: context.marketplace,
    sourceId: context.itemId,
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name,
    images: ["https://img.example.com/1.jpg"],
    variantGroups: [],
    variants: [],
    priceRanges: [{ minQuantity: 1, price: 10 }],
    maxPrice: "10.00",
    descriptionHtml: "",
    ...overrides
  };
}

test("pandamall provider uses no-auth detail when payload is complete", async () => {
  const calls = [];
  const context = buildContext();
  const provider = createPandamallProvider({
    async fetchNoAuth(options) {
      calls.push(["no-auth", options.provider, options.itemId]);
      return {
        itemDetails: {
          response: {
            data: {
              status: true,
              data: {
                id: context.itemId,
                name: "Fast path"
              }
            }
          }
        }
      };
    },
    async fetchWithAuth() {
      calls.push(["auth"]);
      throw new Error("auth should not be called");
    },
    mapToCanonical(raw, activeContext) {
      return buildCanonical(raw.data.name, activeContext);
    }
  });

  const result = await provider.resolveProduct(context);

  assert.equal(result.canonical.name, "Fast path");
  assert.deepEqual(result.accountAttempts, []);
  assert.deepEqual(calls, [["no-auth", "taobao", context.itemId]]);
});

test("pandamall provider falls back to auth accounts when no-auth payload is incomplete", async () => {
  const calls = [];
  const context = buildContext();
  const provider = createPandamallProvider({
    getAccounts() {
      return [{ phone: "0905687687", password: "a" }];
    },
    async fetchNoAuth() {
      calls.push(["no-auth"]);
      return {
        itemDetails: {
          response: {
            data: {
              status: true,
              data: {
                id: context.itemId,
                name: "No auth incomplete"
              }
            }
          }
        }
      };
    },
    async fetchWithAuth(options) {
      calls.push(["auth", options.phone]);
      return {
        itemDetails: {
          response: {
            data: {
              status: true,
              data: {
                id: context.itemId,
                name: "Auth complete"
              }
            }
          }
        }
      };
    },
    mapToCanonical(raw, activeContext) {
      if (raw.data.name === "No auth incomplete") {
        return buildCanonical(raw.data.name, activeContext, {
          images: []
        });
      }

      return buildCanonical(raw.data.name, activeContext);
    }
  });

  const result = await provider.resolveProduct(context);

  assert.equal(result.canonical.name, "Auth complete");
  assert.deepEqual(calls, [["no-auth"], ["auth", "0905687687"]]);
  assert.deepEqual(result.accountAttempts, [
    {
      attempt: 1,
      usernameMasked: "******7687",
      success: true,
      message: "PandaMall account succeeded"
    }
  ]);
});

test("pandamall provider rejects degraded translated labels for taobao source matching", async () => {
  const context = buildContext();
  const provider = createPandamallProvider({
    async fetchNoAuth() {
      return {
        itemDetails: {
          response: {
            data: {
              status: true,
              data: {
                id: context.itemId,
                name: "Degraded"
              }
            }
          }
        }
      };
    },
    getAccounts() {
      return [];
    },
    mapToCanonical(raw, activeContext) {
      return buildCanonical(raw.data.name, activeContext, {
        variantGroups: [
          {
            name: "Thông số sản phẩm",
            sourcePropertyId: null,
            values: [{ name: "Hành khách [phải]", sourceValueId: null, image: null }]
          }
        ],
        variants: [
          {
            skuId: "sku-1",
            specAttrs: "Hành khách [phải]",
            quantity: 10,
            price: 10,
            promotionPrice: 10,
            image: null
          }
        ]
      });
    }
  });

  await assert.rejects(
    provider.resolveProduct(context),
    /incomplete|degraded/i
  );
});
