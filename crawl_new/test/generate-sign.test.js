const test = require("node:test");
const assert = require("node:assert/strict");

const { generateSign } = require("../src/generate-sign");

test("generateSign matches gianghuy sample sign", () => {
  const result = generateSign({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    timestamp: "1774764141932",
    url: "https://nhaphang.gianghuy.com"
  });

  assert.equal(result.sign, "8e88a8e186129c8fe91288451865358c");
  assert.equal(result.signTarget, "nhaphang.gianghuy.com");
  assert.equal(result.headerUrl, "https://nhaphang.gianghuy.com");
});

test("generateSign normalizes protocol and trailing slash", () => {
  const result = generateSign({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    timestamp: "1774764141932",
    url: "http://nhaphang.gianghuy.com/"
  });

  assert.equal(result.sign, "8e88a8e186129c8fe91288451865358c");
  assert.equal(result.signTarget, "nhaphang.gianghuy.com");
  assert.equal(result.headerUrl, "http://nhaphang.gianghuy.com");
});

test("generateSign matches 1688 detail sample sign", () => {
  const result = generateSign({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    timestamp: "1774765232406",
    url: "https://nhaphang.gianghuy.com"
  });

  assert.equal(result.sign, "802737758dd6fdec0e6a013fefe0d9ed");
});

test("generateSign matches taobao detail sample sign", () => {
  const result = generateSign({
    accessKey: "0856e51ae4394aed8229ffdc12fc5f79",
    accessSecret: "f270b8c27d91467b982002eef107fb80",
    timestamp: "1774765636404",
    url: "https://nhaphang.gianghuy.com"
  });

  assert.equal(result.sign, "a68dfc7fd9739ca27606988a87a7950b");
});
