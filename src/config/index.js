const { loadOptionalJsonFile } = require("./files");

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

const SERVICE_PORT = toPositiveInt(process.env.PORT, 3000);
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

module.exports = {
  ALLOWED_SOURCE_TYPES,
  HANGVE_ACCOUNTS,
  PANDAMALL_ACCOUNTS,
  PROVIDER_CHAINS,
  PROVIDER_START_DELAYS_MS,
  PROVIDER_TIMEOUTS_MS,
  SERVICE_PORT,
  getProviderAccounts,
  getProviderChain,
  getProviderStartDelayMs,
  getProviderTimeoutMs
};
