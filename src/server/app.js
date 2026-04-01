const http = require("node:http");

const { HttpError } = require("../core/errors");
const { transformProductFromUrl } = require("../core/orchestrator");

function sendJson(response, statusCode, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body)
  });
  response.end(body);
}

function parseRequestBoolean(value) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  }

  return Boolean(value);
}

function readJsonBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";

    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1024 * 1024) {
        reject(new HttpError("request body is too large", 413, "payload_too_large"));
        request.destroy();
      }
    });
    request.on("end", () => {
      if (!body) {
        resolve({});
        return;
      }

      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new HttpError("request body must be valid JSON", 400, "invalid_json"));
      }
    });
    request.on("error", reject);
  });
}

function createServer({ transform = transformProductFromUrl } = {}) {
  return http.createServer(async (request, response) => {
    try {
      if (request.url === "/health") {
        if (request.method !== "GET") {
          sendJson(response, 405, { error: "method not allowed" });
          return;
        }

        sendJson(response, 200, { status: "ok" });
        return;
      }

      if (request.url === "/transform-product-from-url") {
        if (request.method !== "POST") {
          sendJson(response, 405, { error: "method not allowed" });
          return;
        }

        const body = await readJsonBody(request);
        const url = typeof body.url === "string" ? body.url : "";

        if (!url.trim()) {
          throw new HttpError("url is required", 400, "missing_url");
        }

        const payload = await transform(url, {
          debug: parseRequestBoolean(body.debug)
        });
        sendJson(response, 200, payload);
        return;
      }

      sendJson(response, 404, { error: "not found" });
    } catch (error) {
      const statusCode = error instanceof HttpError ? error.statusCode : 500;
      const payload = {
        error: error.message
      };

      if (error instanceof HttpError && error.details) {
        payload._meta = error.details;
      }

      sendJson(response, statusCode, payload);
    }
  });
}

module.exports = {
  createServer
};
