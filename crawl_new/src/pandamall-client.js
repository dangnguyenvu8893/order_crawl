const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PANDAMALL_CREDENTIALS_PATH = path.join(__dirname, "../config/pandamall.credentials.json");

function loadOptionalPandamallCredentials() {
  try {
    return JSON.parse(fs.readFileSync(PANDAMALL_CREDENTIALS_PATH, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") {
      return {};
    }

    throw error;
  }
}

const pandamallCredentials = loadOptionalPandamallCredentials();

const DEFAULT_PANDAMALL_CONFIG = {
  apiBaseUrl: "https://api.pandamall.vn",
  origin: "https://pandamall.vn",
  referer: "https://pandamall.vn/"
};

const DEFAULT_PANDAMALL_ACCOUNT = {
  phone: process.env.PANDAMALL_PHONE ?? pandamallCredentials.phone ?? "",
  password: process.env.PANDAMALL_PASSWORD ?? pandamallCredentials.password ?? ""
};

const PANDAMALL_PROVIDER_MAP = {
  "1688": "alibaba",
  alibaba: "alibaba",
  taobao: "taobao",
  tmall: "taobao"
};

function encodeBase64Url(bufferSource) {
  const buffer = Buffer.isBuffer(bufferSource)
    ? bufferSource
    : Buffer.from(bufferSource instanceof Uint8Array ? bufferSource : new Uint8Array(bufferSource));

  return buffer
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function encodeUtf8LikeBundle(value) {
  return new TextEncoder().encode(unescape(encodeURIComponent(value)));
}

function replaceCharAt(value, index, nextChar) {
  if (index < 0 || index >= value.length || nextChar.length !== 1) {
    return value;
  }

  return `${value.slice(0, index)}${nextChar}${value.slice(index + 1)}`;
}

function pickRandomIndex(segment) {
  return Math.floor(Math.random() * segment.length);
}

function mutateUuidForJti(uuid, pickIndex = pickRandomIndex) {
  const parts = uuid.split("-").map((segment) => {
    const index = pickIndex(segment);
    const charCodeAtIndex = segment.charCodeAt(index);
    const newStr = replaceCharAt(segment, index, "x");

    return {
      index,
      charCodeAtIndex,
      newStr
    };
  });

  const meta = parts.reduce(
    (result, part) => {
      const indexLength = String(String(part.index).length).padStart(2, "0");
      const charCodeLength = String(String(part.charCodeAtIndex).length).padStart(2, "0");

      result.signature.push([indexLength, part.index, charCodeLength, part.charCodeAtIndex].join(""));
      result.encoded.push(part.newStr);
      return result;
    },
    {
      signature: [],
      encoded: []
    }
  );

  return {
    origin: uuid,
    signature: meta.signature.join(""),
    encoded: meta.encoded.join("-")
  };
}

function normalizeRequestPath(urlOrPath, baseOrigin = DEFAULT_PANDAMALL_CONFIG.origin) {
  try {
    if (/^http(s)?:\/\//.test(urlOrPath)) {
      return new URL(urlOrPath).pathname;
    }

    return new URL(urlOrPath, baseOrigin).pathname;
  } catch {
    return urlOrPath;
  }
}

function normalizePandamallProvider(provider) {
  if (!provider) {
    return "";
  }

  const normalizedProvider = String(provider).trim().toLowerCase();
  return PANDAMALL_PROVIDER_MAP[normalizedProvider] ?? normalizedProvider;
}

function parsePandamallMarketplaceUrl(productUrl) {
  let parsedUrl;

  try {
    parsedUrl = new URL(productUrl);
  } catch {
    throw new Error("Invalid product URL");
  }

  const hostname = parsedUrl.hostname.toLowerCase();
  const pathname = parsedUrl.pathname;
  const searchParams = parsedUrl.searchParams;
  let marketplace = "";
  let provider = "";
  let itemId = "";

  if (hostname.endsWith("1688.com")) {
    marketplace = "1688";
    provider = "alibaba";

    const offerMatch = pathname.match(/\/offer\/(\d+)(?:\.html)?/i);
    itemId = offerMatch?.[1] ?? searchParams.get("offerId") ?? searchParams.get("id") ?? "";
  } else if (hostname.endsWith("tmall.com")) {
    marketplace = "tmall";
    provider = "taobao";
    itemId = searchParams.get("id") ?? "";
  } else if (hostname.endsWith("taobao.com")) {
    marketplace = "taobao";
    provider = "taobao";
    itemId = searchParams.get("id") ?? "";
  } else {
    throw new Error(`Unsupported marketplace host: ${hostname}`);
  }

  if (!itemId || !/^\d+$/.test(itemId)) {
    throw new Error(`Could not extract itemId from URL: ${productUrl}`);
  }

  return {
    url: productUrl,
    hostname,
    marketplace,
    provider,
    normalizedProvider: normalizePandamallProvider(provider),
    itemId
  };
}

function resolvePandamallItemLookupInput({ itemId, provider, url } = {}) {
  const parsedFromUrl = url ? parsePandamallMarketplaceUrl(url) : null;
  const resolvedItemId = String(itemId ?? parsedFromUrl?.itemId ?? "").trim();
  const rawProvider = String(provider ?? parsedFromUrl?.provider ?? "").trim();
  const normalizedProvider = normalizePandamallProvider(rawProvider);

  return {
    url: url ?? parsedFromUrl?.url ?? "",
    hostname: parsedFromUrl?.hostname ?? "",
    marketplace: parsedFromUrl?.marketplace ?? "",
    itemId: resolvedItemId,
    provider: rawProvider,
    normalizedProvider
  };
}

async function generatePandamallKeyPair() {
  const { subtle } = crypto.webcrypto;
  const keyPair = await subtle.generateKey(
    {
      name: "ECDSA",
      namedCurve: "P-256",
      hash: { name: "SHA-256" }
    },
    true,
    ["sign", "verify"]
  );

  const [privateKey, publicKey] = await Promise.all([
    subtle.exportKey("jwk", keyPair.privateKey),
    subtle.exportKey("jwk", keyPair.publicKey)
  ]);

  return {
    privateKey,
    publicKey
  };
}

async function createPandamallDpopProof({
  url,
  method = "GET",
  privateKey,
  publicKey,
  keyPair,
  uuid = crypto.randomUUID(),
  now = Date.now(),
  pickIndex = pickRandomIndex
} = {}) {
  const resolvedKeyPair =
    keyPair ??
    (privateKey && publicKey
      ? { privateKey, publicKey }
      : await generatePandamallKeyPair());

  const activePrivateKey = privateKey ?? resolvedKeyPair.privateKey;
  const activePublicKey = publicKey ?? resolvedKeyPair.publicKey;
  const requestPath = normalizeRequestPath(url);
  const requestMethod = method.toUpperCase();
  const { subtle } = crypto.webcrypto;
  const signingKey = await subtle.importKey(
    "jwk",
    activePrivateKey,
    {
      name: "ECDSA",
      namedCurve: "P-256"
    },
    true,
    ["sign"]
  );

  const proofHeader = {
    typ: "dpop",
    alg: "ES256",
    jwk: {
      crv: activePrivateKey.crv,
      kty: activePrivateKey.kty,
      x: activePrivateKey.x,
      y: activePrivateKey.y
    }
  };

  const jtiMeta = mutateUuidForJti(uuid, pickIndex);
  const proofPayload = {
    iat: Math.ceil(now / 1000),
    jti: jtiMeta.encoded,
    htu: requestPath,
    htm: requestMethod,
    jis: jtiMeta.signature
  };

  const encodedHeader = encodeBase64Url(encodeUtf8LikeBundle(JSON.stringify(proofHeader)));
  const encodedPayload = encodeBase64Url(encodeUtf8LikeBundle(JSON.stringify(proofPayload)));
  const signingInput = `${encodedHeader}.${encodedPayload}`;
  const signature = await subtle.sign(
    {
      name: "ECDSA",
      hash: { name: "SHA-256" }
    },
    signingKey,
    encodeUtf8LikeBundle(signingInput)
  );

  return {
    token: `${signingInput}.${encodeBase64Url(signature)}`,
    header: proofHeader,
    payload: proofPayload,
    jtiMeta,
    keyPair: {
      privateKey: activePrivateKey,
      publicKey: activePublicKey
    }
  };
}

async function requestPandamallJson(path, { method = "POST", body, headers = {}, ...options } = {}) {
  const config = {
    ...DEFAULT_PANDAMALL_CONFIG,
    ...options
  };
  const requestUrl = new URL(path, config.apiBaseUrl).toString();
  const dpopProof = await createPandamallDpopProof({
    url: requestUrl,
    method,
    privateKey: config.privateKey,
    publicKey: config.publicKey,
    keyPair: config.keyPair
  });
  const requestHeaders = {
    accept: "application/json, text/plain, */*",
    "content-type": "application/json",
    origin: config.origin,
    referer: config.referer,
    ...headers,
    dpop: dpopProof.token
  };

  const response = await fetch(requestUrl, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  const responseText = await response.text();
  let responseData;

  try {
    responseData = JSON.parse(responseText);
  } catch {
    responseData = responseText;
  }

  return {
    request: {
      url: requestUrl,
      method: method.toUpperCase(),
      headers: requestHeaders,
      dpop: {
        header: dpopProof.header,
        payload: dpopProof.payload,
        token: dpopProof.token,
        keyPair: dpopProof.keyPair
      }
    },
    response: {
      status: response.status,
      ok: response.ok,
      headers: Object.fromEntries(response.headers.entries()),
      data: responseData
    }
  };
}

async function loginPandamall({ phone, password, ...options } = {}) {
  const resolvedPhone = phone ?? DEFAULT_PANDAMALL_ACCOUNT.phone;
  const resolvedPassword = password ?? DEFAULT_PANDAMALL_ACCOUNT.password;

  if (!resolvedPhone) {
    throw new Error("phone is required");
  }

  if (!resolvedPassword) {
    throw new Error("password is required");
  }

  return requestPandamallJson("/api/pandamall/auth/login", {
    method: "POST",
    body: {
      phone: resolvedPhone,
      password: resolvedPassword
    },
    ...options
  });
}

async function loginPandamallAndGetAccessToken(options = {}) {
  const loginResult = await loginPandamall(options);
  const accessToken = loginResult?.response?.data?.data?.accessToken;

  if (!accessToken) {
    const error = new Error("Failed to get PandaMall access token from login response");
    error.loginResult = loginResult;
    throw error;
  }

  return {
    accessToken,
    loginResult
  };
}

async function getPandamallItemDetails({ itemId, provider, url, ...options } = {}) {
  const resolvedInput = resolvePandamallItemLookupInput({
    itemId,
    provider,
    url
  });

  if (!resolvedInput.itemId) {
    throw new Error("itemId is required");
  }

  if (!resolvedInput.normalizedProvider) {
    throw new Error("provider is required");
  }

  const { accessToken, loginResult } = await loginPandamallAndGetAccessToken(options);
  const itemDetailsResult = await requestPandamallJson("/api/pandamall/v1/item/details", {
    method: "POST",
    headers: {
      authorization: `Bearer ${accessToken}`
    },
    body: {
      item_id: Number(resolvedInput.itemId),
      provider: resolvedInput.normalizedProvider
    },
    keyPair: loginResult?.request?.dpop?.keyPair,
    ...options
  });

  return {
    auth: {
      accessToken,
      login: loginResult
    },
    input: resolvedInput,
    itemDetails: itemDetailsResult
  };
}

module.exports = {
  DEFAULT_PANDAMALL_ACCOUNT,
  DEFAULT_PANDAMALL_CONFIG,
  PANDAMALL_CREDENTIALS_PATH,
  PANDAMALL_PROVIDER_MAP,
  createPandamallDpopProof,
  encodeBase64Url,
  encodeUtf8LikeBundle,
  generatePandamallKeyPair,
  getPandamallItemDetails,
  loginPandamallAndGetAccessToken,
  loginPandamall,
  loadOptionalPandamallCredentials,
  mutateUuidForJti,
  parsePandamallMarketplaceUrl,
  normalizePandamallProvider,
  normalizeRequestPath,
  resolvePandamallItemLookupInput,
  requestPandamallJson
};
