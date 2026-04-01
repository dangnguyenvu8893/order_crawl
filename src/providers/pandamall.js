const { getProviderAccounts } = require("../config");
const { getPandamallItemDetails } = require("../clients/pandamall-client");
const { mapPandamallToCanonical } = require("../mappers/pandamall");
const { runProviderWithOptionalAccounts } = require("./account-runner");
const { buildProviderSignal } = require("./utils");

async function resolveProduct(context, { signal: externalSignal } = {}) {
  const { result, accountAttempts } = await runProviderWithOptionalAccounts({
    accounts: getProviderAccounts("pandamall"),
    label: "PandaMall",
    userKey: "phone",
    execute: async (account) => {
      const signal = buildProviderSignal("pandamall", externalSignal);
      const response = await getPandamallItemDetails({
        itemId: context.itemId,
        provider: context.marketplace === "1688" ? "alibaba" : "taobao",
        url: context.canonicalUrl,
        phone: account.phone,
        password: account.password,
        signal
      });
      const raw = response?.itemDetails?.response?.data;

      if (!raw || typeof raw !== "object") {
        throw new Error("PandaMall item detail response does not contain product data");
      }

      if (raw.status !== true) {
        throw new Error(String(raw.message || "PandaMall item detail request failed"));
      }

      return raw;
    }
  });

  return {
    canonical: mapPandamallToCanonical(result, context),
    accountAttempts
  };
}

module.exports = {
  name: "pandamall",
  resolveProduct
};
