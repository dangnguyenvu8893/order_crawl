const test = require("node:test");
const assert = require("node:assert/strict");
const { once } = require("node:events");

const { createServer } = require("../src/server/app");

async function withServer(handlers, callback) {
  const server = createServer(handlers);
  server.listen(0);
  await once(server, "listening");
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  try {
    await callback(baseUrl);
  } finally {
    server.close();
    await once(server, "close");
  }
}

test("GET /track/17track returns 405", async () => {
  await withServer({}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/17track`);
    const payload = await response.json();

    assert.equal(response.status, 405);
    assert.deepEqual(payload, { error: "method not allowed" });
  });
});

test("POST /track/17track returns 400 when tracking number is missing", async () => {
  await withServer({}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/17track`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({})
    });
    const payload = await response.json();

    assert.equal(response.status, 400);
    assert.deepEqual(payload, { error: "trackingNumber is required" });
  });
});

test("POST /track/17track forwards request phone number to the injected handler", async () => {
  await withServer({
    async track17Handler({ phoneNumber, trackingNumber }) {
      return {
        payload: {
          matched: true,
          phoneNumber,
          timeline: [],
          trackingNumber
        },
        statusCode: 200
      };
    }
  }, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/17track`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        phoneNumber: "0900000001",
        trackingNumber: "78952381275889"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.phoneNumber, "0900000001");
    assert.equal(payload.trackingNumber, "78952381275889");
  });
});

test("POST /track/17track returns 408 timeout payload from handler", async () => {
  await withServer({
    async track17Handler() {
      return {
        payload: { error: "TIMEOUT" },
        statusCode: 408
      };
    }
  }, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/17track`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        trackingNumber: "78952381275889"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 408);
    assert.deepEqual(payload, { error: "TIMEOUT" });
  });
});

test("POST /track/china returns 502 payload from injected handler", async () => {
  await withServer({
    async trackChinaHandler() {
      return {
        payload: {
          error: "UPSTREAM_CHANGED",
          message: "network changed"
        },
        statusCode: 502
      };
    }
  }, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/china`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        trackingNumber: "SF123456789"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 502);
    assert.deepEqual(payload, {
      error: "UPSTREAM_CHANGED",
      message: "network changed"
    });
  });
});

test("POST /track/china returns 200 with no-match payload from injected handler", async () => {
  await withServer({
    async trackChinaHandler({ trackingNumber }) {
      return {
        payload: {
          matched: false,
          safeHtml: "",
          timeline: [],
          trackingNumber
        },
        statusCode: 200
      };
    }
  }, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/track/china`, {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        trackingNumber: "SF123456789"
      })
    });
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.matched, false);
    assert.equal(payload.trackingNumber, "SF123456789");
  });
});
