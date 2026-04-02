const test = require("node:test");
const assert = require("node:assert/strict");

const { HttpError } = require("../src/core/errors");
const { transformProductFromUrl } = require("../src/core/orchestrator");
const { resetOrchestratorRuntimeState } = require("../src/core/orchestrator-state");
const { createNoopProviderExecutionGuard, resetProviderExecutionGuardState } = require("../src/core/provider-guard");

function buildCanonicalProduct(sourceType, sourceId) {
  return {
    provider: "fake",
    sourceType,
    sourceId,
    inputUrl: "",
    url:
      sourceType === "1688"
        ? `https://detail.1688.com/offer/${sourceId}.html`
        : sourceType === "tmall"
          ? `https://detail.tmall.com/item.htm?id=${sourceId}`
          : `https://item.taobao.com/item.htm?id=${sourceId}`,
    name: "Fake product",
    images: ["https://img.example.com/1.jpg"],
    variantGroups: [
      {
        name: "Color",
        sourcePropertyId: "1",
        values: [{ name: "Red", sourceValueId: "11", image: null }]
      }
    ],
    variants: [
      {
        skuId: "sku-1",
        specAttrs: "Color--Red|Size--M",
        quantity: 10,
        price: 99.5,
        promotionPrice: 89.5,
        image: null
      }
    ],
    priceRanges: [
      {
        minQuantity: 1,
        maxQuantity: 9,
        price: 89.5
      }
    ],
    maxPrice: "89.50",
    descriptionHtml: "<p>fake</p>"
  };
}

test.beforeEach(() => {
  resetOrchestratorRuntimeState();
  resetProviderExecutionGuardState();
});

test("orchestrator falls back in order and only reaches PandaMall last", async () => {
  const calls = [];
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls.push("gianghuy");
        return {
          canonical: {
            ...buildCanonicalProduct("taobao", "1016154115457"),
            images: []
          },
          accountAttempts: []
        };
      }
    },
    vipomall: {
      async resolveProduct() {
        calls.push("vipomall");
        throw new Error("vipomall failed");
      }
    },
    hangve: {
      async resolveProduct() {
        calls.push("hangve");
        throw new Error("hangve failed");
      }
    },
    pandamall: {
      async resolveProduct() {
        calls.push("pandamall");
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  const payload = await transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
    debug: true,
    providers,
    providerStartDelaysMs: {
      gianghuy: 0,
      vipomall: 5,
      hangve: 10,
      pandamall: 20
    }
  });

  assert.deepEqual(calls, ["gianghuy", "vipomall", "hangve", "pandamall"]);
  assert.equal(payload.sourceType, "taobao");
  assert.equal(payload._meta.providerUsed, "pandamall");
});

test("orchestrator uses VipoMall first for Tmall and does not call GiangHuy", async () => {
  const calls = [];
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls.push("gianghuy");
        return {
          canonical: buildCanonicalProduct("tmall", "1013307248141"),
          accountAttempts: []
        };
      }
    },
    vipomall: {
      async resolveProduct() {
        calls.push("vipomall");
        return {
          canonical: buildCanonicalProduct("tmall", "1013307248141"),
          accountAttempts: []
        };
      }
    },
    hangve: {
      async resolveProduct() {
        calls.push("hangve");
        return {
          canonical: buildCanonicalProduct("tmall", "1013307248141"),
          accountAttempts: []
        };
      }
    },
    pandamall: {
      async resolveProduct() {
        calls.push("pandamall");
        return {
          canonical: buildCanonicalProduct("tmall", "1013307248141"),
          accountAttempts: []
        };
      }
    }
  };

  const payload = await transformProductFromUrl("https://detail.tmall.com/item.htm?id=1013307248141", {
    providers,
    providerStartDelaysMs: {
      vipomall: 0,
      hangve: 20,
      pandamall: 40
    }
  });

  assert.deepEqual(calls, ["vipomall"]);
  assert.equal(payload.sourceType, "tmall");
});

test("orchestrator throws HttpError 502 when all providers fail", async () => {
  const providers = {
    gianghuy: { async resolveProduct() { throw new Error("gianghuy failed"); } },
    vipomall: { async resolveProduct() { throw new Error("vipomall failed"); } },
    hangve: { async resolveProduct() { throw new Error("hangve failed"); } },
    pandamall: { async resolveProduct() { throw new Error("pandamall failed"); } }
  };

  await assert.rejects(
    transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
      debug: true,
      providers,
      providerStartDelaysMs: {
        gianghuy: 0,
        vipomall: 3,
        hangve: 5,
        pandamall: 10
      }
    }),
    (error) => {
      assert.ok(error instanceof HttpError);
      assert.equal(error.statusCode, 502);
      assert.equal(error.code, "provider_chain_failed");
      assert.equal(error.details.providerUsed, "");
      return true;
    }
  );
});

