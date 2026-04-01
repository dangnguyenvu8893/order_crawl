const { getProviderChain, getProviderStartDelayMs } = require("../config");
const { PROVIDERS } = require("../providers");
const { getIncompleteReasons, isCompleteBackendPayload, serializeBackendPayload } = require("../mappers/backend-payload");
const { HttpError, isAbortError } = require("./errors");
const { parseProductUrl } = require("./url");

function buildDebugMeta(context, attempts, providerUsed, startedAt) {
  return {
    marketplace: context.marketplace,
    providerUsed,
    attempts,
    fallbackTriggered: attempts.length > 1,
    failureReasons: attempts.filter((attempt) => !attempt.success).map((attempt) => attempt.message),
    latencyMs: Date.now() - startedAt
  };
}

function delay(ms, signal) {
  if (!ms || ms <= 0) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    function onAbort() {
      cleanup();
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    }

    function cleanup() {
      clearTimeout(timeoutId);
      signal?.removeEventListener?.("abort", onAbort);
    }

    if (signal?.aborted) {
      onAbort();
      return;
    }

    signal?.addEventListener?.("abort", onAbort, { once: true });
  });
}

function buildAttemptResult(providerName, attemptStartedAt, payload, accountAttempts = []) {
  const incompleteReasons = getIncompleteReasons(payload);
  const success = incompleteReasons.length === 0;
  const attempt = {
    provider: providerName,
    success,
    message: success ? "payload complete" : `incomplete payload: ${incompleteReasons.join(", ")}`,
    durationMs: Date.now() - attemptStartedAt
  };

  if (Array.isArray(accountAttempts) && accountAttempts.length > 0) {
    attempt.accountAttempts = accountAttempts;
  }

  return {
    success,
    payload,
    attempt
  };
}

function buildFailedAttempt(providerName, attemptStartedAt, error) {
  const attempt = {
    provider: providerName,
    success: false,
    message: error.message,
    durationMs: Date.now() - attemptStartedAt
  };

  if (Array.isArray(error.accountAttempts) && error.accountAttempts.length > 0) {
    attempt.accountAttempts = error.accountAttempts;
  }

  return {
    success: false,
    payload: null,
    attempt
  };
}

function startProviderAttempt(context, providerName, provider, startDelayMs) {
  const controller = new AbortController();
  const task = (async () => {
    await delay(startDelayMs, controller.signal);

    const attemptStartedAt = Date.now();

    try {
      const result = await provider.resolveProduct(context, {
        signal: controller.signal
      });
      const payload = serializeBackendPayload(result.canonical);
      return buildAttemptResult(providerName, attemptStartedAt, payload, result.accountAttempts);
    } catch (error) {
      if (isAbortError(error)) {
        return {
          success: false,
          payload: null,
          attempt: null,
          aborted: true
        };
      }

      return buildFailedAttempt(providerName, attemptStartedAt, error);
    }
  })();

  return {
    providerName,
    controller,
    task
  };
}

async function transformProductFromUrl(
  url,
  {
    debug = false,
    providers = PROVIDERS,
    providerStartDelaysMs = {}
  } = {}
) {
  const context = parseProductUrl(url);
  const startedAt = Date.now();
  const attempts = [];
  const activeProviders = [];

  for (const providerName of getProviderChain(context.marketplace)) {
    const provider = providers[providerName];
    if (!provider || typeof provider.resolveProduct !== "function") {
      continue;
    }

    activeProviders.push(
      startProviderAttempt(
        context,
        providerName,
        provider,
        providerStartDelaysMs[providerName] ?? getProviderStartDelayMs(context.marketplace, providerName)
      )
    );
  }

  if (activeProviders.length === 0) {
    throw new HttpError("No provider is configured for this marketplace", 500, "provider_not_configured");
  }

  return new Promise((resolve, reject) => {
    let completedCount = 0;
    let finished = false;

    function finalizeFailure() {
      if (finished) {
        return;
      }

      finished = true;
      const error = new HttpError("Could not fetch product data from any provider", 502, "provider_chain_failed");
      if (debug) {
        error.details = buildDebugMeta(context, attempts, "", startedAt);
      }
      reject(error);
    }

    function finalizeSuccess(payload, providerName) {
      if (finished) {
        return;
      }

      finished = true;
      for (const activeProvider of activeProviders) {
        if (activeProvider.providerName !== providerName) {
          activeProvider.controller.abort();
        }
      }

      if (debug) {
        payload._meta = buildDebugMeta(context, attempts, providerName, startedAt);
      }

      resolve(payload);
    }

    for (const activeProvider of activeProviders) {
      activeProvider.task
        .then((result) => {
          if (finished) {
            return;
          }

          completedCount += 1;

          if (result.attempt) {
            attempts.push(result.attempt);
          }

          if (result.success && result.payload && isCompleteBackendPayload(result.payload)) {
            finalizeSuccess(result.payload, activeProvider.providerName);
            return;
          }

          if (completedCount === activeProviders.length) {
            finalizeFailure();
          }
        })
        .catch((error) => {
          if (finished) {
            return;
          }

          completedCount += 1;

          if (!isAbortError(error)) {
            attempts.push({
              provider: activeProvider.providerName,
              success: false,
              message: error.message,
              durationMs: 0
            });
          }

          if (completedCount === activeProviders.length) {
            finalizeFailure();
          }
        });
    }
  });
}

module.exports = {
  transformProductFromUrl
};
