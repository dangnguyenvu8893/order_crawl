const { ALLOWED_SOURCE_TYPES } = require("../config");
const {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  formatPriceString,
  isHttpUrl,
  normalizeNumericIdentifier,
  normalizeString,
  serializeSpecAttrsForBackend
} = require("../core/product");

function serializeSkuProperty(variantGroups) {
  return (variantGroups ?? [])
    .map((group) => ({
      name: normalizeString(group?.name),
      sourcePropertyId: normalizeNumericIdentifier(group?.sourcePropertyId),
      values: (group?.values ?? [])
        .map((value) => ({
          name: normalizeString(value?.name),
          sourceValueId: normalizeNumericIdentifier(value?.sourceValueId),
          image: normalizeString(value?.image) || null
        }))
        .filter((value) => value.name)
    }))
    .filter((group) => group.name && group.values.length > 0);
}

function serializeSku(variants) {
  return (variants ?? [])
    .map((variant) => {
      const payload = {
        canBookCount: (() => {
          const quantity = coerceInt(variant?.quantity);
          return quantity === null ? "" : String(quantity);
        })(),
        price: (() => {
          const price = firstNonEmpty(variant?.promotionPrice, variant?.price);
          const formatted = formatPriceString(price);
          return formatted || null;
        })(),
        specAttrs: serializeSpecAttrsForBackend(variant?.specAttrs)
      };

      const skuId = normalizeString(variant?.skuId);
      if (skuId) {
        payload.skuId = skuId;
      }

      return payload;
    })
    .filter((variant) => variant.skuId || variant.specAttrs);
}

function serializeRangePrices(priceRanges) {
  return (priceRanges ?? [])
    .map((range) => {
      const price = coerceFloat(range?.price);
      if (price === null) {
        return null;
      }

      return {
        beginAmount: coerceInt(range?.minQuantity) ?? 1,
        endAmount: coerceInt(range?.maxQuantity) ?? 999999,
        price,
        discountPrice: price
      };
    })
    .filter(Boolean);
}

function serializeBackendPayload(canonical) {
  return {
    name: normalizeString(canonical?.name),
    maxPrice: formatPriceString(canonical?.maxPrice),
    sourceId: normalizeString(canonical?.sourceId),
    sourceType: normalizeString(canonical?.sourceType),
    url: normalizeString(canonical?.url),
    images: dedupeStrings(canonical?.images ?? []),
    rangePrices: serializeRangePrices(canonical?.priceRanges),
    skuProperty: serializeSkuProperty(canonical?.variantGroups),
    sku: serializeSku(canonical?.variants)
  };
}

function hasPriceSignal(payload) {
  if (coerceFloat(payload?.maxPrice) !== null) {
    return true;
  }

  if (Array.isArray(payload?.rangePrices) && payload.rangePrices.some((range) => coerceFloat(range?.price) !== null)) {
    return true;
  }

  return Array.isArray(payload?.sku) && payload.sku.some((sku) => coerceFloat(sku?.price) !== null);
}

function getIncompleteReasons(payload) {
  const reasons = [];

  if (!normalizeString(payload?.name)) {
    reasons.push("missing name");
  }

  if (!normalizeString(payload?.sourceId)) {
    reasons.push("missing sourceId");
  }

  if (!ALLOWED_SOURCE_TYPES.includes(normalizeString(payload?.sourceType))) {
    reasons.push("invalid sourceType");
  }

  if (!isHttpUrl(payload?.url)) {
    reasons.push("invalid url");
  }

  if (!Array.isArray(payload?.images) || payload.images.length === 0) {
    reasons.push("missing images");
  }

  if (!hasPriceSignal(payload)) {
    reasons.push("missing price signal");
  }

  if (Array.isArray(payload?.skuProperty) && payload.skuProperty.length > 0) {
    if (!Array.isArray(payload?.sku) || payload.sku.length === 0) {
      reasons.push("missing sku");
    } else if (payload.sku.some((sku) => !normalizeString(sku?.specAttrs))) {
      reasons.push("sku specAttrs not mapped");
    }
  }

  return reasons;
}

function isCompleteBackendPayload(payload) {
  return getIncompleteReasons(payload).length === 0;
}

module.exports = {
  getIncompleteReasons,
  hasPriceSignal,
  isCompleteBackendPayload,
  serializeBackendPayload
};