test("orchestrator returns early from faster fallback without waiting full primary timeout", async () => {
  const calls = [];
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls.push("gianghuy");
        await new Promise((resolve) => setTimeout(resolve, 80));
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    },
    vipomall: {
      async resolveProduct() {
        calls.push("vipomall");
        await new Promise((resolve) => setTimeout(resolve, 10));
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    },
    hangve: {
      async resolveProduct() {
        calls.push("hangve");
        await new Promise((resolve) => setTimeout(resolve, 10));
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    },
    pandamall: {
      async resolveProduct() {
        calls.push("pandamall");
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  const startedAt = Date.now();
  const payload = await transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
    debug: true,
    providers,
    providerStartDelaysMs: {
      gianghuy: 0,
      vipomall: 5,
      hangve: 120,
      pandamall: 250
    }
  });

  assert.equal(payload._meta.providerUsed, "vipomall");
  assert.ok(Date.now() - startedAt < 70);
  assert.deepEqual(calls, ["gianghuy", "vipomall"]);
});

test("orchestrator dedupes concurrent requests for the same canonical URL", async () => {
  let calls = 0;
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 30));
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  const [first, second] = await Promise.all([
    transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
      debug: true,
      providers,
      providerStartDelaysMs: {
        gianghuy: 0
      }
    }),
    transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
      debug: true,
      providers,
      providerStartDelaysMs: {
        gianghuy: 0
      }
    })
  ]);

  assert.equal(calls, 1);
  assert.equal(first.sourceId, "1016154115457");
  assert.equal(second.sourceId, "1016154115457");
  assert.equal(first._meta.sharedRequest, false);
  assert.equal(second._meta.sharedRequest, true);
});

test("orchestrator serves repeated requests from the short-lived result cache", async () => {
  let calls = 0;
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls += 1;
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  const first = await transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
    debug: true,
    providers,
    providerStartDelaysMs: {
      gianghuy: 0
    }
  });
  const second = await transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
    debug: true,
    providers,
    providerStartDelaysMs: {
      gianghuy: 0
    }
  });

  assert.equal(calls, 1);
  assert.equal(first._meta.cacheHit, false);
  assert.equal(second._meta.cacheHit, true);
});

test("orchestrator enforces a hard request deadline", async () => {
  const providers = {
    gianghuy: {
      async resolveProduct() {
        await new Promise((resolve) => setTimeout(resolve, 80));
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };

  await assert.rejects(
    transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
      providers,
      providerStartDelaysMs: {
        gianghuy: 0
      },
      requestDeadlineMs: 20
    }),
    (error) => {
      assert.ok(error instanceof HttpError);
      assert.equal(error.statusCode, 502);
      assert.equal(error.code, "provider_deadline_exceeded");
      assert.equal(error.details.deadlineHit, true);
      return true;
    }
  );
});

test("orchestrator can swap provider guard strategy without touching providers", async () => {
  const calls = [];
  const providers = {
    gianghuy: {
      async resolveProduct() {
        calls.push("gianghuy");
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    },
    vipomall: {
      async resolveProduct() {
        calls.push("vipomall");
        return {
          canonical: buildCanonicalProduct("taobao", "1016154115457"),
          accountAttempts: []
        };
      }
    }
  };
  const customGuard = {
    ...createNoopProviderExecutionGuard(),
    beforeAttempt({ providerName }) {
      if (providerName === "gianghuy") {
        return {
          allowed: false,
          reason: "custom guard skipped gianghuy"
        };
      }

      return {
        allowed: true,
        release() {}
      };
    },
    afterAttempt() {}
  };

  const payload = await transformProductFromUrl("https://item.taobao.com/item.htm?id=1016154115457", {
    debug: true,
    providers,
    providerStartDelaysMs: {
      gianghuy: 0,
      vipomall: 0
    },
    providerExecutionGuard: customGuard
  });

  assert.deepEqual(calls, ["vipomall"]);
  assert.equal(payload._meta.providerUsed, "vipomall");
  assert.equal(payload._meta.attempts[0].message, "custom guard skipped gianghuy");
});

test("orchestrator resolves non-detail input before provider execution", async () => {
  let providerContext = null;
  const providers = {
    gianghuy: {
      async resolveProduct(context) {
        providerContext = context;
        return {
          canonical: buildCanonicalProduct("taobao", "1033960738640"),
          accountAttempts: []
        };
      }
    }
  };

  const payload = await transformProductFromUrl(
    "Tôi gửi link share: https://item.taobao.com/item.htm?id=1033960738640&spm=abc",
    {
      debug: true,
      providers,
      providerStartDelaysMs: {
        gianghuy: 0
      }
    }
  );

  assert.equal(payload.sourceId, "1033960738640");
  assert.equal(providerContext.inputUrl, "https://item.taobao.com/item.htm?id=1033960738640");
  assert.equal(providerContext.originalInput, "Tôi gửi link share: https://item.taobao.com/item.htm?id=1033960738640&spm=abc");
  assert.equal(payload._meta.resolver.method, "text_extract_direct");
});
