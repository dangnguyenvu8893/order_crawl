const { withTrackingPage } = require("./browser");
const { isTrackingTimeoutError } = require("./errors");
const { parseChinaTrackingHtml, sanitizeTrackingHtml } = require("./html");

async function waitAndParseChinaPage(page, trackingNumber) {
  await page.locator("#shippingContent, #trackingContent").first().waitFor({
    state: "attached",
    timeout: 12_000
  });
  await page.waitForTimeout(1_000);

  const html = await page.content();
  const parsed = parseChinaTrackingHtml(html, trackingNumber);

  return {
    ...parsed,
    safeHtml: sanitizeTrackingHtml(parsed.rawHtml || "")
  };
}

async function trackChina({ signal, trackingNumber } = {}) {
  const normalizedTrackingNumber = String(trackingNumber ?? "").trim();
  if (!normalizedTrackingNumber) {
    return {
      payload: { error: "trackingNumber is required" },
      statusCode: 400
    };
  }

  const startedAt = Date.now();

  try {
    if (signal?.aborted) {
      throw signal.reason;
    }

    const parsed = await withTrackingPage(async ({ page }) => {
      await page.goto("https://amzcheck.net/", {
        waitUntil: "domcontentloaded"
      });

      const input = page.locator("#inp_num").first();
      await input.waitFor({ state: "visible", timeout: 10_000 });
      await input.fill(normalizedTrackingNumber);

      const submit = page.locator("#dnus").first();
      await submit.click({ timeout: 5_000 });

      let result = await waitAndParseChinaPage(page, normalizedTrackingNumber);

      if (result.timeline.length === 0 || result.matched === false) {
        await input.fill("");
        await input.type(normalizedTrackingNumber);
        await input.press("Enter");
        result = await waitAndParseChinaPage(page, normalizedTrackingNumber);
      }

      if (result.timeline.length === 0 || result.matched === false) {
        await page.evaluate(() => {
          if (typeof globalThis.checkChinaShippingForm === "function") {
            globalThis.checkChinaShippingForm();
          }
        }).catch(() => {});
        result = await waitAndParseChinaPage(page, normalizedTrackingNumber);
      }

      return result;
    });

    return {
      payload: {
        ...parsed,
        elapsedMs: Date.now() - startedAt
      },
      statusCode: 200
    };
  } catch (error) {
    if (isTrackingTimeoutError(error)) {
      return {
        payload: { error: "TIMEOUT" },
        statusCode: 408
      };
    }

    return {
      payload: {
        error: "UPSTREAM_CHANGED",
        message: String(error?.message || error || "Tracking failed")
      },
      statusCode: 502
    };
  }
}

module.exports = {
  trackChina
};
