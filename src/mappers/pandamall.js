const {
  coerceFloat,
  coerceInt,
  firstNonEmpty,
  normalizeNumericIdentifier,
  normalizeString
} = require("../core/product");
const {
  buildPandamallSpecAttrs,
  buildPandamallValueNameMap,
  computeCanonicalMaxPrice,
  extractPandamallImages,
  extractPandamallName,
  extractPandamallPriceRanges
} = require("./utils");

function mapPandamallToCanonical(raw, context) {
  const product = raw?.data && typeof raw.data === "object" ? raw.data : {};
  const classify = product?.classify && typeof product.classify === "object" ? product.classify : {};
  const skuImages = classify?.skuImages && typeof classify.skuImages === "object" ? classify.skuImages : {};
  const valueNameMap = buildPandamallValueNameMap(classify);

  const variantGroups = [];
  for (const property of classify.skuProperties ?? []) {
    const propertyIdRaw = normalizeString(firstNonEmpty(property?.propID, property?.propId));
    const values = (property?.propValues ?? property?.values ?? [])
      .map((value) => {
        const valueIdRaw = normalizeString(firstNonEmpty(value?.valueID, value?.valueId));
        return {
          name: normalizeString(firstNonEmpty(value?.valueName, value?.name)),
          sourceValueId: normalizeNumericIdentifier(valueIdRaw),
          image:
            normalizeString(
              firstNonEmpty(
                skuImages[`${propertyIdRaw}:${valueIdRaw}`],
                value?.image,
                value?.imageUrl,
                value?.img
              )
            ) || null
        };
      })
      .filter((value) => value.name);

    const groupName = normalizeString(firstNonEmpty(property?.propName, property?.name));
    if (!groupName || values.length === 0) {
      continue;
    }

    variantGroups.push({
      name: groupName,
      sourcePropertyId: normalizeNumericIdentifier(propertyIdRaw),
      values
    });
  }

  const skuMappings = classify?.skuMappings && typeof classify.skuMappings === "object" ? classify.skuMappings : {};
  const variants = Object.entries(skuMappings)
    .map(([mappingKey, value]) => {
      let image = normalizeString(value?.imageURL);
      if (!image) {
        for (const segment of String(mappingKey).split("@")) {
          const candidate = normalizeString(skuImages[normalizeString(segment)]);
          if (candidate) {
            image = candidate;
            break;
          }
        }
      }

      return {
        skuId: normalizeString(firstNonEmpty(value?.skuID, value?.skuId)),
        specAttrs: buildPandamallSpecAttrs(firstNonEmpty(value?.sName, value?.classification), mappingKey, valueNameMap),
        quantity: coerceInt(firstNonEmpty(value?.quantity, value?.amountOnSale, value?.stock)),
        price: coerceFloat(value?.price),
        promotionPrice: coerceFloat(value?.promotionPrice),
        image: image || null
      };
    })
    .filter((variant) => variant.skuId || variant.specAttrs);

  const canonical = {
    provider: "pandamall",
    sourceType: context.marketplace,
    sourceId: normalizeString(firstNonEmpty(context.itemId, product.id)),
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name: extractPandamallName(product),
    images: extractPandamallImages(product),
    variantGroups,
    variants,
    priceRanges: extractPandamallPriceRanges(product, skuMappings),
    maxPrice: normalizeString(firstNonEmpty(product.maxPrice, product.price, product.promotionPrice)),
    descriptionHtml: normalizeString(product.description)
  };

  canonical.maxPrice = computeCanonicalMaxPrice(canonical);
  return canonical;
}

module.exports = {
  mapPandamallToCanonical
};
