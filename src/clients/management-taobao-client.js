const { signedGetJson } = require("./signed-request");

function toBooleanString(value, fallback = "false") {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  const normalized = String(value).trim().toLowerCase();
  return normalized === "true" ? "true" : "false";
}

async function getManagementTaobaoDetailById(options = {}) {
  if (!options.id) {
    throw new Error("id is required");
  }

  const params = new URLSearchParams({
    Id: String(options.id),
    Language: options.language ?? "vi",
    IsNoCache: toBooleanString(options.isNoCache, "false")
  });

  return signedGetJson(`/ManagementTaobao/get-detail-by-id?${params.toString()}`, options);
}

module.exports = {
  getManagementTaobaoDetailById
};
