const cheerio = require("cheerio");

function loadHtml(html) {
  return cheerio.load(html || "", {
    decodeEntities: false
  });
}

function sanitizeTrackingHtml(html) {
  const $ = loadHtml(html);

  $("script, style, iframe, object, embed").remove();

  $("*").each((_, element) => {
    for (const [attributeName, attributeValue] of Object.entries(element.attribs ?? {})) {
      const normalizedName = attributeName.toLowerCase();

      if (normalizedName.startsWith("on")) {
        $(element).removeAttr(attributeName);
        continue;
      }

      if (
        (normalizedName === "href" || normalizedName === "src") &&
        typeof attributeValue === "string" &&
        attributeValue.trim().toLowerCase().startsWith("javascript:")
      ) {
        $(element).removeAttr(attributeName);
      }
    }
  });

  return $.root().html() || "";
}

function parseChinaTrackingHtml(html, trackingNumber) {
  const $ = loadHtml(html);
  const shippingContent = $("#shippingContent").first();
  const trackingContent = $("#trackingContent").first();
  const container = shippingContent.length > 0
    ? shippingContent
    : trackingContent.length > 0
      ? trackingContent
      : $.root();

  const titleText = container.find("span.text-result.gradient-border").first().text().trim();
  const fullText = container.text();
  const timeline = [];

  container.find("ul.timeline_tracking li.event").each((_, element) => {
    const node = $(element);
    const city = node.find("span b").first().text().trim();
    const context = node.find(".context").first().text().trim() || null;
    const primaryText = node.find("div").first().text().trim();

    timeline.push({
      city,
      context,
      status: primaryText
    });
  });

  return {
    matched: Boolean(trackingNumber && ((titleText && titleText.includes(trackingNumber)) || fullText.includes(trackingNumber))),
    rawHtml: $.html(container) || "",
    timeline,
    trackingNumber
  };
}

function extract17TrackTimelineHtml(html) {
  const $ = loadHtml(html);
  const fragments = [];
  const seen = new Set();

  $("div.relative").each((_, element) => {
    if ($(element).find("span.yq-time").length === 0) {
      return;
    }

    const fragment = $.html(element) || "";
    if (fragment && !seen.has(fragment)) {
      seen.add(fragment);
      fragments.push(fragment);
    }
  });

  if (fragments.length > 0) {
    return fragments.join("\n");
  }

  $("span.yq-time").each((_, element) => {
    const container = $(element).closest("div.flex.gap-3");
    const fallbackContainer = container.length > 0 ? container : $(element).parent();
    const fragment = $.html(fallbackContainer) || "";

    if (fragment && !seen.has(fragment)) {
      seen.add(fragment);
      fragments.push(fragment);
    }
  });

  return fragments.join("\n");
}

function extractCityFromDescription(description) {
  const patterns = [
    /\[(?:Thành phố|City|城市)\s*([^\]]+)\]/i,
    /\[([^\]]+)\]\s*[^[]*$/i,
    /Thành phố\s+([^\s,.[\]]+)/i,
    /City\s+([^\s,.[\]]+)/i
  ];

  for (const pattern of patterns) {
    const match = description.match(pattern);
    if (match?.[1]) {
      return match[1].replace(/^(Thành phố|City|城市)\s*/i, "").trim();
    }
  }

  return "";
}

function inferTrackingStatus(htmlFragment, description) {
  const normalizedHtml = String(htmlFragment || "").toLowerCase();
  const normalizedDescription = String(description || "").toLowerCase();
  const haystack = `${normalizedHtml} ${normalizedDescription}`;

  if (/delivered|đã giao|đã nhận/.test(haystack)) {
    return "Delivered";
  }

  if (/out for delivery|đang giao/.test(haystack)) {
    return "Out for Delivery";
  }

  if (/not found|không tìm thấy/.test(haystack)) {
    return "Not found";
  }

  if (/alert/.test(haystack)) {
    return "Alert";
  }

  if (/expired/.test(haystack)) {
    return "Expired";
  }

  if (/pick up|pickup/.test(haystack)) {
    return "Pick Up";
  }

  if (/info received/.test(haystack)) {
    return "Info received";
  }

  return "In Transit";
}

function parse17TrackTimeline(html, trackingNumber) {
  const $ = loadHtml(html);
  const timeline = [];
  const eventNodes = [];
  const seenNodes = new Set();

  $("div.flex.gap-3").each((_, element) => {
    if ($(element).find("span.yq-time").length === 0) {
      return;
    }

    if (!seenNodes.has(element)) {
      seenNodes.add(element);
      eventNodes.push(element);
    }
  });

  if (eventNodes.length === 0) {
    $("span.yq-time").each((_, element) => {
      const eventNode = $(element).closest("div.flex.gap-3")[0] || $(element).parent()[0];

      if (eventNode && !seenNodes.has(eventNode)) {
        seenNodes.add(eventNode);
        eventNodes.push(eventNode);
      }
    });
  }

  for (const eventNode of eventNodes) {
    const node = $(eventNode);
    const timestamp = node.find("span.yq-time").first().text().trim();

    const descriptionSelectors = [
      "span.flex-1",
      "span.text-text-primary",
      "span.text-text-secondary",
      "[class*='flex-1']"
    ];

    let description = "";
    for (const selector of descriptionSelectors) {
      const text = node.find(selector).first().text().trim();
      if (text) {
        description = text;
        break;
      }
    }

    if (!description) {
      description = node.text().replace(timestamp, "").replace(/\s+/g, " ").trim();
    }

    if (!description) {
      continue;
    }

    timeline.push({
      city: extractCityFromDescription(description) || "Unknown",
      context: description,
      status: inferTrackingStatus($.html(node) || "", description)
    });
  }

  return {
    matched: Boolean(trackingNumber && $.root().text().includes(trackingNumber)),
    rawHtml: html || "",
    timeline,
    trackingNumber
  };
}

module.exports = {
  extract17TrackTimelineHtml,
  parse17TrackTimeline,
  parseChinaTrackingHtml,
  sanitizeTrackingHtml
};
