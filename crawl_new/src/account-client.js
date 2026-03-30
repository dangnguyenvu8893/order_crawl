const { signedGetJson } = require("./signed-request");

async function getAccountDefault(overrides = {}) {
  return signedGetJson("/Account/default", overrides);
}

module.exports = {
  getAccountDefault
};
