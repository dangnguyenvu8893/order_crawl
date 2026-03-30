const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const HANGVE_CREDENTIALS_PATH = path.join(__dirname, "../config/hangve.credentials.json");
const HANGVE_KEY_FACIN_OFFSET = Number.parseInt("af7fe3e7bd6b", 16);
const HANGVE_DIFF_TIME_OFFSET = 5678912192;
const HANGVE_KEY_FACIN_ALPHABET = "abcdefghvwxyz0123456789";

function loadOptionalHangveCredentials() {
  try {
    return JSON.parse(fs.readFileSync(HANGVE_CREDENTIALS_PATH, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") {
      return {};
    }

    throw error;
  }
}

const hangveCredentials = loadOptionalHangveCredentials();

const DEFAULT_HANGVE_CONFIG = {
  apiBaseUrl: process.env.HANGVE_API_BASE_URL ?? "https://api-client.hangve.com/api",
  origin: process.env.HANGVE_ORIGIN ?? "https://client.hangve.com",
  referer: process.env.HANGVE_REFERER ?? "https://client.hangve.com/"
};

const DEFAULT_HANGVE_ACCOUNT = {
  username:
    process.env.HANGVE_USERNAME ??
    hangveCredentials.username ??
    hangveCredentials.phone ??
    "",
  password: process.env.HANGVE_PASSWORD ?? hangveCredentials.password ?? ""
};

const HANGVE_SOURCE_MAP = {
  "1688": "sync_1688",
  sync_1688: "sync_1688",
  taobao: "sync_taobao",
  tmall: "sync_taobao",
  sync_taobao: "sync_taobao"
};

function normalizeHangveSource(source = "sync_1688") {
  const normalizedSource = String(source).trim().toLowerCase();
  return HANGVE_SOURCE_MAP[normalizedSource] ?? normalizedSource;
}

function parseHangveMarketplaceUrl(value) {
  let parsedUrl;

  try {
    parsedUrl = new URL(value);
  } catch {
    return null;
  }

  const hostname = parsedUrl.hostname.toLowerCase();

  if (hostname.endsWith("1688.com")) {
    return {
      url: value,
      hostname,
      marketplace: "1688",
      source: "sync_1688"
    };
  }

  if (hostname.endsWith("taobao.com")) {
    return {
      url: value,
      hostname,
      marketplace: "taobao",
      source: "sync_taobao"
    };
  }

  if (hostname.endsWith("tmall.com")) {
    return {
      url: value,
      hostname,
      marketplace: "tmall",
      source: "sync_taobao"
    };
  }

  return null;
}

function resolveHangveSearchInput({ keySearch, url, source } = {}) {
  const resolvedKeySearch = String(keySearch ?? url ?? "").trim();
  const parsedMarketplaceUrl = parseHangveMarketplaceUrl(resolvedKeySearch);

  return {
    keySearch: resolvedKeySearch,
    source: normalizeHangveSource(source ?? parsedMarketplaceUrl?.source ?? "sync_1688"),
    marketplace: parsedMarketplaceUrl?.marketplace ?? "",
    hostname: parsedMarketplaceUrl?.hostname ?? ""
  };
}

function parseHangveJsonValue(value) {
  if (typeof value !== "string") {
    return value;
  }

  const normalizedValue = value.trim();

  if (!normalizedValue || !["{", "["].includes(normalizedValue[0])) {
    return value;
  }

  try {
    return JSON.parse(normalizedValue);
  } catch {
    return value;
  }
}

function normalizeHangveString(value) {
  if (value === undefined || value === null) {
    return "";
  }

  const normalizedValue = String(value).trim();
  return normalizedValue;
}

function getHangveFirstString(...values) {
  for (const value of values) {
    const normalizedValue = normalizeHangveString(value);

    if (normalizedValue) {
      return normalizedValue;
    }
  }

  return "";
}

function normalizeHangveNumber(value) {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }

  const normalizedValue = Number(value);
  return Number.isFinite(normalizedValue) ? normalizedValue : undefined;
}

function normalizeHangveStringArray(values) {
  if (!Array.isArray(values)) {
    return [];
  }

  return values.map((value) => normalizeHangveString(value)).filter(Boolean);
}

