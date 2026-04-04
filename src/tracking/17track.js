const { TRACKING_17TRACK_PHONE_NUMBER } = require("../config");
const { resolveTracking17TrackPhoneNumber } = require("../config/tracking");
const { withTrackingPage } = require("./browser");
const { isTrackingTimeoutError } = require("./errors");
const {
  extract17TrackTimelineHtml,
  parse17TrackTimeline,
  sanitizeTrackingHtml
} = require("./html");

const SECURITY_CHALLENGE_ERROR =
  "Đơn hàng này yêu cầu xác thực thông tin bảo mật. Xin vui lòng liên hệ CSKH để được thông tin chi tiết.";

function build17TrackErrorPayload(trackingNumber, error, elapsedMs) {
  return {
    trackingNumber,
    matched: false,
    timeline: [],
    error: String(error?.message || error || "UPSTREAM_CHANGED"),
    elapsedMs
  };
}

async function closeTooltipIfPresent(page) {
  const tooltipButtons = [
    page.locator("button.tooltip__close").first(),
    page.getByRole("button", { name: /close/i }).first()
  ];

  for (const button of tooltipButtons) {
    try {
      if ((await button.count()) > 0) {
        await button.click({ timeout: 2_000 });
        await page.waitForTimeout(300);
        return true;
      }
    } catch {
      // Continue with the next selector.
    }
  }

  return false;
}

async function waitForReferencePrompt(page, timeoutMs = 3_000) {
  const prompt = page.locator("text=Please enter a reference").first();

  try {
    await prompt.waitFor({ state: "visible", timeout: timeoutMs });
    return true;
  } catch {
    return false;
  }
}

async function submitReferencePhoneNumber(page, phoneNumber) {
  if (!phoneNumber) {
    return {
      needed: true,
      success: false,
      error: "This tracking number requires reference information but no phone number is configured."
    };
  }

  const promptVisible = await waitForReferencePrompt(page);
  if (!promptVisible) {
    return {
      needed: false,
      success: true,
      error: ""
    };
  }

  const referenceLink = page.locator("span[aria-haspopup='dialog']", { hasText: /reference/i }).first();

  try {
    await referenceLink.click({ timeout: 3_000 });
  } catch {
    return {
      needed: true,
      success: false,
      error: "Không thể mở dialog reference trên 17track."
    };
  }

  const dialog = page.locator("div[role='dialog']").first();

  try {
    await dialog.waitFor({ state: "visible", timeout: 5_000 });
    const input = dialog.locator("input[name='phone_number_last_4'], input[id*='-form-item']").first();
    await input.fill(phoneNumber, { timeout: 5_000 });
    await dialog.locator("button[type='submit']").first().click({ timeout: 5_000 });
    await page.waitForTimeout(1_000);
    return {
      needed: true,
      success: true,
      error: ""
    };
  } catch {
    return {
      needed: true,
      success: false,
      error: "Không thể xác thực reference trên 17track."
    };
  }
}

async function waitForTimelineEvents(page, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  const eventLocator = page.locator("span.yq-time");

  while (Date.now() < deadline) {
    const count = await eventLocator.count();
    if (count > 0) {
      return count;
    }

    const bodyText = ((await page.locator("body").textContent().catch(() => "")) || "").toLowerCase();
    if (/captcha|security|verify/i.test(bodyText)) {
      throw new Error(SECURITY_CHALLENGE_ERROR);
    }

    await page.waitForTimeout(500);
  }

  return 0;
}

async function scrollTimeline(page) {
  const eventLocator = page.locator("span.yq-time");
  let lastCount = await eventLocator.count();

  if (lastCount === 0) {
    return 0;
  }

  for (let attempt = 0; attempt < 3; attempt += 1) {
    await eventLocator.nth(lastCount - 1).scrollIntoViewIfNeeded().catch(() => {});
    await page.waitForTimeout(500);

    const nextCount = await eventLocator.count();
    if (nextCount <= lastCount) {
      break;
    }

    lastCount = nextCount;
  }

  return lastCount;
}

