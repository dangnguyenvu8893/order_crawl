const { getManagement1688DetailById } = require("./management1688-client");
const { getManagementTaobaoDetailById } = require("./management-taobao-client");
const { getPandamallItemDetails } = require("./pandamall-client");
const { getHangveItemFull } = require("./hangve-client");

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];

    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => chunks.push(chunk));
    process.stdin.on("end", () => resolve(chunks.join("").trim()));
    process.stdin.on("error", reject);
  });
}

function parseInput(rawValue) {
  if (!rawValue) {
    return {};
  }

  return JSON.parse(rawValue);
}

function writeOutput(value, exitCode = 0) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
  process.exitCode = exitCode;
}

function pickObject(value) {
  return value && typeof value === "object" ? value : {};
}

function buildSuccess({ provider, marketplace, input, raw = null, normalized = null, message = "" }) {
  return {
    ok: true,
    provider,
    marketplace,
    input,
    raw,
    normalized,
    message
  };
}

function buildFailure({ provider, marketplace, input, message, raw = null, error = null }) {
  return {
    ok: false,
    provider,
    marketplace,
    input,
    raw,
    normalized: null,
    message,
    error
  };
}

async function runGiangHuy1688(payload) {
  const itemId = String(payload.itemId ?? payload.id ?? "").trim();
  const result = await getManagement1688DetailById({
    ...payload,
    id: itemId
  });
  const raw = result?.response?.data?.data ?? null;

  if (!raw || typeof raw !== "object") {
    return buildFailure({
      provider: "gianghuy",
      marketplace: "1688",
      input: { itemId },
      message: "GiangHuy 1688 detail response does not contain product data"
    });
  }

  return buildSuccess({
    provider: "gianghuy",
    marketplace: "1688",
    input: { itemId },
    raw
  });
}

async function runGiangHuyTaobao(payload) {
  const itemId = String(payload.itemId ?? payload.id ?? "").trim();
  const result = await getManagementTaobaoDetailById({
    ...payload,
    id: itemId
  });
  const raw = result?.response?.data?.data ?? null;

  if (!raw || typeof raw !== "object") {
    return buildFailure({
      provider: "gianghuy",
      marketplace: "taobao",
      input: { itemId },
      message: "GiangHuy Taobao detail response does not contain product data"
    });
  }

  return buildSuccess({
    provider: "gianghuy",
    marketplace: "taobao",
    input: { itemId },
    raw
  });
}

async function runPandamallDetail(payload) {
  const input = {
    url: payload.url ?? "",
    itemId: payload.itemId ?? "",
    provider: payload.provider ?? ""
  };
  const result = await getPandamallItemDetails({
    ...payload,
    url: input.url,
    itemId: input.itemId,
    provider: input.provider
  });
  const raw = pickObject(result?.itemDetails?.response?.data);
  const message = String(raw?.message ?? "");

  if (raw?.status !== true) {
    return buildFailure({
      provider: "pandamall",
      marketplace: String(payload.marketplace ?? ""),
      input,
      raw,
      message: message || "PandaMall item detail request failed"
    });
  }

  return buildSuccess({
    provider: "pandamall",
    marketplace: String(payload.marketplace ?? ""),
    input,
    raw,
    message
  });
}

async function runHangveFull(payload) {
  const url = String(payload.url ?? payload.keySearch ?? "").trim();
  const result = await getHangveItemFull({
    ...payload,
    keySearch: url,
    detailLimit: payload.detailLimit ?? 1
  });
  const normalized = result?.normalizedDetails?.[0] ?? null;
  const raw = {
    searchCount: result?.search?.response?.data?.data?.items?.length ?? 0,
    detailCount: Array.isArray(result?.details) ? result.details.length : 0
  };

  if (!normalized || typeof normalized !== "object") {
    return buildFailure({
      provider: "hangve",
      marketplace: String(payload.marketplace ?? ""),
      input: { url },
      raw,
      message: "Hangve item detail response does not contain normalized data"
    });
  }

  return buildSuccess({
    provider: "hangve",
    marketplace: String(payload.marketplace ?? ""),
    input: { url },
    raw,
    normalized
  });
}

async function handleInput(input) {
  const action = String(input?.action ?? "").trim();
  const payload = pickObject(input?.payload);

  if (!action) {
    return buildFailure({
      provider: "",
      marketplace: "",
      input: {},
      message: "action is required"
    });
  }

  if (action === "gianghuy_1688_detail") {
    return runGiangHuy1688(payload);
  }

  if (action === "gianghuy_taobao_detail") {
    return runGiangHuyTaobao(payload);
  }

  if (action === "pandamall_detail") {
    return runPandamallDetail(payload);
  }

  if (action === "hangve_full") {
    return runHangveFull(payload);
  }

  return buildFailure({
    provider: "",
    marketplace: String(payload.marketplace ?? ""),
    input: payload,
    message: `Unsupported bridge action: ${action}`
  });
}

async function main() {
  const stdinValue = await readStdin();
  const argvValue = process.argv[2] ? String(process.argv[2]).trim() : "";
  const rawValue = stdinValue || argvValue;
  const input = parseInput(rawValue);
  const output = await handleInput(input);
  writeOutput(output, output.ok ? 0 : 1);
}

main().catch((error) => {
  writeOutput(
    buildFailure({
      provider: "",
      marketplace: "",
      input: {},
      message: error.message || "Unknown bridge error",
      error: {
        name: error.name,
        message: error.message
      }
    }),
    1
  );
});