function uniqueHangveStrings(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeHangveVariantGroups(groups) {
  if (!Array.isArray(groups)) {
    return [];
  }

  return groups
    .map((group) => {
      if (!group || typeof group !== "object") {
        return null;
      }

      const name = getHangveFirstString(group.prop_name, group.prop_name_original);
      const nameOriginal = getHangveFirstString(group.prop_name_original, group.prop_name);
      const values = uniqueHangveStrings(normalizeHangveStringArray(group.prop_values));
      const valuesOriginal = uniqueHangveStrings(normalizeHangveStringArray(group.prop_values_original));
      const valuesOriginalCn = uniqueHangveStrings(normalizeHangveStringArray(group.prop_values_original_cn));

      if (!name && values.length === 0 && valuesOriginal.length === 0 && valuesOriginalCn.length === 0) {
        return null;
      }

      return {
        name,
        nameOriginal,
        values,
        valuesOriginal,
        valuesOriginalCn
      };
    })
    .filter(Boolean);
}

function normalizeHangveSkus(details) {
  if (!Array.isArray(details)) {
    return [];
  }

  return details
    .map((detail) => {
      if (!detail || typeof detail !== "object") {
        return null;
      }

      const skuId = getHangveFirstString(detail.sku_id, detail.mp_sku_id, detail.skuId, detail.mpSkuId);
      const classification = getHangveFirstString(detail.classification, detail.classification_cn);
      const classificationCn = getHangveFirstString(detail.classification_cn, detail.classification);
      const quantity = normalizeHangveNumber(detail.quantity);
      const price = normalizeHangveNumber(detail.price);
      const promotionPrice = normalizeHangveNumber(detail.promotionPrice ?? detail.promotion_price);
      const postFee = normalizeHangveNumber(detail.post_fee ?? detail.postFee);
      const image = getHangveFirstString(detail.pic_url, detail.picUrl);

      if (!skuId && !classification && quantity === undefined && price === undefined && !image) {
        return null;
      }

      return {
        skuId,
        classification,
        classificationCn,
        quantity,
        price,
        promotionPrice,
        postFee,
        image
      };
    })
    .filter(Boolean);
}

function normalizeHangveAttributes(attributes) {
  if (!Array.isArray(attributes)) {
    return [];
  }

  return attributes
    .map((attribute) => {
      if (!attribute || typeof attribute !== "object") {
        return null;
      }

      const name = getHangveFirstString(attribute.name, attribute.propName, attribute.prop_name, attribute.key);
      const value = getHangveFirstString(
        attribute.value,
        attribute.valueNameTranslate,
        attribute.valueName,
        attribute.valueDesc
      );

      if (!name || !value) {
        return null;
      }

      return {
        name,
        value
      };
    })
    .filter(Boolean);
}

function normalizeHangvePriceRanges(priceRanges) {
  if (!Array.isArray(priceRanges)) {
    return [];
  }

  return priceRanges
    .map((priceRange) => {
      if (!priceRange || typeof priceRange !== "object") {
        return null;
      }

      const minQuantity = normalizeHangveNumber(
        priceRange.startQuantity ?? priceRange.start_quantity ?? priceRange.beginAmount ?? priceRange.quantity
      );
      const maxQuantity = normalizeHangveNumber(priceRange.endQuantity ?? priceRange.end_quantity);
      const price = normalizeHangveNumber(
        priceRange.price ?? priceRange.promotionPrice ?? priceRange.promotion_price
      );

      if (minQuantity === undefined && maxQuantity === undefined && price === undefined) {
        return null;
      }

      return {
        minQuantity,
        maxQuantity,
        price
      };
    })
    .filter(Boolean);
}

function normalizeHangveItemDetailPayload(detailPayload = {}) {
  const normalizedDetailPayload =
    detailPayload && typeof detailPayload === "object" ? detailPayload : {};
  const parsedBuyderData = parseHangveJsonValue(normalizedDetailPayload.buyder_data);
  const parsedSkuProperties = parseHangveJsonValue(normalizedDetailPayload.sku_properties);
  const parsedData = parseHangveJsonValue(normalizedDetailPayload.data);
  const parsedItem =
    parsedData?.item && typeof parsedData.item === "object" ? parsedData.item : {};
  const priceRanges = normalizeHangvePriceRanges(
    parsedBuyderData?.priceRangeList ??
      parsedBuyderData?.price_ranges ??
      parsedBuyderData?.sku_price_ranges ??
      normalizedDetailPayload.priceRangeList
  );
  const images = uniqueHangveStrings([
    ...normalizeHangveStringArray(normalizedDetailPayload.images),
    ...normalizeHangveStringArray(parsedSkuProperties?.pic_urls),
    ...normalizeHangveStringArray(parsedBuyderData?.picUrls),
    ...normalizeHangveStringArray(parsedItem.images),
    getHangveFirstString(normalizedDetailPayload.pic, parsedItem.pic)
  ]);
  const variantGroups = normalizeHangveVariantGroups(parsedSkuProperties?.properties);
  const skus = normalizeHangveSkus(parsedSkuProperties?.details);
  const attributes = normalizeHangveAttributes(parsedItem.properties);
  const descriptionHtml = getHangveFirstString(
    parsedBuyderData?.description,
    normalizedDetailPayload.description,
    parsedItem.description
  );

  return {
    source: getHangveFirstString(normalizedDetailPayload.source, parsedItem.source),
    itemId: normalizeHangveNumber(
      normalizedDetailPayload.id ?? parsedBuyderData?.itemId ?? parsedBuyderData?.mpId
    ),
    numIid: getHangveFirstString(
      normalizedDetailPayload.num_iid,
      parsedItem.num_iid,
      parsedBuyderData?.itemId,
      parsedBuyderData?.mpId
    ),
    title: getHangveFirstString(
      normalizedDetailPayload.title_vi,
      normalizedDetailPayload.title,
      parsedItem.title_vi,
      parsedItem.title,
      parsedBuyderData?.title
    ),
    sellerNick: getHangveFirstString(
      normalizedDetailPayload.seller_nick_vi,
      normalizedDetailPayload.seller_nick,
      parsedBuyderData?.shopName,
      parsedBuyderData?.sellerNickName
    ),
    detailUrl: getHangveFirstString(
      normalizedDetailPayload.detail_url,
      parsedItem.detail_url,
      parsedBuyderData?.itemUrl
    ),
    price: normalizeHangveNumber(
      normalizedDetailPayload.price ?? parsedBuyderData?.price ?? parsedItem.price
    ),
    promotionPrice: normalizeHangveNumber(
      normalizedDetailPayload.promotion_price ??
        parsedBuyderData?.promotionPrice ??
        parsedItem.promotion_price
    ),
    quantity: normalizeHangveNumber(parsedBuyderData?.quantity),
    minOrderQuantity: normalizeHangveNumber(
      parsedBuyderData?.minOrderQuantity ?? parsedBuyderData?.min_order_quantity
    ),
    batchNumber: normalizeHangveNumber(parsedBuyderData?.batch_number),
    mainImage: images[0] ?? "",
    images,
    imageCount: images.length,
    variantGroups,
    variantGroupCount: variantGroups.length,
    skus,
    skuCount: skus.length,
    attributes,
    attributeCount: attributes.length,
    priceRanges,
    priceRangeCount: priceRanges.length,
    descriptionHtml
  };
}

function isHangveOptionEnabled(value) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    return !["", "0", "false", "no", "off"].includes(value.trim().toLowerCase());
  }

  return Boolean(value);
}

