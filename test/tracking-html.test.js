const test = require("node:test");
const assert = require("node:assert/strict");

const {
  extract17TrackTimelineHtml,
  parse17TrackTimeline,
  parseChinaTrackingHtml,
  sanitizeTrackingHtml
} = require("../src/tracking/html");

const TRACK17_HTML = `
  <div class="relative">
    <div class="flex gap-3">
      <span class="yq-time">2026-04-04 10:00</span>
      <span class="flex-1">[Thành phố Hà Nội] Đã giao kiện hàng thành công</span>
    </div>
    <script>alert("xss")</script>
  </div>
`;

const CHINA_HTML = `
  <div id="shippingContent">
    <span class="text-result gradient-border">Mã vận đơn 78952381275889</span>
    <ul class="timeline_tracking">
      <li class="event">
        <span><b>Quảng Châu</b></span>
        <div>Đang vận chuyển</div>
        <div class="context">Kiện hàng đã rời kho</div>
      </li>
    </ul>
  </div>
`;

test("extract17TrackTimelineHtml returns only containers that contain tracking events", () => {
  const timelineHtml = extract17TrackTimelineHtml(`
    <div class="relative"><div>ignore me</div></div>
    ${TRACK17_HTML}
  `);

  assert.match(timelineHtml, /yq-time/);
  assert.doesNotMatch(timelineHtml, /ignore me/);
});

test("sanitizeTrackingHtml removes script tags and event handlers", () => {
  const safeHtml = sanitizeTrackingHtml(
    `<div onclick="alert(1)"><script>alert(1)</script><a href="javascript:alert(1)">Link</a></div>`
  );

  assert.doesNotMatch(safeHtml, /script/i);
  assert.doesNotMatch(safeHtml, /onclick/i);
  assert.doesNotMatch(safeHtml, /javascript:/i);
});

test("parse17TrackTimeline parses city, status, and context from 17track timeline HTML", () => {
  const parsed = parse17TrackTimeline(
    `<div>Tracking #78952381275889</div>${TRACK17_HTML}`,
    "78952381275889"
  );

  assert.equal(parsed.trackingNumber, "78952381275889");
  assert.equal(parsed.matched, true);
  assert.deepEqual(parsed.timeline, [
    {
      city: "Hà Nội",
      context: "[Thành phố Hà Nội] Đã giao kiện hàng thành công",
      status: "Delivered"
    }
  ]);
});

test("parseChinaTrackingHtml parses legacy amzcheck timeline HTML", () => {
  const parsed = parseChinaTrackingHtml(CHINA_HTML, "78952381275889");

  assert.equal(parsed.trackingNumber, "78952381275889");
  assert.equal(parsed.matched, true);
  assert.deepEqual(parsed.timeline, [
    {
      city: "Quảng Châu",
      context: "Kiện hàng đã rời kho",
      status: "Đang vận chuyển"
    }
  ]);
});
