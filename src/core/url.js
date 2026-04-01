const { HttpError } = require("./errors");
const { normalizeString } = require("./product");

function parseProductUrl(url) {
  const normalizedInput = normalizeString(url);
  let parsedUrl;

  try {
    parsedUrl = new URL(normalizedInput);
  } catch {
    throw new HttpError("url must be a valid http(s) URL", 400, "invalid_url");
  }

  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    throw new HttpError("url must be a valid http(s) URL", 400, "invalid_url");
  }

  const hostname = parsedUrl.hostname.toLowerCase();
  const searchParams = parsedUrl.searchParams;
  let marketplace = "";
  let itemId = "";

  if (hostname.endsWith("1688.com")) {
    marketplace = "1688";
    itemId =
      parsedUrl.pathname.match(/\/offer\/(\d+)(?:\.html)?/i)?.[1] ??
      searchParams.get("offerId") ??
      searchParams.get("id") ??
      "";
  } else if (hostname.endsWith("tmall.com")) {
    marketplace = "tmall";
    itemId = searchParams.get("id") ?? "";
  } else if (hostname.endsWith("taobao.com")) {
    marketplace = "taobao";
    itemId = searchParams.get("id") ?? "";
  } else {
    throw new HttpError(`Unsupported marketplace host: ${hostname || "unknown"}`, 400, "unsupported_host");
  }

  if (!/^\d+$/.test(itemId)) {
    throw new HttpError(`Could not extract product id from URL: ${normalizedInput}`, 400, "invalid_product_url");
  }

  if (marketplace === "1688") {
    return {
      inputUrl: normalizedInput,
      hostname,
      marketplace,
      itemId,
      canonicalUrl: `https://detail.1688.com/offer/${itemId}.html`
    };
  }

  if (marketplace === "tmall") {
    return {
      inputUrl: normalizedInput,
      hostname,
      marketplace,
      itemId,
      canonicalUrl: `https://detail.tmall.com/item.htm?id=${itemId}`
    };
  }

  return {
    inputUrl: normalizedInput,
    hostname,
    marketplace,
    itemId,
    canonicalUrl: `https://item.taobao.com/item.htm?id=${itemId}`
  };
}

module.exports = {
  parseProductUrl
};
