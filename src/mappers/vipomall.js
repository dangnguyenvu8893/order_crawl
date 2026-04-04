const {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  normalizeNumericIdentifier,
  normalizeRangeList,
  normalizeString
} = require("../core/product");
const { computeCanonicalMaxPrice } = require("./utils");

function normalizeVipomallUrl(value) {
  const normalized = normalizeString(value);
  if (!normalized) {
    return "";
  }

  if (normalized.startsWith("//")) {
    return `https:${normalized}`;
  }

  return normalized;
}

function normalizeVipomallDescriptionHtml(value) {
  const normalized = normalizeString(value);
  if (!normalized) {
    return "";
  }

  return normalized.replaceAll('src="//', 'src="https://').replaceAll("src='//", "src='https://");
}

function extractVipomallVariantGroups(product) {
  return (product.product_prop_list ?? [])
    .map((property) => ({
      name: normalizeString(firstNonEmpty(property?.original_prop_name, property?.prop_name)),
      sourcePropertyId: normalizeNumericIdentifier(property?.prop_id),
      values: (property?.value_list ?? [])
        .map((value) => ({
          name: normalizeString(firstNonEmpty(value?.original_value_name, value?.value_name)),
          sourceValueId: normalizeNumericIdentifier(value?.value_id),
          image: normalizeVipomallUrl(firstNonEmpty(value?.img_url))
            ? normalizeVipomallUrl(firstNonEmpty(value?.img_url))
            : null
        }))
        .filter((value) => value.name)
    }))
    .filter((group) => group.name && group.values.length > 0);
}

function extractVipomallVariants(product) {
  return (product.product_sku_info_list ?? [])
    .map((sku) => ({
      skuId: normalizeString(sku?.sku_id),
      specAttrs: (sku?.sku_prop_list ?? [])
        .map((prop) => normalizeString(firstNonEmpty(prop?.original_value_name, prop?.value_name)))
        .filter(Boolean)
        .join("|"),
      quantity: coerceInt(firstNonEmpty(sku?.stock, sku?.min_purchase)),
      price: coerceFloat(sku?.price),
      promotionPrice: null,
      image: normalizeVipomallUrl(firstNonEmpty(sku?.img_url)) || null
    }))
    .filter((sku) => sku.skuId || sku.specAttrs);
}

function extractVipomallPriceRanges(product, marketplace, variants) {
  const rawRanges = (product.price_ranges ?? [])
    .map((range) => ({
      minQuantity: coerceInt(firstNonEmpty(range?.start_quantity, range?.startQuantity)),
      maxQuantity: null,
      price: coerceFloat(range?.price)
    }))
    .filter((range) => range.minQuantity !== null && range.price !== null);

  if (marketplace === "1688" && rawRanges.length > 0) {
    return normalizeRangeList(rawRanges);
  }

  const minPrice =
    coerceFloat(product?.sku_price_ranges?.min_price) ??
    rawRanges.reduce((currentMin, range) => {
      if (currentMin === null || range.price < currentMin) {
        return range.price;
      }
      return currentMin;
    }, null) ??
    variants.reduce((currentMin, variant) => {
      if (variant.price === null) {
        return currentMin;
      }
      if (currentMin === null || variant.price < currentMin) {
        return variant.price;
      }
      return currentMin;
    }, null);

  if (minPrice === null) {
    return [];
  }

  return [
    {
      minQuantity: 1,
      maxQuantity: 999999,
      price: minPrice
    }
  ];
}

function mapVipomallToCanonical(raw, context) {
  const product = raw?.data && typeof raw.data === "object" ? raw.data : {};
  const variants = extractVipomallVariants(product);
  const canonical = {
    provider: "vipomall",
    sourceType: context.marketplace,
    sourceId: normalizeString(firstNonEmpty(product.product_id, context.itemId)),
    inputUrl: context.inputUrl,
    url: context.canonicalUrl,
    name: normalizeString(firstNonEmpty(product.original_product_name, product.product_name)),
    images: dedupeStrings((product.main_img_url_list ?? []).map((image) => normalizeVipomallUrl(image)).filter(Boolean)),
    variantGroups: extractVipomallVariantGroups(product),
    variants,
    priceRanges: extractVipomallPriceRanges(product, context.marketplace, variants),
    maxPrice: normalizeString(
      firstNonEmpty(
        product?.sku_price_ranges?.max_price,
        product?.sku_price_ranges?.min_price,
        product?.price_ranges?.[0]?.price
      )
    ),
    descriptionHtml: normalizeVipomallDescriptionHtml(product.description)
  };

  canonical.maxPrice = computeCanonicalMaxPrice(canonical);
  return canonical;
}

module.exports = {
  mapVipomallToCanonical,
  normalizeVipomallDescriptionHtml,
  normalizeVipomallUrl
};
