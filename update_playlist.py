import re
import requests

# URL หน้าเว็บ Bunkr ต้นทาง
WEB_PAGE_URL = "https://bunkr.ws/f/WrWkgiCtY4dTc"

# ชื่อไฟล์ M3U หลักใน GitHub ของคุณ
M3U_FILENAME = "IPTV-Marco.m3u"


def fetch_latest_video_url():
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  try:
    response = requests.get(WEB_PAGE_URL, headers=headers, timeout=15)

    # ค้นหาลิงก์ CDN ที่มี .mp4 พร้อม token และ ex ล่าสุดจากหน้าเว็บ
    match = re.search(
        r'https://[^\s<"]+?\.cdn\.cr/storage/media/[^\s<"]+?\.mp4\?token=[^\s<"]+?&ex=\d+',
        response.text,
    )

    if match:
      return match.group(0)

    # วิธีสำรอง: ค้นหาจากลิงก์ปุ่มดาวน์โหลดในหน้าเว็บ
    fallback_match = re.search(
        r'href=["\'](https://[^\s"\']+?\.mp4\?[^\s"\']+?)["\']', response.text
    )
    if fallback_match:
      return fallback_match.group(1)

    print("ไม่สามารถหาลิงก์วิดีโอใหม่จากหน้าเว็บได้")
    return None

  except Exception as e:
    print(f"เกิดข้อผิดพลาด: {e}")
    return None


def update_m3u():
  new_url = fetch_latest_video_url()

  if not new_url:
    print("ข้ามการอัปเดตเนื่องจากไม่พบลิงก์ใหม่")
    return

  print(f"พบลิงก์สดใหม่: {new_url}")

  # เขียนโครงสร้างไฟล์ M3U ลงใน IPTV-Marco.m3u โดยใช้โลโก้เดิมที่มีอยู่แล้ว
  m3u_content = f"""#EXTM3U
#EXTINF:-1 group-title="คลิป" tvg-logo="https://static.scdn.st/027e12ae-683b-4e42-950f-2b3f12448931/thumbs/cc0433e0-c396-4305-8c92-1f792ef9803f.png",cy-102
{new_url}
"""

  with open(M3U_FILENAME, "w", encoding="utf-8") as f:
    f.write(m3u_content)

  print(f"อัปเดตไฟล์ {M3U_FILENAME} สำเร็จเรียบร้อยแล้ว!")


if __name__ == "__main__":
  update_m3u()
