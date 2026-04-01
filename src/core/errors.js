class HttpError extends Error {
  constructor(message, statusCode = 500, code = "internal_error", details = undefined) {
    super(message);
    this.name = "HttpError";
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

function isAbortError(error) {
  return (
    error?.name === "AbortError" ||
    error?.code === "ABORT_ERR" ||
    error?.code === 20 ||
    /aborted/i.test(String(error?.message ?? ""))
  );
}

module.exports = {
  HttpError,
  isAbortError
};
