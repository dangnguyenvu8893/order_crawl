const { ORCHESTRATOR_RESULT_CACHE_TTL_MS } = require("../config");
const { normalizeString } = require("./product");

const ORCHESTRATOR_RESULT_CACHE = new Map();
const ORCHESTRATOR_INFLIGHT_REQUESTS = new Map();

function getOrchestratorCacheKey(canonicalUrl) {
  return normalizeString(canonicalUrl);
}

function getCachedOrchestratorResult(canonicalUrl, now = Date.now()) {
  const cacheKey = getOrchestratorCacheKey(canonicalUrl);
  if (!cacheKey) {
    return null;
  }

  const entry = ORCHESTRATOR_RESULT_CACHE.get(cacheKey);
  if (!entry) {
    return null;
  }

  if (entry.expiresAt <= now) {
    ORCHESTRATOR_RESULT_CACHE.delete(cacheKey);
    return null;
  }

  return entry.result;
}

function setCachedOrchestratorResult(
  canonicalUrl,
  result,
  now = Date.now(),
  ttlMs = ORCHESTRATOR_RESULT_CACHE_TTL_MS
) {
  const cacheKey = getOrchestratorCacheKey(canonicalUrl);
  if (!cacheKey || !result || ttlMs <= 0) {
    return;
  }

  ORCHESTRATOR_RESULT_CACHE.set(cacheKey, {
    result,
    expiresAt: now + ttlMs
  });
}

function getInflightOrchestratorRequest(canonicalUrl) {
  const cacheKey = getOrchestratorCacheKey(canonicalUrl);
  return cacheKey ? ORCHESTRATOR_INFLIGHT_REQUESTS.get(cacheKey) ?? null : null;
}

function setInflightOrchestratorRequest(canonicalUrl, promise) {
  const cacheKey = getOrchestratorCacheKey(canonicalUrl);
  if (!cacheKey || !promise) {
    return;
  }

  ORCHESTRATOR_INFLIGHT_REQUESTS.set(cacheKey, promise);
}

function clearInflightOrchestratorRequest(canonicalUrl) {
  const cacheKey = getOrchestratorCacheKey(canonicalUrl);
  if (!cacheKey) {
    return;
  }

  ORCHESTRATOR_INFLIGHT_REQUESTS.delete(cacheKey);
}

function resetOrchestratorRuntimeState() {
  ORCHESTRATOR_RESULT_CACHE.clear();
  ORCHESTRATOR_INFLIGHT_REQUESTS.clear();
}

module.exports = {
  clearInflightOrchestratorRequest,
  getCachedOrchestratorResult,
  getInflightOrchestratorRequest,
  getOrchestratorCacheKey,
  resetOrchestratorRuntimeState,
  setCachedOrchestratorResult,
  setInflightOrchestratorRequest
};
