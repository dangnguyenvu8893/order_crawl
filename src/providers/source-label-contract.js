const { normalizeString } = require("../core/product");

const VIETNAMESE_DIACRITIC_REGEX = /[ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/i;
const GENERIC_SOURCE_LABELS = new Set([
  "thông số sản phẩm",
  "màu sắc chủ đạo",
  "kích cỡ",
  "màu sắc"
]);

function normalizeComparableLabel(value) {
  return normalizeString(value).toLowerCase().replace(/\s+/g, " ").trim();
}

function hasVietnameseDiacritics(value) {
  return VIETNAMESE_DIACRITIC_REGEX.test(normalizeString(value));
}

function getSourceLabelContractReasons(canonical, context) {
  if (!canonical || !context) {
    return [];
  }

  if (!["taobao", "tmall"].includes(normalizeComparableLabel(context.marketplace))) {
    return [];
  }

  const reasons = [];
  const variantGroups = Array.isArray(canonical.variantGroups) ? canonical.variantGroups : [];
  const variants = Array.isArray(canonical.variants) ? canonical.variants : [];

  for (const group of variantGroups) {
    const groupName = normalizeComparableLabel(group?.name);
    if (GENERIC_SOURCE_LABELS.has(groupName)) {
      reasons.push(`generic property label: ${group?.name}`);
    }

    if (hasVietnameseDiacritics(group?.name)) {
      reasons.push(`translated property label: ${group?.name}`);
    }

    for (const value of group?.values ?? []) {
      const valueName = normalizeComparableLabel(value?.name);
      if (GENERIC_SOURCE_LABELS.has(valueName)) {
        reasons.push(`generic value label: ${value?.name}`);
      }

      if (hasVietnameseDiacritics(value?.name)) {
        reasons.push(`translated value label: ${value?.name}`);
      }
    }
  }

  for (const variant of variants) {
    const specAttrs = normalizeComparableLabel(variant?.specAttrs);
    if (GENERIC_SOURCE_LABELS.has(specAttrs)) {
      reasons.push(`generic sku specAttrs: ${variant?.specAttrs}`);
    }

    if (hasVietnameseDiacritics(variant?.specAttrs)) {
      reasons.push(`translated sku specAttrs: ${variant?.specAttrs}`);
    }
  }

  return [...new Set(reasons)];
}

module.exports = {
  getSourceLabelContractReasons,
};
