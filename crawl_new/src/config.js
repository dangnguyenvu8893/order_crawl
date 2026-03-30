const fs = require("fs");
const path = require("path");

const GIANGHUY_CREDENTIALS_PATH = path.join(__dirname, "../config/gianghuy.credentials.json");

function loadOptionalCredentials(credentialsPath) {
  try {
    return JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") {
      return {};
    }

    throw error;
  }
}

const credentials = loadOptionalCredentials(GIANGHUY_CREDENTIALS_PATH);

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
  loadOptionalCredentials
};
