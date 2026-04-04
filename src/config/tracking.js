const { loadOptionalJsonFile } = require("./files");

function normalizeTrackingPhoneNumber(value) {
  const normalized = String(value ?? "").trim();
  return normalized || "";
}

function loadTrackingCredentials({ loadJsonFile = loadOptionalJsonFile } = {}) {
  const { data, path } = loadJsonFile("tracking.credentials.json");

  return {
    path,
    phoneNumber: normalizeTrackingPhoneNumber(data?.phoneNumber)
  };
}

function resolveTracking17TrackPhoneNumber(requestPhoneNumber, defaultPhoneNumber) {
  return normalizeTrackingPhoneNumber(requestPhoneNumber) || normalizeTrackingPhoneNumber(defaultPhoneNumber);
}

module.exports = {
  loadTrackingCredentials,
  normalizeTrackingPhoneNumber,
  resolveTracking17TrackPhoneNumber
};
