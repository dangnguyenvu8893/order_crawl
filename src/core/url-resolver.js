const { URL_RESOLVER_MAX_RESPONSE_BYTES, URL_RESOLVER_TIMEOUT_MS } = require("../config");
const { HttpError, isAbortError } = require("./errors");
const { normalizeString } = require("./product");
const { parseProductUrl } = require("./url");

const HTTP_PROTOCOL_RE = /^https?:\/\//i;
const DEEP_LINK_PROTOCOL_RE = /^(?:taobao|tmall|wireless1688):\/\//i;
const URL_EXTRACTION_RE = /(?:https?:\/\/|taobao:\/\/|tmall:\/\/|wireless1688:\/\/)[^\s<>"']+/gi;
const URL_PRIORITY_KEYWORDS = Object.freeze([
  "detail.1688.com",
  "item.taobao.com",
  "detail.tmall.com",
  "1688",
  "taobao",
  "tmall",
  "offer",
  "item",
  "id="
]);
const DESKTOP_HOST_MARKETPLACE = Object.freeze({
  "detail.1688.com": "1688",
  "item.taobao.com": "taobao",
  "detail.tmall.com": "tmall"
});
const MOBILE_HOST_MARKETPLACE = Object.freeze({
  "m.taobao.com": "taobao",
  "h5.m.taobao.com": "taobao",
  "m.tmall.com": "tmall",
  "h5.tmall.com": "tmall",
  "m.1688.com": "1688",
  "h5.1688.com": "1688"
});
const CLEAR_SHORT_HOST_MARKETPLACE = Object.freeze({
  "qr.1688.com": "1688",
  "s.click.taobao.com": "taobao",
  "uland.taobao.com": "taobao"
});
const AMBIGUOUS_SHORT_HOSTS = new Set(["e.tb.cn", "tb.cn", "s.tb.cn", "m.tb.cn"]);
const SUPPORTED_HOSTS = new Set([
  ...Object.keys(DESKTOP_HOST_MARKETPLACE),
  ...Object.keys(MOBILE_HOST_MARKETPLACE),
  ...Object.keys(CLEAR_SHORT_HOST_MARKETPLACE),
  ...AMBIGUOUS_SHORT_HOSTS
]);
const DEFAULT_FETCH_HEADERS = Object.freeze({
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
  "cache-control": "no-cache",
  pragma: "no-cache",
  "upgrade-insecure-requests": "1"
});
const MOBILE_FETCH_HEADERS = Object.freeze({
  ...DEFAULT_FETCH_HEADERS,
  "user-agent":
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
  referer: "https://m.taobao.com/"
});
const DESKTOP_FETCH_HEADERS = Object.freeze({
  ...DEFAULT_FETCH_HEADERS,
  "user-agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
  referer: "https://www.taobao.com/"
});
const QUERY_ID_KEYS = Object.freeze(["offerId", "id", "itemId", "item_id", "productId"]);
const CONTENT_ID_PATTERNS = Object.freeze([
  /(?:offerId|itemId|item_id|productId|product_id)\D{0,20}(\d{9,13})/i,
  /(?:detail\.1688\.com\/offer\/|item\.taobao\.com\/item\.htm\?id=|detail\.tmall\.com\/item\.htm\?id=)(\d{9,13})/i,
  /["']id["']\s*[:=]\s*["']?(\d{9,13})/i,
  /\/offer\/(\d{9,13})(?:\.html)?/i
]);

function buildDesktopProductUrl(marketplace, itemId) {
  if (marketplace === "1688") {
    return `https://detail.1688.com/offer/${itemId}.html`;
  }

  if (marketplace === "tmall") {
    return `https://detail.tmall.com/item.htm?id=${itemId}`;
  }

  return `https://item.taobao.com/item.htm?id=${itemId}`;
}

function normalizeHostname(hostname) {
  return normalizeString(hostname).toLowerCase();
}

function cleanExtractedUrl(value) {
  return normalizeString(value)
    .replace(/^[('"【「]+/u, "")
    .replace(/[)\]}>"'.,;!?）】」]+$/u, "")
    .trim();
}

function looksLikeUrlCandidate(value) {
  return HTTP_PROTOCOL_RE.test(normalizeString(value)) || DEEP_LINK_PROTOCOL_RE.test(normalizeString(value));
}

function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function extractUrlsFromText(text) {
  const normalizedText = normalizeString(text);
  if (!normalizedText) {
    return [];
  }

  const seen = new Set();
  const urls = [];
  const matches = normalizedText.match(URL_EXTRACTION_RE) ?? [];

  for (const match of matches) {
    const cleaned = cleanExtractedUrl(match);
    if (!cleaned || seen.has(cleaned)) {
      continue;
    }

    seen.add(cleaned);
    urls.push(cleaned);
  }

  return urls;
}

function scoreUrlPriority(url) {
  const normalizedUrl = normalizeString(url).toLowerCase();
  return URL_PRIORITY_KEYWORDS.reduce((score, keyword, index) => {
    return normalizedUrl.includes(keyword) ? score + (URL_PRIORITY_KEYWORDS.length - index) : score;
  }, 0);
}

function extractBestUrlFromText(text) {
  const urls = extractUrlsFromText(text);
  if (urls.length === 0) {
    return null;
  }

  return [...urls].sort((left, right) => scoreUrlPriority(right) - scoreUrlPriority(left))[0] ?? null;
}

function inferMarketplaceFromHostname(hostname) {
  const normalizedHostname = normalizeHostname(hostname);

  if (DESKTOP_HOST_MARKETPLACE[normalizedHostname]) {
    return DESKTOP_HOST_MARKETPLACE[normalizedHostname];
  }

  if (MOBILE_HOST_MARKETPLACE[normalizedHostname]) {
    return MOBILE_HOST_MARKETPLACE[normalizedHostname];
  }

  if (CLEAR_SHORT_HOST_MARKETPLACE[normalizedHostname]) {
    return CLEAR_SHORT_HOST_MARKETPLACE[normalizedHostname];
  }

  if (normalizedHostname.endsWith(".1688.com")) {
    return "1688";
  }

  if (normalizedHostname.endsWith(".tmall.com")) {
    return "tmall";
  }

  if (normalizedHostname.endsWith(".taobao.com")) {
    return "taobao";
  }

  return null;
}

function inferMarketplaceFromValue(value, fallbackMarketplace = "") {
  const normalizedValue = normalizeString(value).toLowerCase();

  if (normalizedValue.startsWith("wireless1688://")) {
    return "1688";
  }

  if (normalizedValue.startsWith("tmall://")) {
    return "tmall";
  }

  if (normalizedValue.startsWith("taobao://")) {
    return "taobao";
  }

  try {
    return inferMarketplaceFromHostname(new URL(normalizedValue).hostname) ?? fallbackMarketplace;
  } catch {
    if (normalizedValue.includes("1688")) {
      return "1688";
    }

    if (normalizedValue.includes("tmall")) {
      return "tmall";
    }

    if (normalizedValue.includes("taobao")) {
      return "taobao";
    }

    return fallbackMarketplace;
  }
}

function getQueryParamIdCandidate(searchParams) {
  for (const key of QUERY_ID_KEYS) {
    const value = normalizeString(searchParams.get(key));
    if (/^\d{9,13}$/.test(value)) {
      return value;
    }
  }

  return "";
}

function extractProductIdCandidate(value, { allowGeneric = false } = {}) {
  const normalizedValue = normalizeString(value);
  if (!normalizedValue) {
    return "";
  }

  try {
    const parsedUrl = new URL(normalizedValue);
    const queryCandidate = getQueryParamIdCandidate(parsedUrl.searchParams);
    if (queryCandidate) {
      return queryCandidate;
    }

    if (parsedUrl.hash) {
      const hashSearchParams = new URLSearchParams(parsedUrl.hash.replace(/^#/, ""));
      const hashCandidate = getQueryParamIdCandidate(hashSearchParams);
      if (hashCandidate) {
        return hashCandidate;
      }
    }
  } catch {
    // Fall through to regex extraction.
  }

  for (const pattern of [
    /\/offer\/(\d{9,13})(?:\.html)?/i,
    /(?:[?&#](?:offerId|id|itemId|item_id|productId)=)(\d{9,13})/i,
    /\/item\/(\d{9,13})\b/i
  ]) {
    const match = normalizedValue.match(pattern);
    if (match?.[1]) {
      return match[1];
    }
  }

  if (!allowGeneric) {
    return "";
  }

  return normalizedValue.match(/\b(\d{9,13})\b/)?.[1] ?? "";
}

function extractContentProductId(html) {
  const normalizedHtml = normalizeString(html);
  if (!normalizedHtml) {
    return "";
  }

  for (const pattern of CONTENT_ID_PATTERNS) {
    const match = normalizedHtml.match(pattern);
    if (match?.[1]) {
      return match[1];
    }
  }

  return "";
}

function collectNestedUrlCandidates(parsedUrl) {
  const nestedCandidates = [];
  const seen = new Set();
  const candidateValues = [];

  for (const [, value] of parsedUrl.searchParams.entries()) {
    candidateValues.push(value);
    candidateValues.push(safeDecodeURIComponent(value));
  }

  if (parsedUrl.hash) {
    candidateValues.push(parsedUrl.hash.slice(1));
    candidateValues.push(safeDecodeURIComponent(parsedUrl.hash.slice(1)));
  }

  for (const candidate of candidateValues) {
    if (!looksLikeUrlCandidate(candidate)) {
      continue;
    }

    const cleaned = cleanExtractedUrl(candidate);
    if (!cleaned || seen.has(cleaned)) {
      continue;
    }

    seen.add(cleaned);
    nestedCandidates.push(cleaned);
  }

  return nestedCandidates;
}

function resolveDirectProductUrlCandidate(
  value,
  {
    fallbackMarketplace = "",
    allowGenericId = false,
    depth = 0
  } = {}
) {
  const normalizedValue = cleanExtractedUrl(value);
  if (!normalizedValue) {
    return null;
  }

  if (DEEP_LINK_PROTOCOL_RE.test(normalizedValue)) {
    return convertDeepLinkToDesktopUrl(normalizedValue, fallbackMarketplace);
  }

  if (!HTTP_PROTOCOL_RE.test(normalizedValue)) {
    return null;
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(normalizedValue);
  } catch {
    return null;
  }

  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    return null;
  }

  if (depth < 2) {
    const nestedCandidates = collectNestedUrlCandidates(parsedUrl);
    for (const nestedCandidate of nestedCandidates) {
      const resolvedNested = resolveDirectProductUrlCandidate(nestedCandidate, {
        fallbackMarketplace: inferMarketplaceFromValue(normalizedValue, fallbackMarketplace),
        allowGenericId: true,
        depth: depth + 1
      });

      if (resolvedNested) {
        return resolvedNested;
      }
    }
  }

  const hostname = normalizeHostname(parsedUrl.hostname);
  const directMarketplace =
    DESKTOP_HOST_MARKETPLACE[hostname] ??
    MOBILE_HOST_MARKETPLACE[hostname] ??
    CLEAR_SHORT_HOST_MARKETPLACE[hostname];
  const inferredMarketplace = directMarketplace ?? inferMarketplaceFromValue(normalizedValue, fallbackMarketplace);
  const itemId = extractProductIdCandidate(normalizedValue, {
    allowGeneric: allowGenericId || Boolean(directMarketplace) || MOBILE_HOST_MARKETPLACE[hostname] === "1688"
  });

  if (!inferredMarketplace || !itemId) {
    return null;
  }

  if (DESKTOP_HOST_MARKETPLACE[hostname] || MOBILE_HOST_MARKETPLACE[hostname] || CLEAR_SHORT_HOST_MARKETPLACE[hostname]) {
    return buildDesktopProductUrl(inferredMarketplace, itemId);
  }

  return null;
}

function convertDeepLinkToDesktopUrl(value, fallbackMarketplace = "") {
  const itemId = extractProductIdCandidate(value, { allowGeneric: true });
  const marketplace = inferMarketplaceFromValue(value, fallbackMarketplace);

  if (!marketplace || !itemId) {
    return null;
  }

  return buildDesktopProductUrl(marketplace, itemId);
}

function parseContentForProductUrl(html, sourceUrl) {
  const extractedUrl = extractBestUrlFromText(html);
  if (extractedUrl) {
    const resolvedExtractedUrl = resolveDirectProductUrlCandidate(extractedUrl, {
      fallbackMarketplace: inferMarketplaceFromValue(sourceUrl)
    });

    if (resolvedExtractedUrl) {
      return resolvedExtractedUrl;
    }
  }

  const contentItemId = extractContentProductId(html);
  const marketplace = inferMarketplaceFromValue(html, inferMarketplaceFromValue(sourceUrl));
  if (!marketplace || !contentItemId) {
    return null;
  }

  return buildDesktopProductUrl(marketplace, contentItemId);
}

function getSupportedMarketplaceHost(url) {
  try {
    const hostname = normalizeHostname(new URL(url).hostname);
    if (SUPPORTED_HOSTS.has(hostname)) {
      return hostname;
    }

    if (
      hostname.endsWith(".taobao.com") ||
      hostname.endsWith(".tmall.com") ||
      hostname.endsWith(".1688.com")
    ) {
      return hostname;
    }

    return "";
  } catch {
    return "";
  }
}

function createUnsupportedHostError(url) {
  const hostname = normalizeHostname(new URL(url).hostname);
  return new HttpError(`Unsupported marketplace host: ${hostname || "unknown"}`, 400, "unsupported_host");
}

function createInvalidProductUrlError(message, details = undefined) {
  return new HttpError(message, 400, "invalid_product_url", details);
}

function getRemainingBudgetMs(deadlineAt) {
  return deadlineAt - Date.now();
}

function buildRequestSignal(signal, deadlineAt) {
  const timeoutController = new AbortController();
  const remainingMs = getRemainingBudgetMs(deadlineAt);

  if (remainingMs <= 0) {
    timeoutController.abort(new DOMException("Aborted", "AbortError"));
  } else {
    const timeoutId = setTimeout(() => {
      timeoutController.abort(new DOMException("Aborted", "AbortError"));
    }, remainingMs);
    timeoutId.unref?.();
  }

  if (!signal) {
    return timeoutController.signal;
  }

  return AbortSignal.any([signal, timeoutController.signal]);
}

async function fetchWithResolutionBudget(
  url,
  {
    method,
    headers,
    signal,
    deadlineAt,
    fetchImpl
  }
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("URL resolver requires fetch support");
  }

  if (getRemainingBudgetMs(deadlineAt) <= 0) {
    throw new Error("URL resolution timed out");
  }

  return fetchImpl(url, {
    method,
    headers,
    redirect: "follow",
    signal: buildRequestSignal(signal, deadlineAt)
  });
}

async function readResponseTextLimited(response, maxBytes) {
  if (!response?.body || typeof response.body.getReader !== "function") {
    const text = await response.text();
    return text.length > maxBytes ? text.slice(0, maxBytes) : text;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let totalBytes = 0;
  let output = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    totalBytes += value.byteLength;
    if (totalBytes > maxBytes) {
      const allowedBytes = Math.max(0, value.byteLength - (totalBytes - maxBytes));
      if (allowedBytes > 0) {
        output += decoder.decode(value.subarray(0, allowedBytes), { stream: true });
      }
      await reader.cancel();
      break;
    }

    output += decoder.decode(value, { stream: true });
  }

  output += decoder.decode();
  return output;
}

async function resolveViaNetwork(
  url,
  {
    fetchImpl = globalThis.fetch,
    timeoutMs = URL_RESOLVER_TIMEOUT_MS,
    maxResponseBytes = URL_RESOLVER_MAX_RESPONSE_BYTES,
    signal
  } = {}
) {
  const deadlineAt = Date.now() + timeoutMs;
  let lastError = null;

  for (const attempt of [
    { method: "HEAD", headers: MOBILE_FETCH_HEADERS, methodName: "redirect_head", readBody: false },
    { method: "GET", headers: MOBILE_FETCH_HEADERS, methodName: "redirect_get_mobile", readBody: true },
    { method: "GET", headers: DESKTOP_FETCH_HEADERS, methodName: "redirect_get_desktop", readBody: true }
  ]) {
    try {
      const response = await fetchWithResolutionBudget(url, {
        method: attempt.method,
        headers: attempt.headers,
        signal,
        deadlineAt,
        fetchImpl
      });
      const resolvedRedirectUrl = resolveDirectProductUrlCandidate(response.url, {
        fallbackMarketplace: inferMarketplaceFromValue(url)
      });

      if (resolvedRedirectUrl) {
        return {
          resolvedUrl: resolvedRedirectUrl,
          method: attempt.methodName
        };
      }

      if (!attempt.readBody) {
        continue;
      }

      const body = await readResponseTextLimited(response, maxResponseBytes);
      const resolvedFromContent = parseContentForProductUrl(body, response.url || url);
      if (resolvedFromContent) {
        return {
          resolvedUrl: resolvedFromContent,
          method: `${attempt.methodName}_content`
        };
      }
    } catch (error) {
      lastError = error;
      if (isAbortError(error)) {
        break;
      }
    }
  }

  if (isAbortError(lastError) || /timed out/i.test(String(lastError?.message ?? ""))) {
    throw createInvalidProductUrlError("Could not resolve a product detail URL before resolver timeout", {
      reason: "resolver_timeout"
    });
  }

  throw createInvalidProductUrlError("Could not resolve a supported product detail URL from input", {
    reason: lastError?.message ?? "resolver_failed"
  });
}

async function resolveProductUrlInput(
  input,
  {
    fetchImpl = globalThis.fetch,
    timeoutMs = URL_RESOLVER_TIMEOUT_MS,
    maxResponseBytes = URL_RESOLVER_MAX_RESPONSE_BYTES,
    signal
  } = {}
) {
  const originalInput = normalizeString(input);
  if (!originalInput) {
    throw new HttpError("url must be a valid http(s) URL", 400, "invalid_url");
  }

  let candidate = cleanExtractedUrl(originalInput);
  let extractedFromText = false;

  if (!looksLikeUrlCandidate(candidate)) {
    const extractedCandidate = extractBestUrlFromText(originalInput);
    if (!extractedCandidate) {
      throw new HttpError("url must be a valid http(s) URL", 400, "invalid_url");
    }

    candidate = extractedCandidate;
    extractedFromText = true;
  }

  const directResolution = resolveDirectProductUrlCandidate(candidate);
  if (directResolution) {
    return {
      originalInput,
      extractedInputUrl: extractedFromText ? candidate : null,
      resolvedUrl: parseProductUrl(directResolution).canonicalUrl,
      method: extractedFromText ? "text_extract_direct" : "direct",
      extractedFromText,
      networkAttempted: false
    };
  }

  if (DEEP_LINK_PROTOCOL_RE.test(candidate)) {
    throw createInvalidProductUrlError(`Could not extract product id from URL: ${candidate}`);
  }

  if (!HTTP_PROTOCOL_RE.test(candidate)) {
    throw new HttpError("url must be a valid http(s) URL", 400, "invalid_url");
  }

  const supportedHost = getSupportedMarketplaceHost(candidate);
  if (!supportedHost) {
    throw createUnsupportedHostError(candidate);
  }

  const resolved = await resolveViaNetwork(candidate, {
    fetchImpl,
    timeoutMs,
    maxResponseBytes,
    signal
  });

  return {
    originalInput,
    extractedInputUrl: extractedFromText ? candidate : null,
    resolvedUrl: parseProductUrl(resolved.resolvedUrl).canonicalUrl,
    method: resolved.method,
    extractedFromText,
    networkAttempted: true
  };
}

async function buildProductContextFromInput(input, options = {}) {
  const resolution = await resolveProductUrlInput(input, options);
  const parsed = parseProductUrl(resolution.resolvedUrl);

  return {
    ...parsed,
    originalInput: resolution.originalInput,
    extractedInputUrl: resolution.extractedInputUrl,
    resolution
  };
}

module.exports = {
  AMBIGUOUS_SHORT_HOSTS,
  CLEAR_SHORT_HOST_MARKETPLACE,
  DESKTOP_HOST_MARKETPLACE,
  MOBILE_HOST_MARKETPLACE,
  buildDesktopProductUrl,
  buildProductContextFromInput,
  cleanExtractedUrl,
  convertDeepLinkToDesktopUrl,
  extractBestUrlFromText,
  extractContentProductId,
  extractProductIdCandidate,
  extractUrlsFromText,
  getSupportedMarketplaceHost,
  inferMarketplaceFromHostname,
  inferMarketplaceFromValue,
  parseContentForProductUrl,
  resolveDirectProductUrlCandidate,
  resolveProductUrlInput,
  resolveViaNetwork
};
