const { getVipomallProductByLink } = require("../clients/vipomall-client");
const { mapVipomallToCanonical } = require("../mappers/vipomall");
const { getSourceLabelContractReasons } = require("./source-label-contract");
const { buildProviderSignal } = require("./utils");

async function resolveProduct(context, { signal: externalSignal } = {}) {
  const signal = buildProviderSignal("vipomall", externalSignal);
  const response = await getVipomallProductByLink({
    productLink: context.canonicalUrl,
    signal
  });
  const raw = response?.response?.data;

  if (!raw || typeof raw !== "object") {
    throw new Error("VipoMall response does not contain product data");
  }

  if (String(raw.status) !== "01") {
    throw new Error(String(raw.message || "VipoMall request failed"));
  }

  const canonical = mapVipomallToCanonical(raw, context);
  const sourceLabelReasons = getSourceLabelContractReasons(canonical, context);
  if (sourceLabelReasons.length > 0) {
    throw new Error(`VipoMall degraded source labels: ${sourceLabelReasons.join(", ")}`);
  }

  return {
    canonical,
    accountAttempts: []
  };
}

module.exports = {
  name: "vipomall",
  resolveProduct
};