function getDefaultHangveHeaders(config = {}) {
  return {
    accept: "application/json",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    origin: config.origin,
    referer: config.referer,
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-organization": config.origin
  };
}

function buildHangveKeyFacinBase(goSlim) {
  const normalizedGoSlim = Number(goSlim);

  if (!Number.isFinite(normalizedGoSlim)) {
    throw new Error("goSlim is required to build key_facin");
  }

  return HANGVE_KEY_FACIN_OFFSET + normalizedGoSlim - HANGVE_DIFF_TIME_OFFSET;
}

function defaultRandomHangveString(length) {
  const bytes = new Uint8Array(length);
  crypto.webcrypto.getRandomValues(bytes);

  return Array.from(bytes, (value) => HANGVE_KEY_FACIN_ALPHABET[value % HANGVE_KEY_FACIN_ALPHABET.length]).join("");
}

function defaultRandomHangveFiveDigits() {
  return Math.floor(Math.random() * 90000) + 10000;
}

function createHangveKeyFacin({
  goSlim,
  randomString = defaultRandomHangveString,
  randomPrefix = defaultRandomHangveFiveDigits,
  randomSuffix = defaultRandomHangveFiveDigits
} = {}) {
  const keyBase = buildHangveKeyFacinBase(goSlim);
  return `${randomPrefix()}${keyBase}${randomSuffix()}${randomString(20)}`;
}

