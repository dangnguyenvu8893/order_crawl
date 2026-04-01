const {
  coerceFloat,
  coerceInt,
  dedupeStrings,
  firstNonEmpty,
  formatPriceString,
  normalizeRangeList,
  normalizeString
} = require("../core/product");

function computeCanonicalMaxPrice(canonical) {
  const candidates = [];

  const existing = coerceFloat(canonical.maxPrice);
  if (existing !== null) {
    candidates.push(existing);
  }

  for (const range of canonical.priceRanges ?? []) {
    const price = coerceFloat(range.price);
    if (price !== null) {
      candidates.push(price);
    }
  }

  for (const variant of canonical.variants ?? []) {
    for (const value of [variant.promotionPrice, variant.price]) {
      const price = coerceFloat(value);
      if (price !== null) {
        candidates.push(price);
      }
    }
  }

  if (candidates.length === 0) {
    return "";
  }

  return formatPriceString(Math.max(...candidates));
}

function buildGianghuySpecAttrs(value, propertyNames) {
  const parts = normalizeString(value)
    .split(";")
    .map((segment) => normalizeString(segment))
    .filter(Boolean);

  if (propertyNames.length > 0 && propertyNames.length === parts.length) {
    return propertyNames.map((propertyName, index) => `${propertyName}--${parts[index]}`).join("|");
  }

  return parts.join("|");
}

function getNestedValue(value, path) {
  return path.split(".").reduce((current, segment) => {
    if (!current || typeof current !== "object") {
      return undefined;
    }

    return current[segment];
  }, value);
}

function extractPandamallImages(product) {
  const images = [];

  for (const item of product.thumbnails ?? []) {
    if (typeof item === "string") {
      const normalized = normalizeString(item);
      if (normalized) {
        images.push(normalized);
      }
      continue;
    }

    const src = normalizeString(item?.src);
    if (src) {
      images.push(src);
    }
  }

  if (images.length === 0) {
    for (const path of [
      "images",
      "imageList",
      "gallery",
      "photos",
      "imgs",
      "data.images",
      "item.images",
      "product.images"
    ]) {
      const list = path.includes(".") ? getNestedValue(product, path) : product[path];
      if (!Array.isArray(list) || list.length === 0) {
        continue;
      }

      for (const item of list) {
        if (typeof item === "string") {
          const normalized = normalizeString(item);
          if (normalized) {
            images.push(normalized);
          }
          continue;
        }

        for (const key of ["url", "imageUrl", "src", "image"]) {
          const value = normalizeString(item?.[key]);
          if (value) {
            images.push(value);
            break;
          }
        }
      }

      if (images.length > 0) {
        break;
      }
    }
  }

  const mainImage = normalizeString(firstNonEmpty(product.image, getNestedValue(product, "data.image")));
  if (mainImage) {
    images.unshift(mainImage);
  }

  return dedupeStrings(images);
}

function extractPandamallName(product) {
  for (const path of [
    "name",
    "title",
    "productName",
    "itemName",
    "data.title",
    "data.name",
    "item.title",
    "item.name"
  ]) {
    const value = path.includes(".") ? getNestedValue(product, path) : product[path];
    const normalized = normalizeString(value);
    if (normalized) {
      return normalized;
    }
  }

  return "";
}

function buildPandamallValueNameMap(classify) {
  const valueNameMap = new Map();

  for (const property of classify?.skuProperties ?? []) {
    const propertyId = normalizeString(firstNonEmpty(property?.propID, property?.propId));
    if (!propertyId) {
      continue;
    }

    for (const value of property?.propValues ?? property?.values ?? []) {
      const valueId = normalizeString(firstNonEmpty(value?.valueID, value?.valueId));
      const valueName = normalizeString(firstNonEmpty(value?.valueName, value?.name));

      if (valueId && valueName) {
        valueNameMap.set(`${propertyId}:${valueId}`, valueName);
      }
    }
  }

  return valueNameMap;
}

