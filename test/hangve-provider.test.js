const test = require("node:test");
const assert = require("node:assert/strict");

const { createHangveProvider } = require("../src/providers/hangve");

function buildContext(overrides = {}) {
  return {
    marketplace: "1688",
    itemId: "1016816643290",
    inputUrl:
      "https://detail.1688.com/offer/1016816643290.html?offerId=1016816643290&skuId=6191742274948",
    canonicalUrl: "https://detail.1688.com/offer/1016816643290.html",
    ...overrides
  };
}

function mapNormalizedToCanonical(normalized, context) {
  return {
    provider: "hangve",
    sourceType: context.marketplace,
    sourceId: context.itemId,
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name: normalized.title ?? "",
    images: normalized.images ?? [],
    variantGroups: [],
    variants: [],
    priceRanges: normalized.priceRanges ?? [],
    maxPrice: normalized.maxPrice ?? "",
    descriptionHtml: ""
  };
}

test("hangve provider retries next account when first account returns incomplete payload", async () => {
  const calls = [];
  const records = [];
  const provider = createHangveProvider({
    getAccounts() {
      return [
        { username: "0905687687", password: "a" },
        { username: "0905252513", password: "b" }
      ];
    },
    getRankedAccounts(_marketplace, accounts) {
      return accounts;
    },
    getCachedSession() {
      return null;
    },
    setCachedSession() {},
    invalidateCachedSession() {},
    recordAccountResult(result) {
      records.push(result);
    },
    buildSignal(_providerName, signal) {
      return signal ?? new AbortController().signal;
    },
    async login({ username }) {
      return {
        token: `token:${username}`,
        customer: { id: 1 }
      };
    },
    async fetchProduct({ keySearch, token }) {
      calls.push({
        keySearch,
        token
      });

      if (token === "token:0905687687") {
        return {
          normalizedDetails: [
            {
              title: "Incomplete",
              images: [],
              priceRanges: [{ minQuantity: 1, price: 10 }]
            }
          ]
        };
      }

      return {
        normalizedDetails: [
          {
            title: "Complete",
            images: ["https://img.example.com/1.jpg"],
            priceRanges: [{ minQuantity: 1, price: 10 }]
          }
        ]
      };
    },
    mapToCanonical: mapNormalizedToCanonical
  });

  const result = await provider.resolveProduct(buildContext());

  assert.equal(result.canonical.name, "Complete");
  assert.equal(calls[0].keySearch, buildContext().inputUrl);
  assert.deepEqual(
    result.accountAttempts.map((attempt) => ({
      success: attempt.success,
      message: attempt.message
    })),
    [
      {
        success: false,
        message: "Hangve incomplete payload: missing images"
      },
      {
        success: true,
        message: "Hangve account succeeded"
      }
    ]
  );
  assert.equal(records[0].complete, false);
  assert.equal(records[1].complete, true);
});

test("hangve provider reuses cached session and refreshes the same account on cached-session failure", async () => {
  const invalidated = [];
  const cache = new Map([
    [
      "0905687687",
      {
        token: "cached-token",
        customer: { id: 7 }
      }
    ]
  ]);
  let loginCalls = 0;
  const fetchCalls = [];
  const provider = createHangveProvider({
    getAccounts() {
      return [{ username: "0905687687", password: "a" }];
    },
    getRankedAccounts(_marketplace, accounts) {
      return accounts;
    },
    getCachedSession(username) {
      return cache.get(username) ?? null;
    },
    setCachedSession(username, session) {
      cache.set(username, session);
    },
    invalidateCachedSession(username) {
      invalidated.push(username);
      cache.delete(username);
    },
    recordAccountResult() {},
    buildSignal(_providerName, signal) {
      return signal ?? new AbortController().signal;
    },
    async login({ username }) {
      loginCalls += 1;
      return {
        token: `fresh-token:${username}`,
        customer: { id: 7 }
      };
    },
    async fetchProduct({ token }) {
      fetchCalls.push(token);

      if (token === "cached-token") {
        throw new Error("token expired");
      }

      return {
        normalizedDetails: [
          {
            title: "Recovered",
            images: ["https://img.example.com/1.jpg"],
            priceRanges: [{ minQuantity: 1, price: 10 }]
          }
        ]
      };
    },
    mapToCanonical: mapNormalizedToCanonical
  });

  const result = await provider.resolveProduct(buildContext());

  assert.equal(result.canonical.name, "Recovered");
  assert.equal(loginCalls, 1);
  assert.deepEqual(fetchCalls, ["cached-token", "fresh-token:0905687687"]);
  assert.deepEqual(invalidated, ["0905687687"]);
  assert.equal(result.accountAttempts.length, 1);
  assert.equal(result.accountAttempts[0].success, true);
});
