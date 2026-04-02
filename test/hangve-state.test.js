const test = require("node:test");
const assert = require("node:assert/strict");

const { HANGVE_SESSION_TTL_MS } = require("../src/config");
const {
  getHangveCachedSession,
  rankHangveAccounts,
  recordHangveAccountResult,
  resetHangveRuntimeState,
  setHangveCachedSession
} = require("../src/providers/hangve-state");

test("hangve state caches session until ttl expires", () => {
  resetHangveRuntimeState();

  const session = {
    token: "hangve-token",
    customer: {
      id: 42
    }
  };

  setHangveCachedSession("0905687687", session, 1_000);
  assert.deepEqual(getHangveCachedSession("0905687687", 1_500), session);
  assert.equal(getHangveCachedSession("0905687687", 1_000 + HANGVE_SESSION_TTL_MS + 1), null);
});

test("hangve state ranks accounts by marketplace-specific completeness and latency", () => {
  resetHangveRuntimeState();

  const accounts = [
    { username: "0905687687", password: "1" },
    { username: "0905252513", password: "2" },
    { username: "0909521903", password: "3" }
  ];

  recordHangveAccountResult({
    marketplace: "1688",
    username: "0905687687",
    durationMs: 7_000,
    success: true,
    complete: false
  });
  recordHangveAccountResult({
    marketplace: "1688",
    username: "0905252513",
    durationMs: 1_500,
    success: true,
    complete: true
  });
  recordHangveAccountResult({
    marketplace: "1688",
    username: "0909521903",
    durationMs: 2_200,
    success: true,
    complete: true
  });

  assert.deepEqual(
    rankHangveAccounts("1688", accounts).map((account) => account.username),
    ["0905252513", "0909521903", "0905687687"]
  );
  assert.deepEqual(
    rankHangveAccounts("taobao", accounts).map((account) => account.username),
    accounts.map((account) => account.username)
  );
});
