function firstNonEmpty(...values) {
  for (const value of values) {
    if (value === null || value === undefined) {
      continue;
    }

    if (typeof value === "string" && !value.trim()) {
      continue;
    }

    if (Array.isArray(value) && value.length === 0) {
      continue;
    }

    if (value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0) {
      continue;
    }

    return value;
  }

  return undefined;
}

function normalizeString(value) {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value).trim();
}

function normalizeNumericIdentifier(value) {
  const normalized = normalizeString(value);
  return /^\d+$/.test(normalized) ? normalized : null;
}

function coerceFloat(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = normalizeString(value).replaceAll(",", "");
  if (!normalized) {
    return null;
  }

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function coerceInt(value) {
  const parsed = coerceFloat(value);
  return parsed === null ? null : Math.trunc(parsed);
}

function formatPriceString(value) {
  const parsed = coerceFloat(value);
  return parsed === null ? "" : parsed.toFixed(2);
}

function dedupeStrings(values) {
  const seen = new Set();
  const output = [];

  for (const value of values ?? []) {
    const normalized = normalizeString(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }

    seen.add(normalized);
    output.push(normalized);
  }

  return output;
}

function normalizeRangeList(ranges) {
  const normalized = (ranges ?? [])
    .map((range) => ({
      minQuantity: coerceInt(range?.minQuantity),
      maxQuantity: coerceInt(range?.maxQuantity),
      price: coerceFloat(range?.price)
    }))
    .filter((range) => range.minQuantity !== null && range.price !== null)
    .sort((left, right) => left.minQuantity - right.minQuantity || left.price - right.price);

  for (let index = 0; index < normalized.length; index += 1) {
    const current = normalized[index];
    if (current.maxQuantity !== null) {
      continue;
    }

    const next = normalized[index + 1];
    if (next && next.minQuantity > current.minQuantity) {
      current.maxQuantity = next.minQuantity - 1;
    }
  }

  return normalized;
}

function normalizeSpecAttrs(value) {
  const text = normalizeString(value);
  if (!text) {
    return "";
  }

  return text
    .split(/[;|]+/)
    .map((segment) => normalizeString(segment))
    .filter(Boolean)
    .join("|");
}

function serializeSpecAttrsForBackend(value) {
  const normalized = normalizeSpecAttrs(value);
  if (!normalized) {
    return "";
  }

  return normalized
    .split("|")
    .map((segment) => {
      if (!segment.includes("--")) {
        return segment;
      }

      return normalizeString(segment.split("--").slice(-1)[0]);
    })
    .filter(Boolean)
    .join("|");
}

function isHttpUrl(value) {
  try {
    const parsed = new URL(normalizeString(value));
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

module.exports = {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  formatPriceString,
  isHttpUrl,
  normalizeNumericIdentifier,
  normalizeRangeList,
  normalizeSpecAttrs,
  normalizeString,
  serializeSpecAttrsForBackend
};
