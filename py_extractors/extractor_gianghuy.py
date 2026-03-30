"""
Gianghuy Extractor — HTTP thuần, không cần Selenium.

Auth: MD5 signing per-request (stateless)
  sign = MD5(accessKey + timestamp_ms + "nhaphang.gianghuy.com" + accessSecret)

Hỗ trợ: 1688, Taobao, Tmall
  1688  → GET /Management1688/get-detail-by-id?Id={sourceId}
  Taobao/Tmall → GET /ManagementTaobao/get-detail-by-id?Id={sourceId}
"""
import hashlib
import logging
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests

from utils.url_resolver import resolve_product_url

logger = logging.getLogger(__name__)

API_BASE = "https://mps.monamedia.net/api"
DOMAIN   = "nhaphang.gianghuy.com"


class ExtractorGianghuy:

    def __init__(self) -> None:
        self.access_key    = os.getenv("GIANGHUY_ACCESS_KEY",    "0856e51ae4394aed8229ffdc12fc5f79")
        self.access_secret = os.getenv("GIANGHUY_ACCESS_SECRET", "f270b8c27d91467b982002eef107fb80")
        self.end_user_id   = os.getenv("GIANGHUY_END_USER_ID",   "203922")

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _generate_sign(self) -> Dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        raw       = self.access_key + timestamp + DOMAIN + self.access_secret
        sign      = hashlib.md5(raw.encode()).hexdigest()
        return {"timestamp": timestamp, "sign": sign}

    def _build_headers(self, sign_data: Dict[str, str]) -> Dict[str, str]:
        return {
            "accept":       "application/json",
            "access-key":   self.access_key,
            "end-user-id":  self.end_user_id,
            "mona-id":      sign_data["timestamp"],
            "sign":         sign_data["sign"],
            "url":          f"https://{DOMAIN}",
        }

    # ------------------------------------------------------------------
    # Platform detection
    # ------------------------------------------------------------------

    def _detect_platform(self, url: str) -> Dict[str, Optional[str]]:
        """
        Detect platform và extract sourceId từ URL.

        Patterns:
          1688:  detail.1688.com/offer/{id}.html
          Tmall: detail.tmall.com/item.htm?id={id}
                 item.tmall.com/item.htm?id={id}
          Taobao: item.taobao.com/item.htm?id={id}
        """
        url_lower = url.lower()

        if "1688.com" in url_lower:
            # /offer/962800347100.html
            m = re.search(r"/offer/(\d+)", url)
            if not m:
                m = re.search(r"[?&]id=(\d+)", url)
            return {"platform": "1688", "sourceId": m.group(1) if m else None}

        if "tmall.com" in url_lower:
            m = re.search(r"[?&]id=(\d+)", url)
            return {"platform": "tmall", "sourceId": m.group(1) if m else None}

        if "taobao.com" in url_lower:
            m = re.search(r"[?&]id=(\d+)", url)
            return {"platform": "taobao", "sourceId": m.group(1) if m else None}

        return {"platform": None, "sourceId": None}

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _call_api(self, platform: str, source_id: str) -> Dict[str, Any]:
        if platform == "1688":
            endpoint = f"/Management1688/get-detail-by-id?Id={source_id}&Language=vi&IsNoCache=false"
        else:
            endpoint = f"/ManagementTaobao/get-detail-by-id?Id={source_id}&Language=vi&IsNoCache=false"

        api_url   = API_BASE + endpoint
        sign_data = self._generate_sign()
        headers   = self._build_headers(sign_data)

        logger.info(f"[Gianghuy] Gọi API {platform}: {api_url}")
        resp = requests.get(api_url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def extract(self, url: str) -> Dict[str, Any]:
        original_url = url
        try:
            # Bước 1: Resolve URL (xử lý short link, mobile URL, v.v.)
            resolve_result = resolve_product_url(url)
            if not resolve_result.get("success"):
                # Thử dùng URL gốc nếu resolve thất bại (URL đã đầy đủ)
                final_url = url
                logger.warning(f"[Gianghuy] resolve_product_url thất bại, dùng URL gốc: {url}")
            else:
                final_url = resolve_result.get("final_url", url)

            # Bước 2: Detect platform + sourceId
            detect = self._detect_platform(final_url)
            platform  = detect["platform"]
            source_id = detect["sourceId"]

            if not platform:
                return {
                    "status":  "error",
                    "message": f"URL không được hỗ trợ: {final_url}. Chỉ hỗ trợ 1688, Taobao, Tmall.",
                    "url":     final_url,
                    "original_url": original_url,
                }

            if not source_id:
                return {
                    "status":  "error",
                    "message": f"Không tách được product ID từ URL: {final_url}",
                    "url":     final_url,
                    "original_url": original_url,
                }

            # Bước 3: Gọi Gianghuy API
            raw_json = self._call_api(platform, source_id)

            # API có thể trả về null hoặc {"data": null} — sản phẩm không tồn tại
            data_wrapper = (raw_json or {}).get("data") if raw_json else None
            if not raw_json or data_wrapper is None:
                return {
                    "status":  "error",
                    "message": f"Gianghuy API trả về null — sản phẩm không tồn tại hoặc không được hỗ trợ (id={source_id})",
                    "url":     final_url,
                    "original_url": original_url,
                }

            # Kiểm tra statusCode từ API
            status_code = data_wrapper.get("statusCode")
            if status_code and status_code != 200:
                return {
                    "status":  "error",
                    "message": f"Gianghuy API trả về statusCode={status_code}",
                    "url":     final_url,
                    "original_url": original_url,
                }

            return {
                "status":       "success",
                "url":          final_url,
                "original_url": original_url,
                "sourceType":   platform,
                "sourceId":     source_id,
                "raw_data":     raw_json,
            }

        except requests.HTTPError as e:
            logger.error(f"[Gianghuy] HTTP error: {e}")
            return {
                "status":  "error",
                "message": f"HTTP {e.response.status_code}: {str(e)}",
                "url":     original_url,
                "original_url": original_url,
            }
        except Exception as e:
            logger.error(f"[Gianghuy] Lỗi không xác định: {e}", exc_info=True)
            return {
                "status":  "error",
                "message": str(e),
                "url":     original_url,
                "original_url": original_url,
            }


extractor_gianghuy = ExtractorGianghuy()
