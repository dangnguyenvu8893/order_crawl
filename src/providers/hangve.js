const { getProviderAccounts } = require("../config");
const { getHangveItemFull } = require("../clients/hangve-client");
const { mapHangveToCanonical } = require("../mappers/hangve");
const { runProviderWithOptionalAccounts } = require("./account-runner");
const { buildProviderSignal } = require("./utils");

async function resolveProduct(context, { signal: externalSignal } = {}) {
  const { result, accountAttempts } = await runProviderWithOptionalAccounts({
    accounts: getProviderAccounts("hangve"),
    label: "Hangve",
    userKey: "username",
    execute: async (account) => {
      const signal = buildProviderSignal("hangve", externalSignal);
      const response = await getHangveItemFull({
        keySearch: context.canonicalUrl,
        username: account.username,
        password: account.password,
        detailLimit: 1,
        signal
      });
      const normalized = response?.normalizedDetails?.[0];

      if (!normalized || typeof normalized !== "object") {
        throw new Error("Hangve item detail response does not contain normalized data");
      }

      return normalized;
    }
  });

  return {
    canonical: mapHangveToCanonical(result, context),
    accountAttempts
  };
}

module.exports = {
  name: "hangve",
  resolveProduct
};
