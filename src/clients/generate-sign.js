const crypto = require("node:crypto");

function normalizeHeaderUrl(url) {
  if (!url || !String(url).trim()) {
    throw new Error("url is required");
  }

  const trimmed = String(url).trim();
  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  return withProtocol.replace(/\/+$/, "");
}

function buildSignTarget(url) {
  return normalizeHeaderUrl(url).replace(/^https?:\/\//i, "");
}

function generateSign({ accessKey, accessSecret, timestamp = Date.now(), url }) {
  if (!accessKey) {
    throw new Error("accessKey is required");
  }

  if (!accessSecret) {
    throw new Error("accessSecret is required");
  }

  const headerUrl = normalizeHeaderUrl(url);
  const signTarget = buildSignTarget(url);
  const monaId = String(timestamp);
  const raw = `${accessKey}${monaId}${signTarget}${accessSecret}`;
  const sign = crypto.createHash("md5").update(raw).digest("hex");

  return {
    monaId,
    timestamp: Number(monaId),
    headerUrl,
    signTarget,
    raw,
    sign
  };
}

module.exports = {
  normalizeHeaderUrl,
  buildSignTarget,
  generateSign
};
