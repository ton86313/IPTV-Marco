
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
M3U_FILE = ROOT / "IPTV-Marco.m3u"
SOURCES_FILE = ROOT / "bunkr_sources.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/130 Safari/537.36"
}


def get_text(url, timeout=30):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_js_value(html, name):
    pattern = (
        r'\b(?:var|let|const)\s+'
        + re.escape(name)
        + r'\s*=\s*(["\'])(.*?)\1'
    )
    match = re.search(pattern, html, re.S)

    if not match:
        raise ValueError(f"ไม่พบ {name} ในหน้า Bunkr")

    return (
        match.group(2)
        .replace(r"\/", "/")
        .replace(r"\"", '"')
        .replace("&amp;", "&")
    )


def allowed_sign_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    return (
        parsed.scheme == "https"
        and (
            host == "cdn.cr"
            or host.endswith(".cdn.cr")
        )
    )


def find_token_and_expiry(data):
    """ค้นหา token และ ex ใน JSON ที่ signing endpoint ส่งกลับ"""
    if isinstance(data, dict):
        token = data.get("token")
        expiry = data.get("ex")

        if expiry is None:
            expiry = data.get("expires")

        if token and expiry is not None:
            return str(token), str(expiry)

        for value in data.values():
            result = find_token_and_expiry(value)
            if result:
                return result

    elif isinstance(data, list):
        for value in data:
            result = find_token_and_expiry(value)
            if result:
                return result

    return None


def resolve_bunkr(page_url):
    print(f"กำลังอ่านหน้า Bunkr: {page_url}")

    html = get_text(page_url)

    cdn_url = extract_js_value(html, "jsCDN")
    sign_url = extract_js_value(html, "signUrl")

    if not allowed_sign_url(sign_url):
        raise ValueError("Signing host ไม่อยู่ใน allowlist ที่อนุญาต")

    cdn = urlparse(cdn_url)
    if cdn.scheme != "https" or not cdn.hostname:
        raise ValueError("CDN URL ไม่ถูกต้อง")

    # ส่งเฉพาะ path ของไฟล์ให้ signing endpoint
    params = urlencode({"path": cdn.path})
    separator = "&" if "?" in sign_url else "?"
    signing_request = sign_url + separator + params

    req = Request(signing_request, headers=HEADERS)

    with urlopen(req, timeout=30) as response:
        payload = json.loads(
            response.read().decode("utf-8")
        )

    result = find_token_and_expiry(payload)

    if not result:
        # ไม่พิมพ์ token หรือข้อมูลลับออก log
        keys = list(payload.keys()) if isinstance(payload, dict) else []
        raise ValueError(
            f"ไม่พบ token/ex ในผลตอบกลับ; JSON keys={keys}"
        )

    token, expiry = result

    # ประกอบ URL ใหม่จาก CDN path และ token ที่ได้จากต้นทาง
    return cdn_url.split("?")[0] + "?" + urlencode({
        "token": token,
        "ex": expiry
    })


def main():
    if not M3U_FILE.exists():
        raise FileNotFoundError("ไม่พบ IPTV-Marco.m3u")

    with SOURCES_FILE.open(encoding="utf-8") as f:
        sources = json.load(f)

    original = M3U_FILE.read_text(encoding="utf-8-sig")
    lines = original.splitlines()
    updated = 0
    changed = False

    # ดึง URL ใหม่ให้ครบก่อนแก้ไฟล์
    fresh_urls = {
        title: resolve_bunkr(page_url)
        for title, page_url in sources.items()
    }

    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue

        # ชื่อรายการอยู่หลัง comma ตัวสุดท้ายใน EXTINF
        title = line.rsplit(",", 1)[-1].strip()

        if title not in fresh_urls or i + 1 >= len(lines):
            continue

        old_url = lines[i + 1].strip()

        if not old_url.startswith("https://"):
            continue

        new_url = fresh_urls[title]

        if old_url != new_url:
            lines[i + 1] = new_url
            updated += 1
            changed = True
            print(f"เตรียมอัปเดต: {title}")

    if changed:
        temp_file = M3U_FILE.with_suffix(".m3u.tmp")
        temp_file.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8"
        )
        os.replace(temp_file, M3U_FILE)
        print(f"อัปเดต URL สำเร็จ {updated} รายการ")
    else:
        print("ไม่มี URL ที่ต้องเปลี่ยน")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, HTTPError, URLError,
            TimeoutError, json.JSONDecodeError) as exc:
        print(f"อัปเดตไม่สำเร็จ: {exc}", file=sys.stderr)
        sys.exit(1)
