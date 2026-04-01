const { getManagement1688DetailById } = require("../clients/management1688-client");
const { getManagementTaobaoDetailById } = require("../clients/management-taobao-client");
const { HttpError } = require("../core/errors");
const { mapGianghuyToCanonical } = require("../mappers/gianghuy");
const { buildProviderSignal } = require("./utils");

async function resolveProduct(context, { signal: externalSignal } = {}) {
  if (!["1688", "taobao"].includes(context.marketplace)) {
    throw new HttpError("GiangHuy does not support this marketplace in v1", 500, "provider_unsupported");
  }

  const signal = buildProviderSignal("gianghuy", externalSignal);
  const result =
    context.marketplace === "1688"
      ? await getManagement1688DetailById({ id: context.itemId, signal })
      : await getManagementTaobaoDetailById({ id: context.itemId, signal });
  const raw = result?.response?.data?.data;

  if (!raw || typeof raw !== "object") {
    throw new Error("GiangHuy detail response does not contain product data");
  }

  return {
    canonical: mapGianghuyToCanonical(raw, context),
    accountAttempts: []
  };
}

module.exports = {
  name: "gianghuy",
  resolveProduct
};
