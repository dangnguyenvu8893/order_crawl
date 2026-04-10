const { randomUUID } = require("node:crypto");

const SERVICE_NAME = "order-crawl";

function getHeaderValue(headers, name) {
  const value = headers?.[name];

  if (Array.isArray(value)) {
    return value.find(Boolean) || null;
  }

  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeForwardedFor(value) {
  if (!value) {
    return [];
  }

  return String(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function serializeError(error) {
  if (!(error instanceof Error)) {
    return error;
  }

  const serialized = {
    name: error.name,
    message: error.message,
    stack: error.stack
  };

  if (error.statusCode !== undefined) {
    serialized.statusCode = error.statusCode;
  }

  if (error.code !== undefined) {
    serialized.code = error.code;
  }

  if (error.details !== undefined) {
    serialized.details = error.details;
  }

  return serialized;
}

function createRequestContext(request) {
  const forwardedFor = normalizeForwardedFor(getHeaderValue(request.headers, "x-forwarded-for"));
  const remoteAddress = request.socket?.remoteAddress || null;

  return {
    clientApp: getHeaderValue(request.headers, "x-client-app"),
    clientScreen: getHeaderValue(request.headers, "x-client-screen"),
    forwardedFor,
    ip: forwardedFor[0] || remoteAddress,
    method: request.method,
    origin: getHeaderValue(request.headers, "origin"),
    path: request.url,
    referer: getHeaderValue(request.headers, "referer"),
    remoteAddress,
    requestId: getHeaderValue(request.headers, "x-request-id") || randomUUID(),
    userAgent: getHeaderValue(request.headers, "user-agent")
  };
}

function normalizeMeta(meta = {}) {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(meta)
      .filter(([, value]) => value !== undefined)
      .map(([key, value]) => [key, value instanceof Error ? serializeError(value) : value])
  );
}

function writeLog(level, message, meta = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE_NAME,
    message,
    ...normalizeMeta(meta)
  };

  const line = JSON.stringify(entry);

  if (level === "error") {
    console.error(line);
    return;
  }

  if (level === "warn") {
    console.warn(line);
    return;
  }

  console.log(line);
}

module.exports = {
  createRequestContext,
  error(message, meta) {
    writeLog("error", message, meta);
  },
  info(message, meta) {
    writeLog("info", message, meta);
  },
  warn(message, meta) {
    writeLog("warn", message, meta);
  }
};