async function requestHangveJson(
  requestPath,
  { method = "GET", body, params, token, headers = {}, ...options } = {}
) {
  const config = {
    ...DEFAULT_HANGVE_CONFIG,
    ...options
  };
  const normalizedRequestPath = String(requestPath).replace(/^\/+/, "");
  const normalizedApiBaseUrl = config.apiBaseUrl.endsWith("/") ? config.apiBaseUrl : `${config.apiBaseUrl}/`;
  const requestUrl = new URL(normalizedRequestPath, normalizedApiBaseUrl);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      requestUrl.searchParams.set(key, value ?? "");
    }
  }

  const requestHeaders = {
    ...getDefaultHangveHeaders(config),
    ...headers
  };

  if (token) {
    requestHeaders.authorization = `Bearer ${token}`;
  }

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
      url: requestUrl.toString(),
      method: method.toUpperCase(),
      headers: requestHeaders,
      body,
      params: params ?? {}
    },
    response: {
      status: response.status,
      ok: response.ok,
      headers: Object.fromEntries(response.headers.entries()),
      data: responseData
    }
  };
}

async function loginHangve({ username, password, headers = {}, ...options } = {}) {
  const resolvedUsername = username ?? DEFAULT_HANGVE_ACCOUNT.username;
  const resolvedPassword = password ?? DEFAULT_HANGVE_ACCOUNT.password;

  if (!resolvedUsername) {
    throw new Error("username is required");
  }

  if (!resolvedPassword) {
    throw new Error("password is required");
  }

  return requestHangveJson("/auth/sign-in", {
    method: "POST",
    headers: {
      authorization: "Bearer",
      ...headers
    },
    body: {
      username: resolvedUsername,
      password: resolvedPassword
    },
    ...options
  });
}

async function getHangveCustomerMe({ token, ...options } = {}) {
  if (!token) {
    throw new Error("token is required");
  }

  return requestHangveJson("/customer/me", {
    method: "GET",
    token,
    ...options
  });
}

async function loginHangveAndGetSession(options = {}) {
  const loginResult = await loginHangve(options);
  const token = loginResult?.response?.data?.data?.token;

  if (!token) {
    const error = new Error("Failed to get Hangve token from login response");
    error.loginResult = loginResult;
    throw error;
  }

  const customerMeResult = await getHangveCustomerMe({
    token,
    ...options
  });
  const customer = customerMeResult?.response?.data?.data;

  if (!customer?.id) {
    const error = new Error("Failed to get Hangve customer info");
    error.customerMeResult = customerMeResult;
    throw error;
  }

  return {
    token,
    loginResult,
    customerMeResult,
    customer
  };
}

async function ensureHangveToken({ token, ...options } = {}) {
  if (token) {
    return {
      token,
      auth: {
        token
      }
    };
  }

  const session = await loginHangveAndGetSession(options);

  return {
    token: session.token,
    auth: session
  };
}

async function ensureHangveSearchContext({ token, customer, ...options } = {}) {
  if (token && customer?.id) {
    return {
      token,
      customer,
      auth: {
        token,
        customer
      }
    };
  }

  if (!token) {
    const session = await loginHangveAndGetSession(options);

    return {
      token: session.token,
      customer: session.customer,
      auth: session
    };
  }

  const customerMeResult = await getHangveCustomerMe({
    token,
    ...options
  });
  const resolvedCustomer = customerMeResult?.response?.data?.data;

  if (!resolvedCustomer?.id) {
    const error = new Error("Failed to get Hangve customer info from token");
    error.customerMeResult = customerMeResult;
    throw error;
  }

  return {
    token,
    customer: resolvedCustomer,
    auth: {
      token,
      customerMeResult,
      customer: resolvedCustomer
    }
  };
}

function resolveHangveDetailItemIds({ searchItems = [], itemId, detailLimit = 1 } = {}) {
  if (itemId !== undefined && itemId !== null && itemId !== "") {
    return [Number(itemId)].filter(Number.isFinite);
  }

  const normalizedLimit = Math.max(1, Number(detailLimit) || 1);

  return searchItems
    .map((item) => Number(item?.id))
    .filter(Number.isFinite)
    .slice(0, normalizedLimit);
}

async function getHangveItemDetail({ itemId, token, ...options } = {}) {
  const resolvedItemId = Number(itemId);

  if (!Number.isFinite(resolvedItemId)) {
    throw new Error("itemId is required");
  }

  const auth = await ensureHangveToken({
    token,
    ...options
  });
  const detailResult = await requestHangveJson(`/item/detail/${resolvedItemId}`, {
    method: "POST",
    token: auth.token,
    ...options
  });
  const normalized = normalizeHangveItemDetailPayload(detailResult?.response?.data?.data);

  return {
    auth: auth.auth,
    input: {
      itemId: resolvedItemId
    },
    detail: detailResult,
    normalized
  };
}

