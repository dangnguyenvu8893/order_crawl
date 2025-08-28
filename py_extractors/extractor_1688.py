import re
import json
import time
import logging
from typing import Dict, Any, Optional

# Import Playwright kiểu an toàn (tham khảo cách tránh lỗi import như parser)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:  # ImportError khi môi trường local chưa có playwright
    sync_playwright = None  # sẽ kiểm tra ở runtime trước khi dùng

logger = logging.getLogger(__name__)


class Extractor1688:
    def __init__(self) -> None:
        self.context_full_regex = re.compile(
            r"window\\.context\\s*=\\s*\\(function\\([^)]*\\)\\s*{[\\s\\S]*?}\\s*\\)\\s*\\([^,]+,\\s*({[\\s\\S]*?})\\s*\\);",
            re.DOTALL,
        )

    def _generate_random_string(self, length: int, chars: str = 'abcdefghijklmnopqrstuvwxyz0123456789') -> str:
        return ''.join(__import__('random').choices(chars, k=length))

    def _generate_fake_cookies(self) -> Any:
        cookies = []
        base = [
            { 'name': 'cna', 'value': self._generate_random_string(22), 'domain': '.1688.com', 'path': '/' },
            { 'name': 'xlly_s', 'value': self._generate_random_string(32), 'domain': '.1688.com', 'path': '/' },
            { 'name': 'ali_apache_id', 'value': f"{__import__('random').randint(1000000000, 9999999999)}.{int(time.time())}", 'domain': '.1688.com', 'path': '/' },
        ]
        cookies.extend(base)
        # Thêm 5-15 cookie ngẫu nhiên
        for _ in range(__import__('random').randint(5, 15)):
            cookies.append({
                'name': self._generate_random_string(__import__('random').randint(8, 15), 'abcdefghijklmnopqrstuvwxyz'),
                'value': self._generate_random_string(__import__('random').randint(10, 30)),
                'domain': '.1688.com',
                'path': '/'
            })
        return cookies

    def _add_stealth_script(self, context: Any) -> None:
        context.add_init_script("""
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
window.chrome = { runtime: {} };
""")

    def _parse_with_node(self, json_str: str) -> Optional[Dict[str, Any]]:
        try:
            subprocess = __import__('subprocess')
            tempfile = __import__('tempfile')
            os = __import__('os')
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(f"""
try {{
  const data = {json_str};
  console.log(JSON.stringify(data));
}} catch (e) {{
  console.error('Error:' + e.message);
  process.exit(1);
}}
""")
                temp_file = f.name
            result = subprocess.run(['node', temp_file], capture_output=True, text=True, timeout=10)
            os.unlink(temp_file)
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            return None
        except Exception:
            return None

    def _extract_by_brace_counting(self, html: str) -> Optional[Dict[str, Any]]:
        start_marker = 'window.contextPath,'
        start_pos = html.find(start_marker)
        if start_pos == -1:
            return None
        json_start = start_pos + len(start_marker)
        brace_count = 0
        in_string = False
        escape_next = False
        json_end = None
        for i in range(json_start, len(html)):
            ch = html[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
        if json_end is None:
            return None
        json_str = html[json_start:json_end]
        try:
            return json.loads(json_str)
        except Exception:
            return self._parse_with_node(json_str)

    def can_handle(self, url: str) -> bool:
        return bool(re.search(r"detail\.1688\.com/offer/\d+\.html", url))

    def parse_product_id(self, url: str) -> Optional[str]:
        m = re.search(r"offer/(\d+)\.html", url)
        return m.group(1) if m else None

    def extract_window_context(self, html: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"window\\.context\\s*=\\s*({[\\s\\S]*?});", html)
        if m:
            s = m.group(1)
            try:
                return json.loads(s)
            except Exception:
                pass

        m2 = self.context_full_regex.search(html)
        if m2:
            s = m2.group(1)
            try:
                return json.loads(s)
            except Exception:
                # thử dùng Node eval object literal
                node_parsed = self._parse_with_node(s)
                if node_parsed is not None:
                    return node_parsed

        # fallback: brace counting
        bc = self._extract_by_brace_counting(html)
        if bc is not None:
            return bc
        return None

    def extract_result_json(self, html: str) -> Optional[Dict[str, Any]]:
        data = self.extract_window_context(html)
        if not data:
            return None
        if isinstance(data, dict) and "result" in data:
            return {"result": data["result"]}
        return data

    def extract(self, url: str) -> Dict[str, Any]:
        if not self.can_handle(url):
            return {"status": "error", "message": "Unsupported URL"}

        product_id = self.parse_product_id(url) or ""

        if sync_playwright is None:
            return {"status": "error", "message": "Playwright chưa được cài đặt trong môi trường chạy"}

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ])
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0",
                    "Referer": "https://www.1688.com/",
                },
            )
            # thêm cookies giả + stealth
            try:
                context.add_cookies(self._generate_fake_cookies())
            except Exception:
                pass
            self._add_stealth_script(context)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # chờ thêm để JS và XHR hoàn tất
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(5000)

            # nỗ lực truy xuất dữ liệu trực tiếp từ window thay vì chỉ regex
            raw = None
            try:
                ctx = page.evaluate("() => (typeof window !== 'undefined' && window.context) ? window.context : null")
                if isinstance(ctx, dict):
                    raw = {"result": ctx.get("result", ctx)}
            except Exception:
                pass

            # fallback: thử các biến khác thường gặp
            if raw is None:
                try:
                    init_data = page.evaluate("() => (window.__INIT_DATA__ || window.__GLOBAL_DATA__ || null)")
                    if isinstance(init_data, dict):
                        raw = {"result": init_data.get("result", init_data)}
                except Exception:
                    pass

            # cuối cùng mới dùng regex từ HTML
            html = page.content()
            if raw is None:
                raw = self.extract_result_json(html)

            # retry một lần nếu nghi ngờ captcha/verification hoặc thiếu window.context
            suspicious = (raw is None) or (('captcha' in html.lower()) or ('verification' in html.lower()) or ('_config_' in html))
            if suspicious:
                try:
                    page.close()
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass

                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Cache-Control": "max-age=0",
                        "Referer": "https://www.1688.com/",
                    },
                )
                try:
                    context.add_cookies(self._generate_fake_cookies())
                except Exception:
                    pass
                self._add_stealth_script(context)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                page.wait_for_timeout(5000)

                # thử lại đọc window + regex
                try:
                    ctx = page.evaluate("() => (typeof window !== 'undefined' && window.context) ? window.context : null")
                    if isinstance(ctx, dict):
                        raw = {"result": ctx.get("result", ctx)}
                except Exception:
                    pass
                if raw is None:
                    try:
                        init_data = page.evaluate("() => (window.__INIT_DATA__ || window.__GLOBAL_DATA__ || null)")
                        if isinstance(init_data, dict):
                            raw = {"result": init_data.get("result", init_data)}
                    except Exception:
                        pass
                html = page.content()
                if raw is None:
                    raw = self.extract_result_json(html)
            cookies_used = len(context.cookies())

            return {
                "status": "success" if raw else "error",
                "url": url,
                "timestamp": time.time(),
                "sourceType": "1688",
                "sourceId": product_id,
                "content_length": len(html),
                "cookies_used": cookies_used,
                "raw_data": raw,
            }
        finally:
            browser.close()
            playwright.stop()


extractor_1688 = Extractor1688()
