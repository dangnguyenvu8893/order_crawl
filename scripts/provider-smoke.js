const { getProviderChain } = require("../src/config");
const { parseProductUrl } = require("../src/core/url");
const { getIncompleteReasons, serializeBackendPayload } = require("../src/mappers/backend-payload");
const { PROVIDERS } = require("../src/providers");

const SAMPLE_URLS = {
  "1688": process.env.PROVIDER_SMOKE_URL_1688 ?? "https://detail.1688.com/offer/892407994374.html",
  taobao: process.env.PROVIDER_SMOKE_URL_TAOBAO ?? "https://item.taobao.com/item.htm?id=1016154115457",
  tmall: process.env.PROVIDER_SMOKE_URL_TMALL ?? "https://detail.tmall.com/item.htm?id=1013307248141"
};

async function runSmokeCheck() {
  const results = [];

  for (const [marketplace, url] of Object.entries(SAMPLE_URLS)) {
    const context = parseProductUrl(url);

    for (const providerName of getProviderChain(marketplace)) {
      const provider = PROVIDERS[providerName];
      const startedAt = Date.now();

      try {
        const result = await provider.resolveProduct(context);
        const payload = serializeBackendPayload(result.canonical);
        const incompleteReasons = getIncompleteReasons(payload);

        results.push({
          marketplace,
          provider: providerName,
          url: context.canonicalUrl,
          ok: incompleteReasons.length === 0,
          latencyMs: Date.now() - startedAt,
          incompleteReasons
        });
      } catch (error) {
        results.push({
          marketplace,
          provider: providerName,
          url: context.canonicalUrl,
          ok: false,
          latencyMs: Date.now() - startedAt,
          error: error.message
        });
      }
    }
  }

  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);

  if (results.some((result) => !result.ok)) {
    process.exitCode = 1;
  }
}

runSmokeCheck().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
