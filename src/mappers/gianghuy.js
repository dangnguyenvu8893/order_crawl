const {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  normalizeNumericIdentifier,
  normalizeString
} = require("../core/product");
const { buildGianghuySpecAttrs, computeCanonicalMaxPrice, mapRawRangesToCanonical } = require("./utils");

function mapGianghuyToCanonical(raw, context) {
  const images = dedupeStrings(
    (raw.medias ?? [])
      .filter((item) => item && typeof item === "object" && item.isVideo === false)
      .map((item) => item.link)
  );

  const propertyNames = [];
  const variantGroups = [];

  for (const property of raw.properties ?? []) {
    const name = normalizeString(property?.name);
    if (!name) {
      continue;
    }

    propertyNames.push(name);
    const values = (property.values ?? [])
      .map((value) => ({
        name: normalizeString(value?.name),
        sourceValueId: normalizeNumericIdentifier(value?.id),
        image: normalizeString(value?.imageUrl) || null
      }))
      .filter((value) => value.name);

    variantGroups.push({
      name,
      sourcePropertyId: normalizeNumericIdentifier(property?.id),
      values
    });
  }

  const variants = (raw.skuInfos ?? [])
    .map((sku) => {
      const image = normalizeString(normalizeString(sku?.imageUrls).split("|")[0]);
      return {
        skuId: normalizeString(firstNonEmpty(sku?.id, sku?.skuId)),
        specAttrs: buildGianghuySpecAttrs(sku?.skuPropertyName, propertyNames),
        quantity: coerceInt(firstNonEmpty(sku?.amountOnSale, sku?.quantity)),
        price: coerceFloat(sku?.price),
        promotionPrice: coerceFloat(sku?.promotionPrice),
        image: image || null
      };
    })
    .filter((variant) => variant.skuId || variant.specAttrs);

  const canonical = {
    provider: "gianghuy",
    sourceType: context.marketplace,
    sourceId: normalizeString(firstNonEmpty(context.itemId, raw.itemId)),
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name: normalizeString(firstNonEmpty(raw.title, raw.name, raw.titleTranslate)),
    images,
    variantGroups,
    variants,
    priceRanges: mapRawRangesToCanonical(raw.priceRanges, {
      minQuantity: "startQuantity",
      maxQuantity: "endQuantity",
      price: "price"
    }),
    maxPrice: normalizeString(firstNonEmpty(raw.maxPrice, raw.price, raw.promotionPrice)),
    descriptionHtml: normalizeString(raw.description)
  };

  canonical.maxPrice = computeCanonicalMaxPrice(canonical);
  return canonical;
}

module.exports = {
  mapGianghuyToCanonical
};
