const { HANGVE_SESSION_TTL_MS } = require("../config");
const { normalizeString } = require("../core/product");

const HANGVE_SESSION_CACHE = new Map();
const HANGVE_ACCOUNT_STATS = new Map();
const HANGVE_EWMA_ALPHA = 0.35;

function buildHangveStatsKey(marketplace, username) {
  const normalizedMarketplace = normalizeString(marketplace);
  const normalizedUsername = normalizeString(username);
  return normalizedMarketplace && normalizedUsername
    ? `${normalizedMarketplace}::${normalizedUsername}`
    : "";
}

function getEmptyHangveAccountStats() {
  return {
    attempts: 0,
    successCount: 0,
    completeCount: 0,
    incompleteCount: 0,
    failureCount: 0,
    ewmaDurationMs: null,
    lastDurationMs: null,
    lastUpdatedAt: 0
  };
}

function getHangveCachedSession(username, now = Date.now()) {
  const normalizedUsername = normalizeString(username);
  if (!normalizedUsername) {
    return null;
  }

  const entry = HANGVE_SESSION_CACHE.get(normalizedUsername);
  if (!entry) {
    return null;
  }

  if (entry.expiresAt <= now) {
    HANGVE_SESSION_CACHE.delete(normalizedUsername);
    return null;
  }

  return entry.session;
}

function setHangveCachedSession(username, session, now = Date.now()) {
  const normalizedUsername = normalizeString(username);

  if (!normalizedUsername || !session?.token || !session?.customer?.id) {
    return null;
  }

  const entry = {
    session: {
      token: session.token,
      customer: session.customer
    },
    expiresAt: now + HANGVE_SESSION_TTL_MS
  };

  HANGVE_SESSION_CACHE.set(normalizedUsername, entry);
  return entry.session;
}

function invalidateHangveCachedSession(username) {
  const normalizedUsername = normalizeString(username);
  if (!normalizedUsername) {
    return;
  }

  HANGVE_SESSION_CACHE.delete(normalizedUsername);
}

function getHangveAccountStats(marketplace, username) {
  const key = buildHangveStatsKey(marketplace, username);
  if (!key) {
    return getEmptyHangveAccountStats();
  }

  return HANGVE_ACCOUNT_STATS.get(key) ?? getEmptyHangveAccountStats();
}

function recordHangveAccountResult({
  marketplace,
  username,
  durationMs,
  success = false,
  complete = false,
  now = Date.now()
} = {}) {
  const key = buildHangveStatsKey(marketplace, username);
  if (!key) {
    return getEmptyHangveAccountStats();
  }

  const current = HANGVE_ACCOUNT_STATS.get(key) ?? getEmptyHangveAccountStats();
  const safeDurationMs = Number.isFinite(durationMs) && durationMs >= 0 ? durationMs : null;
  const next = {
    attempts: current.attempts + 1,
    successCount: current.successCount + (success ? 1 : 0),
    completeCount: current.completeCount + (complete ? 1 : 0),
    incompleteCount: current.incompleteCount + (success && !complete ? 1 : 0),
    failureCount: current.failureCount + (!success ? 1 : 0),
    ewmaDurationMs:
      safeDurationMs === null
        ? current.ewmaDurationMs
        : current.ewmaDurationMs === null
          ? safeDurationMs
          : current.ewmaDurationMs * (1 - HANGVE_EWMA_ALPHA) + safeDurationMs * HANGVE_EWMA_ALPHA,
    lastDurationMs: safeDurationMs,
    lastUpdatedAt: now
  };

  HANGVE_ACCOUNT_STATS.set(key, next);
  return next;
}

function getHangveAccountScore(stats) {
  if (!stats || stats.attempts === 0) {
    return Number.NEGATIVE_INFINITY;
  }

  const completeRate = stats.completeCount / stats.attempts;
  const successRate = stats.successCount / stats.attempts;
  const failureRate = stats.failureCount / stats.attempts;
  const incompleteRate = stats.incompleteCount / stats.attempts;
  const latencyPenalty = (stats.ewmaDurationMs ?? 8000) / 1000;

  return completeRate * 100 + successRate * 10 - failureRate * 30 - incompleteRate * 20 - latencyPenalty;
}

function rankHangveAccounts(marketplace, accounts = []) {
  return [...accounts]
    .map((account, index) => ({
      account,
      index,
      stats: getHangveAccountStats(marketplace, account?.username)
    }))
    .sort((left, right) => {
      const scoreDiff = getHangveAccountScore(right.stats) - getHangveAccountScore(left.stats);
      if (scoreDiff !== 0) {
        return scoreDiff;
      }

      const leftLatency = left.stats.ewmaDurationMs ?? Number.POSITIVE_INFINITY;
      const rightLatency = right.stats.ewmaDurationMs ?? Number.POSITIVE_INFINITY;
      if (leftLatency !== rightLatency) {
        return leftLatency - rightLatency;
      }

      return left.index - right.index;
    })
    .map((entry) => entry.account);
}

function resetHangveRuntimeState() {
  HANGVE_SESSION_CACHE.clear();
  HANGVE_ACCOUNT_STATS.clear();
}

module.exports = {
  getHangveAccountStats,
  getHangveCachedSession,
  invalidateHangveCachedSession,
  rankHangveAccounts,
  recordHangveAccountResult,
  resetHangveRuntimeState,
  setHangveCachedSession
};
