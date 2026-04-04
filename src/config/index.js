const { loadOptionalJsonFile } = require("./files");
const { loadTrackingCredentials } = require("./tracking");

const ALLOWED_SOURCE_TYPES = Object.freeze(["1688", "taobao", "tmall"]);
const PROVIDER_CHAINS = Object.freeze({
  "1688": Object.freeze(["gianghuy", "vipomall", "hangve", "pandamall"]),
  taobao: Object.freeze(["gianghuy", "vipomall", "hangve", "pandamall"]),
  tmall: Object.freeze(["vipomall", "hangve", "pandamall"])
});

function toPositiveInt(value, fallback) {
  const normalized = Number.parseInt(value, 10);
  return Number.isFinite(normalized) && normalized > 0 ? normalized : fallback;
}

function toNonNegativeInt(value, fallback) {
  const normalized = Number.parseInt(value, 10);
  return Number.isFinite(normalized) && normalized >= 0 ? normalized : fallback;
}

function toBoolean(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  if (typeof value === "boolean") {
    return value;
  }

  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
}

function toMode(value, fallback) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return normalized || fallback;
}

function normalizeAccountEntries(rawAccounts, userKey) {
  const accountsInput =
    rawAccounts && typeof rawAccounts === "object" && !Array.isArray(rawAccounts)
      ? rawAccounts.accounts
      : rawAccounts;

  if (!Array.isArray(accountsInput)) {
    return [];
  }

  return accountsInput
    .filter((account) => account && typeof account === "object")
    .map((account) => ({
      [userKey]: String(account[userKey] ?? "").trim(),
      password: String(account.password ?? "").trim()
    }))
    .filter((account) => account[userKey] && account.password);
}

function buildSingletonAccount(credentials, userKey, envUserKey, envPasswordKey, aliases = []) {
  const username =
    process.env[envUserKey] ??
    credentials[userKey] ??
    aliases.map((alias) => credentials[alias]).find(Boolean) ??
    "";
  const password = process.env[envPasswordKey] ?? credentials.password ?? "";

  if (!String(username).trim() || !String(password).trim()) {
    return [];
  }

  return [
    {
      [userKey]: String(username).trim(),
      password: String(password).trim()
    }
  ];
}

function buildProviderGuardSettings(prefix, defaults) {
  return Object.freeze({
    enabled: toBoolean(process.env[`${prefix}_ENABLED`], defaults.enabled),
    maxInflight: toPositiveInt(process.env[`${prefix}_MAX_INFLIGHT`], defaults.maxInflight),
    minIntervalMs: toNonNegativeInt(process.env[`${prefix}_MIN_INTERVAL_MS`], defaults.minIntervalMs),
    failureThreshold: toPositiveInt(process.env[`${prefix}_FAILURE_THRESHOLD`], defaults.failureThreshold),
    cooldownMs: toNonNegativeInt(process.env[`${prefix}_COOLDOWN_MS`], defaults.cooldownMs)
  });
}

const SERVICE_PORT = toPositiveInt(process.env.PORT, 3000);
const HANGVE_SESSION_TTL_MS = toPositiveInt(process.env.HANGVE_SESSION_TTL_MS, 10 * 60 * 1000);
const TRACKING_TIMEOUT_MS = toPositiveInt(process.env.TRACKING_TIMEOUT_MS, 60 * 1000);
const TRACKING_MAX_INFLIGHT = toPositiveInt(process.env.TRACKING_MAX_INFLIGHT, 2);
const TRACKING_BROWSER_HEADLESS = toBoolean(process.env.TRACKING_BROWSER_HEADLESS, true);
const TRACKING_BROWSER_EXECUTABLE_PATH = String(process.env.TRACKING_BROWSER_EXECUTABLE_PATH ?? "").trim();
const ORCHESTRATOR_RESULT_CACHE_TTL_MS = toNonNegativeInt(
  process.env.CRAWL_RESULT_CACHE_TTL_MS,
  30 * 1000
);
const ORCHESTRATOR_REQUEST_DEADLINE_MS = toPositiveInt(process.env.CRAWL_REQUEST_DEADLINE_MS, 9 * 1000);
const URL_RESOLVER_TIMEOUT_MS = toPositiveInt(process.env.CRAWL_URL_RESOLVER_TIMEOUT_MS, 2500);
const URL_RESOLVER_MAX_RESPONSE_BYTES = toPositiveInt(
  process.env.CRAWL_URL_RESOLVER_MAX_RESPONSE_BYTES,
  256 * 1024
);
const PROVIDER_GUARD_MODE = toMode(process.env.CRAWL_PROVIDER_GUARD_MODE, "adaptive");
const PROVIDER_GUARD_SETTINGS = Object.freeze({
  gianghuy: buildProviderGuardSettings("CRAWL_GUARD_GIANGHUY", {
    enabled: true,
    maxInflight: 12,
    minIntervalMs: 0,
    failureThreshold: 8,
    cooldownMs: 1000
  }),
  vipomall: buildProviderGuardSettings("CRAWL_GUARD_VIPOMALL", {
    enabled: true,
    maxInflight: 10,
    minIntervalMs: 0,
    failureThreshold: 8,
    cooldownMs: 1000
  }),
  hangve: buildProviderGuardSettings("CRAWL_GUARD_HANGVE", {
    enabled: true,
    maxInflight: 2,
    minIntervalMs: 250,
    failureThreshold: 4,
    cooldownMs: 5000
  }),
  pandamall: buildProviderGuardSettings("CRAWL_GUARD_PANDAMALL", {
    enabled: true,
    maxInflight: 4,
    minIntervalMs: 100,
    failureThreshold: 6,
    cooldownMs: 3000
  })
});
const PROVIDER_TIMEOUTS_MS = Object.freeze({
  gianghuy: toPositiveInt(process.env.CRAWL_GIANGHUY_TIMEOUT_MS, 15000),
  vipomall: toPositiveInt(process.env.CRAWL_VIPOMALL_TIMEOUT_MS, 10000),
  hangve: toPositiveInt(process.env.CRAWL_HANGVE_TIMEOUT_MS, 25000),
  pandamall: toPositiveInt(process.env.CRAWL_PANDAMALL_TIMEOUT_MS, 30000)
});
const PROVIDER_START_DELAYS_MS = Object.freeze({
  "1688": Object.freeze({
    gianghuy: toNonNegativeInt(process.env.CRAWL_1688_GIANGHUY_DELAY_MS, 0),
    vipomall: toNonNegativeInt(process.env.CRAWL_1688_VIPOMALL_DELAY_MS, 150),
    hangve: toNonNegativeInt(process.env.CRAWL_1688_HANGVE_DELAY_MS, 500),
    pandamall: toNonNegativeInt(process.env.CRAWL_1688_PANDAMALL_DELAY_MS, 1400)
  }),
  taobao: Object.freeze({
    gianghuy: toNonNegativeInt(process.env.CRAWL_TAOBAO_GIANGHUY_DELAY_MS, 0),
    vipomall: toNonNegativeInt(process.env.CRAWL_TAOBAO_VIPOMALL_DELAY_MS, 150),
    hangve: toNonNegativeInt(process.env.CRAWL_TAOBAO_HANGVE_DELAY_MS, 500),
    pandamall: toNonNegativeInt(process.env.CRAWL_TAOBAO_PANDAMALL_DELAY_MS, 1400)
  }),
  tmall: Object.freeze({
    vipomall: toNonNegativeInt(process.env.CRAWL_TMALL_VIPOMALL_DELAY_MS, 0),
    hangve: toNonNegativeInt(process.env.CRAWL_TMALL_HANGVE_DELAY_MS, 300),
    pandamall: toNonNegativeInt(process.env.CRAWL_TMALL_PANDAMALL_DELAY_MS, 1200)
  })
});

