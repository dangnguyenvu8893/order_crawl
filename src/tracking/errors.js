class TrackingTimeoutError extends Error {
  constructor(message = "TIMEOUT") {
    super(message);
    this.name = "TrackingTimeoutError";
  }
}

function isTrackingTimeoutError(error) {
  return (
    error instanceof TrackingTimeoutError ||
    error?.name === "TrackingTimeoutError" ||
    error?.name === "TimeoutError" ||
    error?.code === "ETIMEDOUT" ||
    /timeout/i.test(String(error?.message ?? ""))
  );
}

module.exports = {
  TrackingTimeoutError,
  isTrackingTimeoutError
};
