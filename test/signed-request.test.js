const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildSignedHeaders,
  getGianghuySigningContext,
  resetGianghuySigningContextCache
} = require("../src/clients/signed-request");

test("gianghuy signing context is cached when only timestamp changes", () => {
  resetGianghuySigningContextCache();

  const firstContext = getGianghuySigningContext({
    accessKey: "ak",
    accessSecret: "sk",
    endUserId: 1,
    url: "https://nhaphang.gianghuy.com",
    apiBaseUrl: "https://mps.monamedia.net/api",
    timestamp: 1000
  });
  const secondContext = getGianghuySigningContext({
    accessKey: "ak",
    accessSecret: "sk",
    endUserId: 1,
    url: "https://nhaphang.gianghuy.com",
    apiBaseUrl: "https://mps.monamedia.net/api",
    timestamp: 2000,
    signal: new AbortController().signal
  });

  assert.equal(firstContext, secondContext);
});

test("buildSignedHeaders reuses static gianghuy auth fields and only changes sign by timestamp", () => {
  resetGianghuySigningContextCache();

  const first = buildSignedHeaders({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    endUserId: "203922",
    url: "https://nhaphang.gianghuy.com",
    timestamp: "1774764141932"
  });
  const second = buildSignedHeaders({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    endUserId: "203922",
    url: "https://nhaphang.gianghuy.com",
    timestamp: "1774765232406"
  });

  assert.equal(first.headers["access-key"], second.headers["access-key"]);
  assert.equal(first.headers.url, second.headers.url);
  assert.equal(first.headers["end-user-id"], second.headers["end-user-id"]);
  assert.notEqual(first.headers.sign, second.headers.sign);
  assert.equal(first.headers.sign, "8e88a8e186129c8fe91288451865358c");
  assert.equal(second.headers.sign, "802737758dd6fdec0e6a013fefe0d9ed");
});
