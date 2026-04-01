const { getProviderTimeoutMs } = require("../config");

function buildProviderSignal(providerName, externalSignal) {
  const timeoutSignal = AbortSignal.timeout(getProviderTimeoutMs(providerName));
  return externalSignal ? AbortSignal.any([timeoutSignal, externalSignal]) : timeoutSignal;
}

module.exports = {
  buildProviderSignal
};
