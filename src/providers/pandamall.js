const { getProviderAccounts } = require("../config");
const { isAbortError } = require("../core/errors");
const { normalizeString } = require("../core/product");
const { getIncompleteReasons, serializeBackendPayload } = require("../mappers/backend-payload");
const { mapPandamallToCanonical } = require("../mappers/pandamall");
const {
  getPandamallItemDetails,
  getPandamallItemDetailsNoAuth
} = require("../clients/pandamall-client");
const { buildProviderSignal } = require("./utils");

function maskPandamallPhone(phone) {
  const normalizedPhone = normalizeString(phone);
  if (normalizedPhone.length <= 4) {
    return normalizedPhone;
  }

  return `${"*".repeat(normalizedPhone.length - 4)}${normalizedPhone.slice(-4)}`;
}

function getPandamallProviderName(context) {
  return context.marketplace === "1688" ? "alibaba" : "taobao";
}

function getResolvedPandamallAccounts() {
  const accounts = getProviderAccounts("pandamall");
  return accounts.length > 0 ? accounts : [];
}

function extractPandamallRaw(response) {
  const raw = response?.itemDetails?.response?.data;

  if (!raw || typeof raw !== "object") {
    throw new Error("PandaMall item detail response does not contain product data");
  }

  if (raw.status !== true) {
    throw new Error(String(raw.message || "PandaMall item detail request failed"));
  }

  return raw;
}

function getPandamallCompleteness(canonical, getPayloadIncompleteReasons = getIncompleteReasons) {
  const payload = serializeBackendPayload(canonical);
  return getPayloadIncompleteReasons(payload);
}

function createPandamallProvider({
  getAccounts = getResolvedPandamallAccounts,
  fetchNoAuth = getPandamallItemDetailsNoAuth,
  fetchWithAuth = getPandamallItemDetails,
  mapToCanonical = mapPandamallToCanonical,
  getPayloadIncompleteReasons = getIncompleteReasons,
  buildSignal = buildProviderSignal
} = {}) {
  return {
    name: "pandamall",
    async resolveProduct(context, { signal: externalSignal } = {}) {
      const signal = buildSignal("pandamall", externalSignal);
      const provider = getPandamallProviderName(context);
      const noAuthResponse = await (async () => {
        try {
          return await fetchNoAuth({
            itemId: context.itemId,
            provider,
            url: context.canonicalUrl,
            signal
          });
        } catch (error) {
          if (isAbortError(error)) {
            throw error;
          }

          return null;
        }
      })();

      if (noAuthResponse) {
        const noAuthRaw = extractPandamallRaw(noAuthResponse);
        const noAuthCanonical = mapToCanonical(noAuthRaw, context);
        const noAuthIncompleteReasons = getPandamallCompleteness(noAuthCanonical, getPayloadIncompleteReasons);

        if (noAuthIncompleteReasons.length === 0) {
          return {
            canonical: noAuthCanonical,
            accountAttempts: []
          };
        }
      }

      const accounts = getAccounts(context);
      const accountAttempts = [];
      let lastError = null;

      for (let index = 0; index < accounts.length; index += 1) {
        const account = accounts[index];

        try {
          const response = await fetchWithAuth({
            itemId: context.itemId,
            provider,
            url: context.canonicalUrl,
            phone: account.phone,
            password: account.password,
            signal
          });
          const raw = extractPandamallRaw(response);
          const canonical = mapToCanonical(raw, context);
          const incompleteReasons = getPandamallCompleteness(canonical, getPayloadIncompleteReasons);
          const complete = incompleteReasons.length === 0;

          accountAttempts.push({
            attempt: index + 1,
            usernameMasked: maskPandamallPhone(account.phone),
            success: complete,
            message: complete
              ? "PandaMall account succeeded"
              : `PandaMall incomplete payload: ${incompleteReasons.join(", ")}`
          });

          if (complete) {
            return {
              canonical,
              accountAttempts
            };
          }

          lastError = new Error(`PandaMall incomplete payload: ${incompleteReasons.join(", ")}`);
        } catch (error) {
          accountAttempts.push({
            attempt: index + 1,
            usernameMasked: maskPandamallPhone(account.phone),
            success: false,
            message: error.message
          });

          if (isAbortError(error)) {
            error.accountAttempts = accountAttempts;
            throw error;
          }

          lastError = error;
        }
      }

      const error =
        lastError ??
        new Error(
          noAuthResponse
            ? "PandaMall no-auth payload was incomplete and no fallback account is configured"
            : "PandaMall account rotation exhausted"
        );
      error.accountAttempts = accountAttempts;
      throw error;
    }
  };
}

module.exports = {
  ...createPandamallProvider(),
  createPandamallProvider,
  extractPandamallRaw,
  getPandamallProviderName
};
