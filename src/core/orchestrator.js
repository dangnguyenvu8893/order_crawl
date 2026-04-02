const {
  ORCHESTRATOR_REQUEST_DEADLINE_MS,
  ORCHESTRATOR_RESULT_CACHE_TTL_MS,
  getProviderChain,
  getProviderStartDelayMs
} = require("../config");
const { getIncompleteReasons, isCompleteBackendPayload, serializeBackendPayload } = require("../mappers/backend-payload");
const { PROVIDERS } = require("../providers");
const {
  clearInflightOrchestratorRequest,
  getCachedOrchestratorResult,
  getInflightOrchestratorRequest,
  setCachedOrchestratorResult,
  setInflightOrchestratorRequest
} = require("./orchestrator-state");
const { DEFAULT_PROVIDER_EXECUTION_GUARD } = require("./provider-guard");
const { HttpError, isAbortError } = require("./errors");
const { buildProductContextFromInput } = require("./url-resolver");

function buildDebugMeta(context, attempts, providerUsed, startedAt, extra = {}) {
  return {
    marketplace: context.marketplace,
    inputUrl: context.inputUrl,
    originalInput: context.originalInput,
    providerUsed,
    attempts,
    fallbackTriggered: attempts.length > 1,
    failureReasons: attempts.filter((attempt) => !attempt.success).map((attempt) => attempt.message),
    latencyMs: Date.now() - startedAt,
    resolver: context.resolution
      ? {
          method: context.resolution.method,
          extractedFromText: context.resolution.extractedFromText,
          networkAttempted: context.resolution.networkAttempted
        }
      : undefined,
    ...extra
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

function buildBlockedAttempt(providerName, attemptStartedAt, reason) {
  return {
    success: false,
    payload: null,
    attempt: {
      provider: providerName,
      success: false,
      message: reason,
      durationMs: Date.now() - attemptStartedAt
    }
  };
}

function startProviderAttempt(
  context,
  providerName,
  provider,
  startDelayMs,
  requestSignal,
  providerExecutionGuard
) {
  const controller = new AbortController();
  const task = (async () => {
    await delay(startDelayMs, controller.signal);

    const attemptStartedAt = Date.now();
    const effectiveSignal = requestSignal ? AbortSignal.any([controller.signal, requestSignal]) : controller.signal;
    let guardLease = null;

    try {
      guardLease = await providerExecutionGuard.beforeAttempt({
        providerName,
        context,
        signal: effectiveSignal
      });

      if (!guardLease?.allowed) {
        return buildBlockedAttempt(providerName, attemptStartedAt, guardLease?.reason ?? "provider guard blocked attempt");
      }

      const result = await provider.resolveProduct(context, {
        signal: effectiveSignal
      });
      const payload = serializeBackendPayload(result.canonical);
      const attemptResult = buildAttemptResult(providerName, attemptStartedAt, payload, result.accountAttempts);
      providerExecutionGuard.afterAttempt({
        providerName,
        context,
        success: attemptResult.success,
        durationMs: attemptResult.attempt?.durationMs ?? 0
      });
      return attemptResult;
    } catch (error) {
      if (isAbortError(error)) {
        return {
          success: false,
          payload: null,
          attempt: null,
          aborted: true
        };
      }

      const failedAttempt = buildFailedAttempt(providerName, attemptStartedAt, error);
      providerExecutionGuard.afterAttempt({
        providerName,
        context,
        success: false,
        durationMs: failedAttempt.attempt?.durationMs ?? 0,
        error
      });
      return failedAttempt;
    } finally {
      guardLease?.release?.();
    }
  })();

  return {
    providerName,
    controller,
    task
  };
}

function clonePayload(payload) {
  return {
    ...payload,
    images: [...(payload?.images ?? [])],
    rangePrices: [...(payload?.rangePrices ?? [])],
    skuProperty: [...(payload?.skuProperty ?? [])],
    sku: [...(payload?.sku ?? [])]
  };
}

function finalizePayloadResult(context, result, { debug = false, startedAt = Date.now(), extraMeta = {} } = {}) {
  const payload = clonePayload(result.payload);

  if (debug) {
    payload._meta = buildDebugMeta(context, result.attempts, result.providerUsed, startedAt, extraMeta);
  }

  return payload;
}

async function executeTransform(
  context,
  {
    providers = PROVIDERS,
    providerStartDelaysMs = {},
    requestDeadlineMs,
    providerExecutionGuard = DEFAULT_PROVIDER_EXECUTION_GUARD
  } = {}
) {
  const startedAt = Date.now();
  const attempts = [];
  const activeProviders = [];
  const deadlineMs = Number.isFinite(requestDeadlineMs) && requestDeadlineMs > 0
    ? requestDeadlineMs
    : ORCHESTRATOR_REQUEST_DEADLINE_MS;
  const requestController = new AbortController();

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
        providerStartDelaysMs[providerName] ?? getProviderStartDelayMs(context.marketplace, providerName),
        requestController.signal,
        providerExecutionGuard
      )
    );
  }

  if (activeProviders.length === 0) {
    throw new HttpError("No provider is configured for this marketplace", 500, "provider_not_configured");
  }

  return new Promise((resolve, reject) => {
    let completedCount = 0;
    let finished = false;
    const deadlineTimer = setTimeout(() => {
      if (finished) {
        return;
      }

      finished = true;
      requestController.abort(new DOMException("Aborted", "AbortError"));
      for (const activeProvider of activeProviders) {
        activeProvider.controller.abort();
      }

      const error = new HttpError(
        "Request deadline exceeded before any provider returned a complete payload",
        502,
        "provider_deadline_exceeded",
        buildDebugMeta(context, attempts, "", startedAt, {
          deadlineMs,
          deadlineHit: true
        })
      );
      reject(error);
    }, deadlineMs);

    function cleanup() {
      clearTimeout(deadlineTimer);
    }

    function finalizeFailure() {
      if (finished) {
        return;
      }

      finished = true;
      cleanup();
      const error = new HttpError("Could not fetch product data from any provider", 502, "provider_chain_failed");
      error.details = buildDebugMeta(context, attempts, "", startedAt, {
        deadlineMs,
        deadlineHit: false
      });
      reject(error);
    }

    function finalizeSuccess(payload, providerName) {
      if (finished) {
        return;
      }

      finished = true;
      cleanup();
      for (const activeProvider of activeProviders) {
        if (activeProvider.providerName !== providerName) {
          activeProvider.controller.abort();
        }
      }

      resolve({
        payload,
        providerUsed: providerName,
        attempts
      });
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

async function transformProductFromUrl(
  url,
  {
    debug = false,
    providers = PROVIDERS,
    providerStartDelaysMs = {},
    requestDeadlineMs = ORCHESTRATOR_REQUEST_DEADLINE_MS,
    resultCacheTtlMs = ORCHESTRATOR_RESULT_CACHE_TTL_MS,
    providerExecutionGuard = DEFAULT_PROVIDER_EXECUTION_GUARD,
    buildContext = buildProductContextFromInput
  } = {}
) {
  const context = await buildContext(url);
  const startedAt = Date.now();
  const cacheKey = context.canonicalUrl;

  const cachedResult = getCachedOrchestratorResult(cacheKey, startedAt);
  if (cachedResult) {
    return finalizePayloadResult(context, cachedResult, {
      debug,
      startedAt,
      extraMeta: {
        cacheHit: true,
        sharedRequest: false
      }
    });
  }

  const inflightRequest = getInflightOrchestratorRequest(cacheKey);
  if (inflightRequest) {
    const sharedResult = await inflightRequest;
    return finalizePayloadResult(context, sharedResult, {
      debug,
      startedAt,
      extraMeta: {
        cacheHit: false,
        sharedRequest: true
      }
    });
  }

  const execution = executeTransform(context, {
    providers,
    providerStartDelaysMs,
    requestDeadlineMs,
    providerExecutionGuard
  })
    .then((result) => {
      setCachedOrchestratorResult(cacheKey, result, Date.now(), resultCacheTtlMs);
      return result;
    })
    .finally(() => {
      clearInflightOrchestratorRequest(cacheKey);
    });

  setInflightOrchestratorRequest(cacheKey, execution);

  const result = await execution;
  return finalizePayloadResult(context, result, {
    debug,
    startedAt,
    extraMeta: {
      cacheHit: false,
      sharedRequest: false
    }
  });
}

module.exports = {
  executeTransform,
  transformProductFromUrl
};
