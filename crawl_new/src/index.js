const { getConfig } = require("./config");
const { generateSign } = require("./generate-sign");
const { getAccountDefault } = require("./account-client");
const { getManagement1688DetailById } = require("./management1688-client");
const { getManagementTaobaoDetailById } = require("./management-taobao-client");
const { getPandamallItemDetails, loginPandamall } = require("./pandamall-client");
const { getHangveItemDetail, getHangveItemFull, loginHangve, searchHangveItems } = require("./hangve-client");

const OPTION_NAME_MAP = {
  "access-key": "accessKey",
  "access-secret": "accessSecret",
  "end-user-id": "endUserId",
  "api-base-url": "apiBaseUrl",
  "is-no-cache": "isNoCache",
  language: "language",
  id: "id",
  "item-id": "itemId",
  "key-search": "keySearch",
  "category-id": "categoryId",
  phone: "phone",
  password: "password",
  username: "username",
  provider: "provider",
  url: "url",
  timestamp: "timestamp",
  "show-raw": "showRaw",
  "price-from": "priceFrom",
  "price-to": "priceTo",
  page: "page",
  "per-page": "perPage",
  "price-order": "priceOrder",
  "sales-order": "salesOrder",
  source: "source",
  "is-china-freeshiping": "isChinaFreeshiping",
  "include-detail": "includeDetail",
  "detail-limit": "detailLimit"
};

function parseArgs(argv) {
  const [command = "account-default", ...rest] = argv;
  const options = {};

  for (const part of rest) {
    if (!part.startsWith("--")) {
      continue;
    }

    const raw = part.slice(2);
    const separatorIndex = raw.indexOf("=");
    const rawKey = separatorIndex === -1 ? raw : raw.slice(0, separatorIndex);
    const rawValue = separatorIndex === -1 ? undefined : raw.slice(separatorIndex + 1);
    const key = OPTION_NAME_MAP[rawKey] ?? rawKey;

    if (rawValue === undefined) {
      options[key] = true;
      continue;
    }

    options[key] = rawKey === "timestamp" ? Number(rawValue) : rawValue;
  }

  return { command, options };
}

function printHelp() {
  console.log(
    [
      "Usage:",
      "  npm run sign",
      "  npm run sign -- --timestamp=1774764141932 --url=https://nhaphang.gianghuy.com",
      "  npm run account:default",
      "  npm run account:default -- --end-user-id=203922",
      "  npm run detail:1688",
      "  npm run detail:1688 -- --id=946758645543 --language=vi --is-no-cache=false",
      "  npm run detail:taobao",
      "  npm run detail:taobao -- --id=844351996614 --language=vi --is-no-cache=false",
      "  npm run pandamall:login",
      "  npm run pandamall:item-details -- --item-id=892407994374 --provider=alibaba",
      "  npm run pandamall:item-details -- --item-id=1016154115457 --provider=taobao",
      "  npm run pandamall:item-details -- --item-id=1013307248141 --provider=tmall",
      "  npm run pandamall:item-details -- --url='https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393'",
      "  npm run hangve:login -- --username=0987064673 --password=21731823",
      "  npm run hangve:item-search -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'",
      "  npm run hangve:item-search -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751' --include-detail",
      "  npm run hangve:item-detail -- --username=0987064673 --password=21731823 --item-id=1471325",
      "  npm run hangve:item-full -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'"
    ].join("\n")
  );
}

function redactSecrets(value, keyName = "") {
  if (Array.isArray(value)) {
    return value.map((item) => redactSecrets(item));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [entryKey, redactSecrets(entryValue, entryKey)])
    );
  }

  if (typeof value !== "string") {
    return value;
  }

  if (keyName === "password") {
    return "***REDACTED***";
  }

  if (keyName === "token") {
    return "***REDACTED***";
  }

  if (keyName === "authorization" && value.startsWith("Bearer ")) {
    return "Bearer ***REDACTED***";
  }

  return value;
}

async function runSign(options) {
  const config = getConfig(options);
  const result = generateSign({
    accessKey: config.accessKey,
    accessSecret: config.accessSecret,
    timestamp: config.timestamp,
    url: config.url
  });

  const output = {
    accessKey: config.accessKey,
    monaId: result.monaId,
    headerUrl: result.headerUrl,
    signTarget: result.signTarget,
    sign: result.sign
  };

  if (options.showRaw) {
    output.raw = result.raw;
  }

  console.log(JSON.stringify(output, null, 2));
}

async function runAccountDefault(options) {
  const result = await getAccountDefault(options);
  console.log(JSON.stringify(result, null, 2));
}

async function runDetail1688(options) {
  const result = await getManagement1688DetailById({
    ...options,
    id: options.id ?? "946758645543"
  });
  console.log(JSON.stringify(result, null, 2));
}

async function runDetailTaobao(options) {
  const result = await getManagementTaobaoDetailById({
    ...options,
    id: options.id ?? "844351996614"
  });
  console.log(JSON.stringify(result, null, 2));
}

async function runPandamallLogin(options) {
  const result = await loginPandamall(options);
  console.log(JSON.stringify(result, null, 2));
}

async function runPandamallItemDetails(options) {
  const result = await getPandamallItemDetails({
    ...options,
    itemId: options.itemId ?? process.env.PANDAMALL_ITEM_ID,
    provider: options.provider ?? process.env.PANDAMALL_PROVIDER
  });
  console.log(JSON.stringify(result, null, 2));
}

async function runHangveLogin(options) {
  const result = await loginHangve(options);
  console.log(JSON.stringify(options.showRaw ? result : redactSecrets(result), null, 2));
}

async function runHangveItemSearch(options) {
  const result = await searchHangveItems(options);
  console.log(JSON.stringify(options.showRaw ? result : redactSecrets(result), null, 2));
}

async function runHangveItemDetail(options) {
  const result = await getHangveItemDetail({
    ...options,
    itemId: options.itemId ?? options.id
  });
  console.log(JSON.stringify(options.showRaw ? result : redactSecrets(result), null, 2));
}

async function runHangveItemFull(options) {
  const result = await getHangveItemFull(options);
  console.log(JSON.stringify(options.showRaw ? result : redactSecrets(result), null, 2));
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));

  if (command === "help" || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  if (command === "sign") {
    await runSign(options);
    return;
  }

  if (command === "account-default") {
    await runAccountDefault(options);
    return;
  }

  if (command === "detail-1688") {
    await runDetail1688(options);
    return;
  }

  if (command === "detail-taobao") {
    await runDetailTaobao(options);
    return;
  }

  if (command === "pandamall-login") {
    await runPandamallLogin(options);
    return;
  }

  if (command === "pandamall-item-details") {
    await runPandamallItemDetails(options);
    return;
  }

  if (command === "hangve-login") {
    await runHangveLogin(options);
    return;
  }

  if (command === "hangve-item-search") {
    await runHangveItemSearch(options);
    return;
  }

  if (command === "hangve-item-detail") {
    await runHangveItemDetail(options);
    return;
  }

  if (command === "hangve-item-full") {
    await runHangveItemFull(options);
    return;
  }

  printHelp();
  process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
