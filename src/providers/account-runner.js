const { isAbortError } = require("../core/errors");
const { normalizeString } = require("../core/product");

function maskAccountUsername(username) {
  const normalized = normalizeString(username);
  if (normalized.length <= 4) {
    return normalized;
  }

  return `${"*".repeat(normalized.length - 4)}${normalized.slice(-4)}`;
}

async function runProviderWithOptionalAccounts({ accounts, label, userKey, execute }) {
  if (!accounts || accounts.length === 0) {
    try {
      return {
        result: await execute({}),
        accountAttempts: []
      };
    } catch (error) {
      error.accountAttempts = [];
      throw error;
    }
  }

  const accountAttempts = [];
  let lastError = null;

  for (let index = 0; index < accounts.length; index += 1) {
    const account = accounts[index];
    const maskedUsername = maskAccountUsername(account?.[userKey]);

    try {
      const result = await execute(account);
      accountAttempts.push({
        attempt: index + 1,
        usernameMasked: maskedUsername,
        success: true,
        message: `${label} account succeeded`
      });

      return {
        result,
        accountAttempts
      };
    } catch (error) {
      lastError = error;
      accountAttempts.push({
        attempt: index + 1,
        usernameMasked: maskedUsername,
        success: false,
        message: error.message
      });

      if (isAbortError(error)) {
        error.accountAttempts = accountAttempts;
        throw error;
      }
    }
  }

  if (lastError) {
    lastError.accountAttempts = accountAttempts;
    throw lastError;
  }

  const error = new Error(`${label} account rotation exhausted`);
  error.accountAttempts = accountAttempts;
  throw error;
}

module.exports = {
  runProviderWithOptionalAccounts
};