async function searchHangveItems({
  keySearch,
  url,
  categoryId = "",
  source,
  priceFrom = "",
  priceTo = "",
  page = 1,
  perPage = 30,
  priceOrder = "",
  salesOrder = "",
  isChinaFreeshiping = 0,
  token,
  userId,
  keyFacin,
  customer,
  includeDetail = false,
  detailItemId,
  detailLimit = 1,
  ...options
} = {}) {
  const resolvedSearchInput = resolveHangveSearchInput({
    keySearch,
    url,
    source
  });

  if (!resolvedSearchInput.keySearch) {
    throw new Error("keySearch is required");
  }

  const authContext = await ensureHangveSearchContext({
    token,
    customer,
    ...options
  });
  const activeToken = authContext.token;
  const activeCustomer = authContext.customer;

  const resolvedUserId = Number(userId ?? activeCustomer.id);

  if (!Number.isFinite(resolvedUserId)) {
    throw new Error("userId is required");
  }

  const resolvedKeyFacin =
    keyFacin ??
    createHangveKeyFacin({
      goSlim: activeCustomer.go_slim
    });

  const searchResult = await requestHangveJson("/item/search", {
    method: "POST",
    token: activeToken,
    params: {
      price_from: priceFrom,
      price_to: priceTo,
      page,
      per_page: perPage,
      price_order: priceOrder,
      sales_order: salesOrder,
      is_china_freeshiping: Number(isChinaFreeshiping),
      source: resolvedSearchInput.source
    },
    body: {
      key_search: resolvedSearchInput.keySearch,
      category_id: categoryId,
      user_id: resolvedUserId,
      key_facin: resolvedKeyFacin
    },
    ...options
  });

  let detailResults = [];

  if (isHangveOptionEnabled(includeDetail)) {
    const searchItems = searchResult?.response?.data?.data?.items ?? [];
    const resolvedDetailItemIds = resolveHangveDetailItemIds({
      searchItems,
      itemId: detailItemId,
      detailLimit
    });

    detailResults = await Promise.all(
      resolvedDetailItemIds.map((currentItemId) =>
        requestHangveJson(`/item/detail/${currentItemId}`, {
          method: "POST",
          token: activeToken,
          ...options
        }).then((detailResult) => ({
          itemId: currentItemId,
          detail: detailResult,
          normalized: normalizeHangveItemDetailPayload(detailResult?.response?.data?.data)
        }))
      )
    );
  }

  return {
    auth: authContext.auth,
    input: {
      keySearch: resolvedSearchInput.keySearch,
      categoryId,
      source: resolvedSearchInput.source,
      marketplace: resolvedSearchInput.marketplace,
      hostname: resolvedSearchInput.hostname,
      priceFrom,
      priceTo,
      page: Number(page),
      perPage: Number(perPage),
      priceOrder,
      salesOrder,
      isChinaFreeshiping: Number(isChinaFreeshiping),
      userId: resolvedUserId,
      keyFacin: resolvedKeyFacin,
      includeDetail: isHangveOptionEnabled(includeDetail),
      detailItemId: detailItemId === undefined ? undefined : Number(detailItemId),
      detailLimit: Number(detailLimit) || 1
    },
    search: searchResult,
    details: detailResults,
    normalizedDetails: detailResults.map((detailResult) => detailResult.normalized)
  };
}

async function getHangveItemFull(options = {}) {
  return searchHangveItems({
    ...options,
    includeDetail: true,
    detailLimit: options.detailLimit ?? 1
  });
}

module.exports = {
  DEFAULT_HANGVE_ACCOUNT,
  DEFAULT_HANGVE_CONFIG,
  HANGVE_CREDENTIALS_PATH,
  HANGVE_DIFF_TIME_OFFSET,
  HANGVE_KEY_FACIN_ALPHABET,
  HANGVE_KEY_FACIN_OFFSET,
  HANGVE_SOURCE_MAP,
  buildHangveKeyFacinBase,
  createHangveKeyFacin,
  defaultRandomHangveFiveDigits,
  defaultRandomHangveString,
  ensureHangveSearchContext,
  ensureHangveToken,
  getDefaultHangveHeaders,
  getHangveCustomerMe,
  getHangveItemDetail,
  getHangveItemFull,
  isHangveOptionEnabled,
  loadOptionalHangveCredentials,
  loginHangve,
  loginHangveAndGetSession,
  normalizeHangveSource,
  normalizeHangveItemDetailPayload,
  parseHangveMarketplaceUrl,
  parseHangveJsonValue,
  requestHangveJson,
  resolveHangveDetailItemIds,
  resolveHangveSearchInput,
  searchHangveItems
};
