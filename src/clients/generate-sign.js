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

function createSignContext({ accessKey, accessSecret, url }) {
  if (!accessKey) {
    throw new Error("accessKey is required");
  }

  if (!accessSecret) {
    throw new Error("accessSecret is required");
  }

  const headerUrl = normalizeHeaderUrl(url);
  const signTarget = headerUrl.replace(/^https?:\/\//i, "");

  return {
    accessKey,
    accessSecret,
    headerUrl,
    signTarget
  };
}

function normalizeExistingSignContext(context = {}) {
  if (
    context &&
    context.accessKey &&
    context.accessSecret &&
    context.headerUrl &&
    context.signTarget
  ) {
    return {
      accessKey: context.accessKey,
      accessSecret: context.accessSecret,
      headerUrl: context.headerUrl,
      signTarget: context.signTarget
    };
  }

  return createSignContext(context);
}

function generateSignFromContext(context, timestamp = Date.now()) {
  const signContext = normalizeExistingSignContext(context);
  const monaId = String(timestamp);
  const raw = `${signContext.accessKey}${monaId}${signContext.signTarget}${signContext.accessSecret}`;
  const sign = crypto.createHash("md5").update(raw).digest("hex");

  return {
    accessKey: signContext.accessKey,
    accessSecret: signContext.accessSecret,
    monaId,
    timestamp: Number(monaId),
    headerUrl: signContext.headerUrl,
    signTarget: signContext.signTarget,
    raw,
    sign
  };
}

function generateSign({ accessKey, accessSecret, timestamp = Date.now(), url }) {
  return generateSignFromContext(
    {
      accessKey,
      accessSecret,
      url
    },
    timestamp
  );
}

module.exports = {
  createSignContext,
  generateSignFromContext,
  normalizeExistingSignContext,
  normalizeHeaderUrl,
  buildSignTarget,
  generateSign
};
