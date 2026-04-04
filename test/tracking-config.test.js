const test = require("node:test");
const assert = require("node:assert/strict");

const {
  loadTrackingCredentials,
  normalizeTrackingPhoneNumber,
  resolveTracking17TrackPhoneNumber
} = require("../src/config/tracking");

test("loadTrackingCredentials reads phone number from tracking.credentials.json", () => {
  const credentials = loadTrackingCredentials({
    loadJsonFile(filename) {
      assert.equal(filename, "tracking.credentials.json");
      return {
        path: "/tmp/tracking.credentials.json",
        data: {
          phoneNumber: " 0971037741 "
        }
      };
    }
  });

  assert.deepEqual(credentials, {
    path: "/tmp/tracking.credentials.json",
    phoneNumber: "0971037741"
  });
});

test("resolveTracking17TrackPhoneNumber prefers request phone number over JSON config", () => {
  assert.equal(resolveTracking17TrackPhoneNumber("0900000001", "0971037741"), "0900000001");
});

test("resolveTracking17TrackPhoneNumber falls back to JSON config when request phone number is empty", () => {
  assert.equal(resolveTracking17TrackPhoneNumber("", "0971037741"), "0971037741");
  assert.equal(resolveTracking17TrackPhoneNumber(null, "0971037741"), "0971037741");
});

test("normalizeTrackingPhoneNumber returns an empty string when no phone number is configured", () => {
  assert.equal(normalizeTrackingPhoneNumber(undefined), "");
});