async function configureVietnameseTranslation(page) {
  const translationContainer = page.locator("#yq-tracking-translate").first();

  if ((await translationContainer.count()) === 0) {
    return false;
  }

  try {
    await translationContainer.waitFor({ state: "visible", timeout: 5_000 });
  } catch {
    return false;
  }

  try {
    const combobox = translationContainer.locator("button[role='combobox']").first();
    if ((await combobox.count()) > 0) {
      const currentText = (await combobox.textContent()) || "";
      if (!/vietnamese/i.test(currentText)) {
        await combobox.click({ timeout: 2_000 });
        const option = page.getByText("Vietnamese", { exact: false }).first();
        await option.waitFor({ state: "visible", timeout: 2_000 });
        await option.click({ timeout: 2_000 });
        await page.waitForTimeout(500);
      }
    }
  } catch {
    // Translation language is optional. Leave the original content if selection fails.
  }

  try {
    const toggle = translationContainer.locator(
      "button[role='switch'], button.relative.inline-flex.h-6.w-11"
    ).first();

    if ((await toggle.count()) > 0) {
      const ariaChecked = await toggle.getAttribute("aria-checked");
      const className = await toggle.getAttribute("class");
      const alreadyEnabled = ariaChecked === "true" || /bg-blue-600/.test(className || "");

      if (!alreadyEnabled) {
        await toggle.click({ timeout: 2_000 });
      }
    }
  } catch {
    // Leave the untranslated content if the switch is unavailable.
  }

  const vietnameseKeywords = ["thành phố", "đã", "được", "giao", "nhận", "chuyển", "kho"];
  const deadline = Date.now() + 10_000;

  while (Date.now() < deadline) {
    const bodyText = ((await page.locator("body").textContent().catch(() => "")) || "").toLowerCase();
    if (vietnameseKeywords.some((keyword) => bodyText.includes(keyword))) {
      return true;
    }

    await page.waitForTimeout(500);
  }

  return false;
}

async function load17TrackHtml({ page, phoneNumber, trackingNumber }) {
  await page.goto(`https://t.17track.net/en#nums=${encodeURIComponent(trackingNumber)}`, {
    waitUntil: "domcontentloaded"
  });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1_000);

  await closeTooltipIfPresent(page);

  const referenceAttempt = await submitReferencePhoneNumber(page, phoneNumber);
  if (referenceAttempt.needed && !referenceAttempt.success) {
    throw new Error(referenceAttempt.error);
  }

  let eventCount = await waitForTimelineEvents(page);
  if (eventCount === 0 && (await waitForReferencePrompt(page, 500))) {
    const delayedReferenceAttempt = await submitReferencePhoneNumber(page, phoneNumber);
    if (delayedReferenceAttempt.needed && !delayedReferenceAttempt.success) {
      throw new Error(delayedReferenceAttempt.error);
    }

    eventCount = await waitForTimelineEvents(page);
  }

  await scrollTimeline(page);
  await configureVietnameseTranslation(page);
  eventCount = await scrollTimeline(page);

  if (eventCount === 0) {
    throw new Error(SECURITY_CHALLENGE_ERROR);
  }

  return page.content();
}

async function track17({ phoneNumber, signal, trackingNumber } = {}) {
  const normalizedTrackingNumber = String(trackingNumber ?? "").trim();
  if (!normalizedTrackingNumber) {
    return {
      payload: { error: "trackingNumber is required" },
      statusCode: 400
    };
  }

  const startedAt = Date.now();
  const effectivePhoneNumber = resolveTracking17TrackPhoneNumber(
    phoneNumber,
    TRACKING_17TRACK_PHONE_NUMBER
  );

  try {
    if (signal?.aborted) {
      throw signal.reason;
    }

    const html = await withTrackingPage(({ page }) =>
      load17TrackHtml({
        page,
        phoneNumber: effectivePhoneNumber,
        trackingNumber: normalizedTrackingNumber
      })
    );

    const timelineHtml = extract17TrackTimelineHtml(html);
    const parsed = parse17TrackTimeline(timelineHtml || html, normalizedTrackingNumber);

    return {
      payload: {
        ...parsed,
        elapsedMs: Date.now() - startedAt,
        safeHtml: timelineHtml ? sanitizeTrackingHtml(timelineHtml) : ""
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
      payload: build17TrackErrorPayload(normalizedTrackingNumber, error, Date.now() - startedAt),
      statusCode: 502
    };
  }
}

module.exports = {
  track17
};
