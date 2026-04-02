const { PROVIDER_GUARD_MODE, getProviderGuardSettings } = require("../config");
const { normalizeString } = require("./product");

const ADAPTIVE_PROVIDER_GUARD_STATE = new Map();

function getAdaptiveGuardState(providerName) {
  const key = normalizeString(providerName);
  if (!ADAPTIVE_PROVIDER_GUARD_STATE.has(key)) {
    ADAPTIVE_PROVIDER_GUARD_STATE.set(key, {
      inflight: 0,
      nextAllowedAt: 0,
      cooldownUntil: 0,
      consecutiveFailures: 0
    });
  }

  return ADAPTIVE_PROVIDER_GUARD_STATE.get(key);
}

function resetProviderExecutionGuardState() {
  ADAPTIVE_PROVIDER_GUARD_STATE.clear();
}

function createNoopProviderExecutionGuard() {
  return Object.freeze({
    mode: "off",
    beforeAttempt() {
      return {
        allowed: true,
        release() {}
      };
    },
    afterAttempt() {},
    getProviderSnapshot() {
      return {};
    }
  });
}

function createAdaptiveProviderExecutionGuard({ now = Date.now } = {}) {
  return Object.freeze({
    mode: "adaptive",
    beforeAttempt({ providerName }) {
      const settings = getProviderGuardSettings(providerName);
      if (!settings.enabled) {
        return {
          allowed: true,
          release() {}
        };
      }

      const providerState = getAdaptiveGuardState(providerName);
      const currentTime = now();

      if (providerState.cooldownUntil > currentTime) {
        return {
          allowed: false,
          reason: `provider guard cooldown active for ${providerState.cooldownUntil - currentTime}ms`
        };
      }

      if (providerState.inflight >= settings.maxInflight) {
        return {
          allowed: false,
          reason: `provider guard max inflight ${settings.maxInflight} reached`
        };
      }

      if (providerState.nextAllowedAt > currentTime) {
        return {
          allowed: false,
          reason: `provider guard min interval active for ${providerState.nextAllowedAt - currentTime}ms`
        };
      }

      providerState.inflight += 1;
      providerState.nextAllowedAt = currentTime + settings.minIntervalMs;

      let released = false;

      return {
        allowed: true,
        release() {
          if (released) {
            return;
          }

          released = true;
          providerState.inflight = Math.max(0, providerState.inflight - 1);
        }
      };
    },
    afterAttempt({ providerName, success }) {
      const settings = getProviderGuardSettings(providerName);
      if (!settings.enabled) {
        return;
      }

      const providerState = getAdaptiveGuardState(providerName);

      if (success) {
        providerState.consecutiveFailures = 0;
        return;
      }

      providerState.consecutiveFailures += 1;

      if (providerState.consecutiveFailures >= settings.failureThreshold) {
        providerState.cooldownUntil = now() + settings.cooldownMs;
        providerState.consecutiveFailures = 0;
      }
    },
    getProviderSnapshot(providerName) {
      const settings = getProviderGuardSettings(providerName);
      const providerState = getAdaptiveGuardState(providerName);
      const currentTime = now();

      return {
        mode: "adaptive",
        enabled: settings.enabled,
        inflight: providerState.inflight,
        nextAllowedInMs: Math.max(0, providerState.nextAllowedAt - currentTime),
        cooldownRemainingMs: Math.max(0, providerState.cooldownUntil - currentTime),
        consecutiveFailures: providerState.consecutiveFailures
      };
    }
  });
}

const DEFAULT_PROVIDER_EXECUTION_GUARD =
  PROVIDER_GUARD_MODE === "off"
    ? createNoopProviderExecutionGuard()
    : createAdaptiveProviderExecutionGuard();

function createProviderExecutionGuard({ mode = PROVIDER_GUARD_MODE, now = Date.now } = {}) {
  if (mode === "off") {
    return createNoopProviderExecutionGuard();
  }

  if (mode === "adaptive") {
    return createAdaptiveProviderExecutionGuard({ now });
  }

  throw new Error(`Unsupported provider guard mode: ${mode}`);
}

module.exports = {
  DEFAULT_PROVIDER_EXECUTION_GUARD,
  createAdaptiveProviderExecutionGuard,
  createNoopProviderExecutionGuard,
  createProviderExecutionGuard,
  resetProviderExecutionGuardState
};
