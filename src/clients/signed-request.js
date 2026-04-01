const { getConfig } = require("./config");
const { generateSign } = require("./generate-sign");

function buildSignedHeaders(overrides = {}) {
  const config = getConfig(overrides);
  const signMeta = generateSign({
    accessKey: config.accessKey,
    accessSecret: config.accessSecret,
    timestamp: config.timestamp,
    url: config.url
  });

  const headers = {
    accept: "application/json",
    "access-key": config.accessKey,
    "end-user-id": String(config.endUserId),
    "mona-id": signMeta.monaId,
    sign: signMeta.sign,
    url: signMeta.headerUrl
  };

  return {
    config,
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
  signedGetJson
};