const { data: hangveCredentials } = loadOptionalJsonFile("hangve.credentials.json");
const { data: hangveAccountsRaw } = loadOptionalJsonFile("hangve.accounts.json");
const { data: pandamallCredentials } = loadOptionalJsonFile("pandamall.credentials.json");
const { data: pandamallAccountsRaw } = loadOptionalJsonFile("pandamall.accounts.json");
const TRACKING_CREDENTIALS = Object.freeze(loadTrackingCredentials());
const TRACKING_17TRACK_PHONE_NUMBER = TRACKING_CREDENTIALS.phoneNumber;

const HANGVE_ACCOUNTS = Object.freeze(
  normalizeAccountEntries(hangveAccountsRaw, "username").length > 0
    ? normalizeAccountEntries(hangveAccountsRaw, "username")
    : buildSingletonAccount(
        hangveCredentials,
        "username",
        "HANGVE_USERNAME",
        "HANGVE_PASSWORD",
        ["phone"]
      )
);

const PANDAMALL_ACCOUNTS = Object.freeze(
  normalizeAccountEntries(pandamallAccountsRaw, "phone").length > 0
    ? normalizeAccountEntries(pandamallAccountsRaw, "phone")
    : buildSingletonAccount(
        pandamallCredentials,
        "phone",
        "PANDAMALL_PHONE",
        "PANDAMALL_PASSWORD"
      )
);

function getProviderChain(sourceType) {
  return [...(PROVIDER_CHAINS[sourceType] ?? [])];
}

function getProviderTimeoutMs(providerName) {
  return PROVIDER_TIMEOUTS_MS[providerName] ?? 15000;
}

function getProviderStartDelayMs(sourceType, providerName) {
  return PROVIDER_START_DELAYS_MS[sourceType]?.[providerName] ?? 0;
}

function getProviderAccounts(providerName) {
  if (providerName === "hangve") {
    return HANGVE_ACCOUNTS.map((account) => ({ ...account }));
  }

  if (providerName === "pandamall") {
    return PANDAMALL_ACCOUNTS.map((account) => ({ ...account }));
  }

  return [];
}

function getProviderGuardSettings(providerName) {
  return PROVIDER_GUARD_SETTINGS[providerName] ?? {
    enabled: false,
    maxInflight: 1,
    minIntervalMs: 0,
    failureThreshold: 1,
    cooldownMs: 0
  };
}

module.exports = {
  ALLOWED_SOURCE_TYPES,
  HANGVE_ACCOUNTS,
  HANGVE_SESSION_TTL_MS,
  ORCHESTRATOR_REQUEST_DEADLINE_MS,
  ORCHESTRATOR_RESULT_CACHE_TTL_MS,
  PANDAMALL_ACCOUNTS,
  PROVIDER_CHAINS,
  PROVIDER_GUARD_MODE,
  PROVIDER_GUARD_SETTINGS,
  PROVIDER_START_DELAYS_MS,
  PROVIDER_TIMEOUTS_MS,
  SERVICE_PORT,
  TRACKING_17TRACK_PHONE_NUMBER,
  TRACKING_BROWSER_EXECUTABLE_PATH,
  TRACKING_BROWSER_HEADLESS,
  TRACKING_MAX_INFLIGHT,
  TRACKING_TIMEOUT_MS,
  URL_RESOLVER_MAX_RESPONSE_BYTES,
  URL_RESOLVER_TIMEOUT_MS,
  getProviderAccounts,
  getProviderChain,
  getProviderGuardSettings,
  getProviderStartDelayMs,
  getProviderTimeoutMs
};
