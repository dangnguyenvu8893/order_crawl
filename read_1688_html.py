import argparse
import json
import sys
import re
import tempfile
import subprocess
from parser_1688 import parser_1688


def normalize_json_path(path: str) -> str:
    """Chuẩn hoá path: chấp nhận '$.a.b.c' hoặc 'a.b.c'"""
    if not path:
        return path
    return path[2:] if path.startswith('$.') else path


def main() -> None:
    cli = argparse.ArgumentParser(description="Đọc HTML 1688 local và trích xuất dữ liệu theo JSON path (mặc định: offerPriceRanges)")
    cli.add_argument("html_file", help="Đường dẫn file HTML cần đọc")
    cli.add_argument(
        "--path",
        dest="json_path",
        default="$.result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.offerPriceRanges",
        help="JSON path dạng dot (vd: $.result.data.mainPrice.fields.finalPriceModel.tradeWithoutPromotion.offerPriceRanges)",
    )
    cli.add_argument("--pretty", action="store_true", help="In JSON với indent=2")
    args = cli.parse_args()

    # Đảm bảo console in được UTF-8 trên Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        with open(args.html_file, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Không đọc được file: {e}"}, ensure_ascii=False))
        sys.exit(1)

    def extract_context_js_object(html_text: str) -> str | None:
        # Cách 1: regex đa dòng bắt đối tượng truyền vào function
        multi_pattern = re.compile(
            r"window\\.context\\s*=\\s*\\(function\\([^)]*\\)\\s*{[\\s\\S]*?}\\s*\\)\\s*\\([^,]+,\\s*({[\\s\\S]*?})\\s*\\);",
            re.DOTALL,
        )
        m = multi_pattern.search(html_text)
        if m:
            return m.group(1)

        # Cách 2: đếm dấu ngoặc từ marker
        marker = 'window.contextPath,'
        start = html_text.find(marker)
        if start == -1:
            return None
        i = start + len(marker)
        brace = 0
        in_str = False
        esc = False
        json_end = None
        while i < len(html_text):
            ch = html_text[i]
            if esc:
                esc = False
                i += 1
                continue
            if ch == '\\':
                esc = True
                i += 1
                continue
            if ch == '"':
                in_str = not in_str
                i += 1
                continue
            if not in_str:
                if ch == '{':
                    brace += 1
                elif ch == '}':
                    brace -= 1
                    if brace == 0:
                        json_end = i + 1
                        break
            i += 1
        if json_end is None:
            return None
        return html_text[start + len(marker):json_end]

    def parse_js_object(obj_literal: str) -> dict:
        # Thử parse strict JSON trước
        try:
            return json.loads(obj_literal)
        except Exception:
            pass
        # Dùng Node để eval object literal hợp lệ JS
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(
                    """
const util = require('util');
try {
  const data = (REPLACE_OBJECT);
  console.log(JSON.stringify(data));
} catch (e) {
  console.error('JS_EVAL_ERROR:' + e.message);
  process.exit(1);
}
""".replace("REPLACE_OBJECT", obj_literal)
                )
                temp_js = f.name
            result = subprocess.run(["node", temp_js], capture_output=True, text=True, encoding="utf-8", timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            raise RuntimeError(result.stderr.strip() or "Unknown Node error")
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Không thể eval JavaScript object: {e}"}, ensure_ascii=False))
            sys.exit(2)

    obj_str = extract_context_js_object(html)
    if not obj_str:
        print(json.dumps({"status": "error", "message": "Không trích xuất được window.context"}, ensure_ascii=False))
        sys.exit(2)
    context = parse_js_object(obj_str)

    path = normalize_json_path(args.json_path)
    value = parser_1688.get_nested_value(context, path)
    if value is None:
        print(json.dumps({"status": "error", "message": f"Không tìm thấy dữ liệu tại path: {args.json_path}"}, ensure_ascii=False))
        sys.exit(3)

    if args.pretty:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()


