const { getConfig } = require("./config");
const { createSignContext, generateSignFromContext } = require("./generate-sign");

const GIANGHUY_SIGNING_CONTEXT_CACHE = new Map();

function buildSigningContextCacheKey(config) {
  return [
    String(config?.accessKey ?? ""),
    String(config?.accessSecret ?? ""),
    String(config?.endUserId ?? ""),
    String(config?.url ?? ""),
    String(config?.apiBaseUrl ?? "")
  ].join("::");
}

function createGianghuySigningContext(config) {
  const signContext = createSignContext({
    accessKey: config.accessKey,
    accessSecret: config.accessSecret,
    url: config.url
  });

  return Object.freeze({
    config: Object.freeze({
      accessKey: config.accessKey,
      accessSecret: config.accessSecret,
      endUserId: config.endUserId,
      url: signContext.headerUrl,
      apiBaseUrl: config.apiBaseUrl
    }),
    baseHeaders: Object.freeze({
      accept: "application/json",
      "access-key": config.accessKey,
      "end-user-id": String(config.endUserId),
      url: signContext.headerUrl
    }),
    signContext: Object.freeze(signContext)
  });
}

function getGianghuySigningContext(overrides = {}) {
  const config = getConfig(overrides);
  const cacheKey = buildSigningContextCacheKey(config);

  let signingContext = GIANGHUY_SIGNING_CONTEXT_CACHE.get(cacheKey);
  if (!signingContext) {
    signingContext = createGianghuySigningContext(config);
    GIANGHUY_SIGNING_CONTEXT_CACHE.set(cacheKey, signingContext);
  }

  return signingContext;
}

function resetGianghuySigningContextCache() {
  GIANGHUY_SIGNING_CONTEXT_CACHE.clear();
}

function buildSignedHeaders(overrides = {}) {
  const signingContext = getGianghuySigningContext(overrides);
  const signMeta = generateSignFromContext(signingContext.signContext, overrides.timestamp);
  const headers = {
    ...signingContext.baseHeaders,
    "mona-id": signMeta.monaId,
    sign: signMeta.sign
  };

  return {
    config:
      overrides.timestamp === undefined
        ? signingContext.config
        : {
            ...signingContext.config,
            timestamp: overrides.timestamp
          },
    headers,
    signMeta
  };
}

async function signedGetJson(path, overrides = {}) {
  const { config, headers, signMeta } = buildSignedHeaders(overrides);
  const apiUrl = `${config.apiBaseUrl.replace(/\/+$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(apiUrl, {
    method: "GET",
    headers,
    signal: overrides.signal
  });

  const text = await response.text();
  let data;

  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }

  if (!response.ok) {
    const error = new Error(`Request failed with status ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return {
    request: {
      apiUrl,
      headers,
      signMeta: {
        monaId: signMeta.monaId,
        headerUrl: signMeta.headerUrl,
        signTarget: signMeta.signTarget,
        sign: signMeta.sign
      }
    },
    response: {
      status: response.status,
      data
    }
  };
}

module.exports = {
  buildSignedHeaders,
  buildSigningContextCacheKey,
  createGianghuySigningContext,
  getGianghuySigningContext,
  resetGianghuySigningContextCache,
  signedGetJson
};