function normalizePandamallSpecAttrs(value) {
  const text = normalizeString(value);
  if (!text) {
    return "";
  }

  return text
    .split("@")
    .map((segment) => normalizeString(segment))
    .filter(Boolean)
    .map((segment) => {
      if (!segment.includes(":")) {
        return segment;
      }

      return normalizeString(segment.split(":").slice(-1)[0]);
    })
    .filter(Boolean)
    .join("|");
}

function buildPandamallSpecAttrs(rawValue, mappingKey, valueNameMap) {
  const preferred = normalizePandamallSpecAttrs(rawValue);
  if (preferred) {
    return preferred;
  }

  return normalizeString(mappingKey)
    .split("@")
    .map((segment) => normalizeString(segment))
    .filter(Boolean)
    .map((segment) => normalizeString(valueNameMap.get(segment) ?? segment))
    .filter(Boolean)
    .join("|");
}

function parsePandamallPriceRanges(priceRanges) {
  if (!priceRanges || typeof priceRanges !== "object") {
    return [];
  }

  const normalized = [];
  for (const [key, value] of Object.entries(priceRanges)) {
    const price = coerceFloat(value);
    if (price === null) {
      continue;
    }

    const betweenMatch = String(key).match(/^(\d+)\s*-\s*(\d+)$/);
    const plusMatch = String(key).match(/^(\d+)\s*\+$/);

    if (betweenMatch) {
      normalized.push({
        minQuantity: Number(betweenMatch[1]),
        maxQuantity: Number(betweenMatch[2]),
        price
      });
    } else if (plusMatch) {
      normalized.push({
        minQuantity: Number(plusMatch[1]),
        maxQuantity: null,
        price
      });
    }
  }

  return normalizeRangeList(normalized);
}

function extractPandamallPriceRanges(product, skuMappings) {
  const topLevel = parsePandamallPriceRanges(product.priceRanges);
  if (topLevel.length > 0) {
    return topLevel;
  }

  const nested = [];
  const prices = [];

  for (const value of Object.values(skuMappings ?? {})) {
    if (!value || typeof value !== "object") {
      continue;
    }

    if (value.priceRanges && typeof value.priceRanges === "object") {
      nested.push(...parsePandamallPriceRanges(value.priceRanges));
    }

    const price = coerceFloat(firstNonEmpty(value.promotionPrice, value.price));
    if (price !== null && price > 0) {
      prices.push(price);
    }
  }

  if (nested.length > 0) {
    return normalizeRangeList(nested);
  }

  if (prices.length > 0) {
    return [
      {
        minQuantity: 1,
        maxQuantity: 999999,
        price: Math.min(...prices)
      }
    ];
  }

  const fallbackPrice = coerceFloat(
    firstNonEmpty(product.price, product.minPrice, product.startPrice, getNestedValue(product, "data.price"))
  );

  if (fallbackPrice === null || fallbackPrice <= 0) {
    return [];
  }

  return [
    {
      minQuantity: 1,
      maxQuantity: 999999,
      price: fallbackPrice
    }
  ];
}

function mapRawRangesToCanonical(ranges, fieldMap = {}) {
  return normalizeRangeList(
    (ranges ?? []).map((item) => ({
      minQuantity: firstNonEmpty(item?.[fieldMap.minQuantity ?? "minQuantity"], item?.startQuantity),
      maxQuantity: firstNonEmpty(item?.[fieldMap.maxQuantity ?? "maxQuantity"], item?.endQuantity),
      price: firstNonEmpty(item?.[fieldMap.price ?? "price"], item?.promotionPrice)
    }))
  );
}

module.exports = {
  buildGianghuySpecAttrs,
  buildPandamallSpecAttrs,
  buildPandamallValueNameMap,
  computeCanonicalMaxPrice,
  extractPandamallImages,
  extractPandamallName,
  extractPandamallPriceRanges,
  getNestedValue,
  mapRawRangesToCanonical
};
