const { loadOptionalJsonFile } = require("../config/files");

const { path: GIANGHUY_CREDENTIALS_PATH, data: credentials } = loadOptionalJsonFile("gianghuy.credentials.json");

const DEFAULT_CONFIG = {
  accessKey: process.env.GIANGHUY_ACCESS_KEY ?? credentials.accessKey,
  accessSecret: process.env.GIANGHUY_ACCESS_SECRET ?? credentials.accessSecret,
  endUserId: process.env.GIANGHUY_END_USER_ID ?? "203922",
  url: process.env.GIANGHUY_URL ?? "https://nhaphang.gianghuy.com",
  apiBaseUrl: process.env.MONA_API_BASE_URL ?? "https://mps.monamedia.net/api"
};

function getConfig(overrides = {}) {
  return {
    ...DEFAULT_CONFIG,
    ...overrides
  };
}

module.exports = {
  DEFAULT_CONFIG,
  getConfig,
  credentials,
  GIANGHUY_CREDENTIALS_PATH,
  loadOptionalCredentials: loadOptionalJsonFile
};
