const fs = require("node:fs");

const { chromium } = require("playwright-core");

const {
  TRACKING_BROWSER_EXECUTABLE_PATH,
  TRACKING_BROWSER_HEADLESS,
  TRACKING_MAX_INFLIGHT,
  TRACKING_TIMEOUT_MS
} = require("../config");
const { TrackingTimeoutError } = require("./errors");

const DEFAULT_EXECUTABLE_PATHS = Object.freeze([
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium"
]);

const DEFAULT_LAUNCH_ARGS = Object.freeze([
  "--disable-dev-shm-usage",
  "--disable-setuid-sandbox",
  "--disable-web-security",
  "--no-sandbox"
]);

class Semaphore {
  constructor(maxConcurrency) {
    this.maxConcurrency = Math.max(1, Number(maxConcurrency) || 1);
    this.currentConcurrency = 0;
    this.queue = [];
  }

  async acquire() {
    if (this.currentConcurrency < this.maxConcurrency) {
      this.currentConcurrency += 1;
      return () => this.release();
    }

    return new Promise((resolve) => {
      this.queue.push(resolve);
    }).then(() => {
      this.currentConcurrency += 1;
      return () => this.release();
    });
  }

  release() {
    this.currentConcurrency = Math.max(0, this.currentConcurrency - 1);
    const next = this.queue.shift();
    if (next) {
      next();
    }
  }

  async use(task) {
    const release = await this.acquire();
    try {
      return await task();
    } finally {
      release();
    }
  }
}

const trackingSemaphore = new Semaphore(TRACKING_MAX_INFLIGHT);

function uniqueStrings(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))];
}

function resolveBrowserExecutablePath(explicitPath = TRACKING_BROWSER_EXECUTABLE_PATH) {
  const candidates = uniqueStrings([
    explicitPath,
    process.env.CHROME_BIN,
    process.env.CHROME_PATH,
    ...DEFAULT_EXECUTABLE_PATHS
  ]);

  return candidates.find((candidatePath) => fs.existsSync(candidatePath)) || "";
}

async function closeResource(resource) {
  if (!resource) {
    return;
  }

  try {
    await resource.close();
  } catch {
    // Ignore cleanup failures.
  }
}

async function withTrackingPage(run, options = {}) {
  const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
    ? options.timeoutMs
    : TRACKING_TIMEOUT_MS;

  return trackingSemaphore.use(async () => {
    const executablePath = resolveBrowserExecutablePath(options.executablePath);

    if (!executablePath) {
      throw new Error(
        "Could not find a Chromium executable for tracking. Set TRACKING_BROWSER_EXECUTABLE_PATH."
      );
    }

    let browser;
    let context;
    let page;
    let timeoutHandle;

    const execution = (async () => {
      browser = await chromium.launch({
        args: DEFAULT_LAUNCH_ARGS,
        executablePath,
        headless: options.headless ?? TRACKING_BROWSER_HEADLESS
      });

      context = await browser.newContext({
        locale: "en-US",
        userAgent:
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport: { width: 1366, height: 768 }
      });

      page = await context.newPage();
      page.setDefaultNavigationTimeout(Math.min(timeoutMs, 30_000));
      page.setDefaultTimeout(Math.min(timeoutMs, 15_000));

      return run({ browser, context, page });
    })();

    const timedExecution = new Promise((_, reject) => {
      timeoutHandle = setTimeout(() => {
        reject(new TrackingTimeoutError());
      }, timeoutMs);
    });

    try {
      return await Promise.race([execution, timedExecution]);
    } finally {
      clearTimeout(timeoutHandle);
      await closeResource(page);
      await closeResource(context);
      await closeResource(browser);
    }
  });
}

module.exports = {
  resolveBrowserExecutablePath,
  withTrackingPage
};
