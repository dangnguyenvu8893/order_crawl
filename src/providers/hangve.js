const { getProviderAccounts } = require("../config");
const { loginHangveAndGetSession, getHangveItemFull } = require("../clients/hangve-client");
const { isAbortError } = require("../core/errors");
const { normalizeString } = require("../core/product");
const { getIncompleteReasons, serializeBackendPayload } = require("../mappers/backend-payload");
const { mapHangveToCanonical } = require("../mappers/hangve");
const {
  getHangveCachedSession,
  invalidateHangveCachedSession,
  rankHangveAccounts,
  recordHangveAccountResult,
  setHangveCachedSession
} = require("./hangve-state");
const { buildProviderSignal } = require("./utils");

function maskHangveUsername(username) {
  const normalizedUsername = normalizeString(username);
  if (normalizedUsername.length <= 4) {
    return normalizedUsername;
  }

  return `${"*".repeat(normalizedUsername.length - 4)}${normalizedUsername.slice(-4)}`;
}

function getHangveLookupUrl(context) {
  return normalizeString(context?.inputUrl) || normalizeString(context?.canonicalUrl);
}

function getResolvedHangveAccounts() {
  const configuredAccounts = getProviderAccounts("hangve");
  return configuredAccounts.length > 0 ? configuredAccounts : [{}];
}

async function fetchHangveNormalizedProduct({
  account,
  context,
  signal,
  login = loginHangveAndGetSession,
  fetchProduct = getHangveItemFull,
  getCachedSession = getHangveCachedSession,
  setCachedSession = setHangveCachedSession,
  invalidateCachedSession = invalidateHangveCachedSession
} = {}) {
  const username = normalizeString(account?.username);
  const lookupUrl = getHangveLookupUrl(context);

  async function fetchWithSession(session) {
    const response = await fetchProduct({
      keySearch: lookupUrl,
      token: session.token,
      customer: session.customer,
      detailLimit: 1,
      signal
    });
    const normalized = response?.normalizedDetails?.[0];

    if (!normalized || typeof normalized !== "object") {
      throw new Error("Hangve item detail response does not contain normalized data");
    }

    return normalized;
  }

  const cachedSession = getCachedSession(username);
  if (cachedSession) {
    try {
      return await fetchWithSession(cachedSession);
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }

      invalidateCachedSession(username);
    }
  }

  const freshSession = await login({
    username: account?.username,
    password: account?.password,
    signal
  });

  setCachedSession(username, freshSession);

  try {
    return await fetchWithSession(freshSession);
  } catch (error) {
    invalidateCachedSession(username);
    throw error;
  }
}

function createHangveProvider({
  getAccounts = getResolvedHangveAccounts,
  getRankedAccounts = rankHangveAccounts,
  login = loginHangveAndGetSession,
  fetchProduct = getHangveItemFull,
  mapToCanonical = mapHangveToCanonical,
  serializePayload = serializeBackendPayload,
  getPayloadIncompleteReasons = getIncompleteReasons,
  recordAccountResult = recordHangveAccountResult,
  getCachedSession = getHangveCachedSession,
  setCachedSession = setHangveCachedSession,
  invalidateCachedSession = invalidateHangveCachedSession,
  buildSignal = buildProviderSignal,
  now = Date.now
} = {}) {
  return {
    name: "hangve",
    async resolveProduct(context, { signal: externalSignal } = {}) {
      const signal = buildSignal("hangve", externalSignal);
      const orderedAccounts = getRankedAccounts(context.marketplace, getAccounts(context));
      const accountAttempts = [];
      let lastError = null;

      for (let index = 0; index < orderedAccounts.length; index += 1) {
        const account = orderedAccounts[index];
        const username = normalizeString(account?.username);
        const attemptStartedAt = now();

        try {
          const normalized = await fetchHangveNormalizedProduct({
            account,
            context,
            signal,
            login,
            fetchProduct,
            getCachedSession,
            setCachedSession,
            invalidateCachedSession
          });
          const canonical = mapToCanonical(normalized, context);
          const payload = serializePayload(canonical);
          const incompleteReasons = getPayloadIncompleteReasons(payload);
          const complete = incompleteReasons.length === 0;
          const durationMs = now() - attemptStartedAt;

          recordAccountResult({
            marketplace: context.marketplace,
            username,
            durationMs,
            success: true,
            complete
          });

          accountAttempts.push({
            attempt: index + 1,
            usernameMasked: maskHangveUsername(username),
            success: complete,
            message: complete
              ? "Hangve account succeeded"
              : `Hangve incomplete payload: ${incompleteReasons.join(", ")}`,
            durationMs
          });

          if (complete) {
            return {
              canonical,
              accountAttempts
            };
          }

          lastError = new Error(`Hangve incomplete payload: ${incompleteReasons.join(", ")}`);
        } catch (error) {
          const durationMs = now() - attemptStartedAt;
          recordAccountResult({
            marketplace: context.marketplace,
            username,
            durationMs,
            success: false,
            complete: false
          });

          accountAttempts.push({
            attempt: index + 1,
            usernameMasked: maskHangveUsername(username),
            success: false,
            message: error.message,
            durationMs
          });

          if (isAbortError(error)) {
            error.accountAttempts = accountAttempts;
            throw error;
          }

          lastError = error;
        }
      }

      const error = lastError ?? new Error("Hangve account rotation exhausted");
      error.accountAttempts = accountAttempts;
      throw error;
    }
  };
}

module.exports = {
  ...createHangveProvider(),
  createHangveProvider,
  fetchHangveNormalizedProduct,
  getHangveLookupUrl
};
