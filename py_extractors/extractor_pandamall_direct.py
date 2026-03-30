"""
Pandamall Direct API Extractor — bypass Cloudflare hoàn toàn.

Thay thế extractor_pandamall.py (Selenium-based) bằng HTTP call trực tiếp.
Auth dùng DPoP (RFC 9449 variant của Pandamall):
  - Authorization: Bearer <access_token>
  - DPoP: <ES256 signed proof JWT>
  - Signed với EC P-256 privateKey từ localStorage

Session inject 1 lần qua /pandamall-inject-session, không cần login lại.
"""
import base64
import hashlib
import json
import logging
import os
import pickle
import time
import uuid
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Import PyJWT + cryptography
try:
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric.ec import (
        EllipticCurvePrivateNumbers,
        EllipticCurvePublicNumbers,
        SECP256R1,
    )
    DPOP_AVAILABLE = True
except ImportError as _e:
    logger.warning(f"PyJWT/cryptography không khả dụng: {_e}")
    DPOP_AVAILABLE = False


API_ENDPOINT = "https://api.pandamall.vn/api/pandamall/v1/item/details"
PANDAMALL_ORIGIN = "https://pandamall.vn"
# htu dùng relative path (theo format Pandamall thực tế, không phải RFC chuẩn)
DPOP_HTU = "/api/pandamall/v1/item/details"


def _b64url_decode(s: str) -> bytes:
    """Base64url decode với padding tự động."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _load_private_key(private_key_jwk: dict):
    """Load EC P-256 private key từ JWK dict."""
    d = int.from_bytes(_b64url_decode(private_key_jwk["d"]), "big")
    x = int.from_bytes(_b64url_decode(private_key_jwk["x"]), "big")
    y = int.from_bytes(_b64url_decode(private_key_jwk["y"]), "big")
    return EllipticCurvePrivateNumbers(
        d, EllipticCurvePublicNumbers(x, y, SECP256R1())
    ).private_key()


def _create_dpop_proof(private_key_jwk: dict, access_token: str) -> str:
    """
    Tạo DPoP proof JWT theo format thực tế của Pandamall:
    - typ: "dpop" (khác RFC chuẩn "dpop+jwt")
    - htu: relative path "/api/pandamall/v1/item/details"
    - htm: "POST"
    - ath: base64url(SHA-256(access_token)) — RFC 9449
    """
    private_key = _load_private_key(private_key_jwk)

    pub_jwk = {
        "crv": "P-256",
        "kty": "EC",
        "x": private_key_jwk["x"],
        "y": private_key_jwk["y"],
    }

    dpop_headers = {
        "typ": "dpop",
        "alg": "ES256",
        "jwk": pub_jwk,
    }

    ath = base64.urlsafe_b64encode(
        hashlib.sha256(access_token.encode("ascii")).digest()
    ).rstrip(b"=").decode()

    dpop_payload = {
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
        "htu": DPOP_HTU,
        "htm": "POST",
        "ath": ath,
    }

    token = pyjwt.encode(
        dpop_payload,
        private_key,
        algorithm="ES256",
        headers=dpop_headers,
    )
    return token


class ExtractorPandamallDirect:
    """Direct HTTP extractor — không cần Selenium, không bị Cloudflare chặn."""

    def __init__(self) -> None:
        self.session_dir = "/app/logs/sessions"
        self.session_file = os.path.join(self.session_dir, "pandamall_session.pkl")
        self.session_ttl = 7 * 24 * 3600

    # ========== Session Load ==========

    def _load_session(self) -> Optional[dict]:
        """Load session từ file."""
        try:
            if not os.path.exists(self.session_file):
                return None
            with open(self.session_file, "rb") as f:
                data = pickle.load(f)
            if data.get("expires_at", 0) > time.time():
                return data
            logger.info("Session đã hết hạn")
        except Exception as e:
            logger.error(f"Lỗi load session: {e}")
        return None

    def _get_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Lấy access_token, privateKey từ session.
        Trả None nếu session không có đủ thông tin.
        """
        session = self._load_session()
        if not session:
            return None

        local_storage_raw = session.get("local_storage")
        if not local_storage_raw:
            return None

        try:
            local_storage = json.loads(local_storage_raw)
        except Exception:
            return None

        # access_token
        pandamall_user_raw = local_storage.get("pandamall_user")
        if not pandamall_user_raw:
            return None
        try:
            pandamall_user = json.loads(pandamall_user_raw)
        except Exception:
            return None
        access_token = pandamall_user.get("access_token")
        if not access_token:
            return None

        # privateKey
        private_key_raw = local_storage.get("privateKey")
        if not private_key_raw:
            return None
        try:
            private_key_jwk = json.loads(private_key_raw)
        except Exception:
            return None

        # cookie_string
        cookie_string = session.get("cookie_string", "")

        return {
            "access_token": access_token,
            "private_key_jwk": private_key_jwk,
            "cookie_string": cookie_string,
        }

    # ========== API Call ==========

    def call_api(self, source_url: str) -> Dict[str, Any]:
        """
        Gọi Pandamall API trực tiếp với DPoP auth.
        Trả về raw API response dict.
        """
        if not DPOP_AVAILABLE:
            return {"status": "error", "message": "PyJWT/cryptography chưa được cài đặt"}

        creds = self._get_credentials()
        if not creds:
            return {
                "status": "error",
                "message": "Chưa có session pandamall. Gọi /pandamall-inject-session trước.",
            }

        dpop_proof = _create_dpop_proof(creds["private_key_jwk"], creds["access_token"])

        headers = {
            "Authorization": f"Bearer {creds['access_token']}",
            "DPoP": dpop_proof,
            "Content-Type": "application/json",
            "Origin": PANDAMALL_ORIGIN,
            "Referer": f"{PANDAMALL_ORIGIN}/",
            "Cookie": creds["cookie_string"],
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }

        body = {"sourceUrl": source_url}

        try:
            resp = requests.post(API_ENDPOINT, json=body, headers=headers, timeout=15)
            logger.info(f"Pandamall API → {resp.status_code} for {source_url[:80]}")
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                return {"status": "success", "data": data, "http_status": 200}
            return {
                "status": "error",
                "message": f"API returned {resp.status_code}: {data.get('message', '')}",
                "http_status": resp.status_code,
                "raw": data,
            }
        except Exception as e:
            logger.error(f"Lỗi gọi Pandamall API: {e}")
            return {"status": "error", "message": str(e)}

    # ========== Public extract() — cùng interface với extractor_pandamall ==========

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Interface giống extractor_pandamall.extract() để dùng chung transformer.
        """
        import re

        # Extract item_id từ URL
        if "1688.com" in url:
            m = re.search(r"/offer/(\d+)\.html", url)
        else:
            m = re.search(r"[?&]id=(\d+)", url)
        item_id = m.group(1) if m else ""

        # Detect provider
        if "1688.com" in url:
            provider = "1688"
        elif "tmall.com" in url:
            provider = "tmall"
        else:
            provider = "taobao"

        api_result = self.call_api(url)

        return {
            "status": api_result["status"],
            "url": url,
            "original_url": url,
            "timestamp": time.time(),
            "sourceType": "pandamall",
            "sourceId": item_id,
            "provider": provider,
            "raw_data": api_result,
        }


# Singleton
extractor_pandamall_direct = ExtractorPandamallDirect()
