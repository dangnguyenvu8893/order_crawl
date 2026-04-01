const DEFAULT_VIPOMALL_CONFIG = {
  apiBaseUrl: process.env.VIPOMALL_API_BASE_URL ?? "https://api-vipo.viettelpost.vn",
  origin: process.env.VIPOMALL_ORIGIN ?? "https://vipomall.vn",
  referer: process.env.VIPOMALL_REFERER ?? "https://vipomall.vn/",
  apiVersion: process.env.VIPOMALL_API_VERSION ?? "1.0.3",
  sessionId: process.env.VIPOMALL_SESSION_ID ?? "7d11ea52f552494b96bedfb4df01c7a8"
};

function getVipomallHeaders(config = {}) {
  return {
    accept: "application/json, text/plain, */*",
    "accept-language": "vi",
    "api-version": config.apiVersion,
    authorization: "Bearer null",
    "content-type": "application/json",
    origin: config.origin,
    priority: "u=1, i",
    referer: config.referer,
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "session-id": config.sessionId,
    "user-agent":
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
  };
}

async function requestVipomallJson(requestPath, { productLink, headers = {}, ...options } = {}) {
  if (!productLink) {
    throw new Error("productLink is required");
  }

  const config = {
    ...DEFAULT_VIPOMALL_CONFIG,
    ...options
  };
  const requestUrl = new URL(requestPath, config.apiBaseUrl).toString();
  const requestHeaders = {
    ...getVipomallHeaders(config),
    ...headers
  };

  const response = await fetch(requestUrl, {
    method: "POST",
    headers: requestHeaders,
    body: JSON.stringify({
      product_link: productLink
    }),
    signal: options.signal
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
      method: "POST",
      headers: requestHeaders,
      body: {
        product_link: productLink
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

async function getVipomallProductByLink({ productLink, ...options } = {}) {
  return requestVipomallJson("/listing/product/search/link", {
    productLink,
    ...options
  });
}

module.exports = {
  DEFAULT_VIPOMALL_CONFIG,
  getVipomallHeaders,
  getVipomallProductByLink,
  requestVipomallJson
};
