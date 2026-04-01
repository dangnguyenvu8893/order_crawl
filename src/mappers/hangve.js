const {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  normalizeNumericIdentifier,
  normalizeSpecAttrs,
  normalizeString
} = require("../core/product");
const { computeCanonicalMaxPrice, mapRawRangesToCanonical } = require("./utils");

function normalizeHangveValues(group) {
  const output = [];

  if (Array.isArray(group?.valueEntries) && group.valueEntries.length > 0) {
    for (const value of group.valueEntries) {
      const name = normalizeString(firstNonEmpty(value?.nameOriginalCn, value?.nameOriginal, value?.name));
      if (!name) {
        continue;
      }

      output.push({
        name,
        sourceValueId: normalizeNumericIdentifier(value?.sourceValueId),
        image: normalizeString(value?.image) || null
      });
    }

    if (output.length > 0) {
      return output;
    }
  }

  const fallbackLists = [
    group?.valuesOriginalCn,
    group?.valuesOriginal,
    group?.values
  ];

  for (const list of fallbackLists) {
    if (!Array.isArray(list)) {
      continue;
    }

    for (const item of list) {
      const name = normalizeString(item);
      if (name) {
        output.push({
          name,
          sourceValueId: null,
          image: null
        });
      }
    }

    if (output.length > 0) {
      break;
    }
  }

  return output;
}

function mapHangveToCanonical(normalized, context) {
  const variantGroups = (normalized.variantGroups ?? [])
    .map((group) => ({
      name: normalizeString(firstNonEmpty(group?.nameOriginal, group?.name)),
      sourcePropertyId: normalizeNumericIdentifier(group?.sourcePropertyId),
      values: normalizeHangveValues(group)
    }))
    .filter((group) => group.name && group.values.length > 0);

  const variants = (normalized.skus ?? [])
    .map((sku) => ({
      skuId: normalizeString(sku?.skuId),
      specAttrs: normalizeSpecAttrs(firstNonEmpty(sku?.classification, sku?.classificationCn)),
      quantity: coerceInt(sku?.quantity),
      price: coerceFloat(sku?.price),
      promotionPrice: coerceFloat(sku?.promotionPrice),
      image: normalizeString(sku?.image) || null
    }))
    .filter((variant) => variant.skuId || variant.specAttrs);

  const canonical = {
    provider: "hangve",
    sourceType: context.marketplace,
    sourceId: normalizeString(firstNonEmpty(context.itemId, normalized.numIid)),
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name: normalizeString(normalized.title),
    images: dedupeStrings(normalized.images ?? []),
    variantGroups,
    variants,
    priceRanges: mapRawRangesToCanonical(normalized.priceRanges),
    maxPrice: normalizeString(firstNonEmpty(normalized.price, normalized.promotionPrice)),
    descriptionHtml: normalizeString(normalized.descriptionHtml)
  };

  canonical.maxPrice = computeCanonicalMaxPrice(canonical);
  return canonical;
}

module.exports = {
  mapHangveToCanonical
};
