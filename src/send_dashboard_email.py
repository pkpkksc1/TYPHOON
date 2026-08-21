from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo
import mimetypes
import os
import smtplib
import sys

ROOT = Path(__file__).resolve().parents[1]
OFFLINE_HTML = ROOT / "output" / "typhoon_dashboard_offline.html"

SUBJECT = "[물류] SBLC 태풍 물류대시보드"
BODY = """안녕하세요.

SBLC 태풍 물류대시보드를 첨부드립니다.
첨부된 HTML 파일을 다운로드한 뒤 실행하여 확인해 주세요.

※ 첨부파일은 메일 발송 시점의 데이터를 기준으로 생성된 오프라인 대시보드입니다.
※ 인터넷 연결 없이 확인할 수 있습니다.
"""


def env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        print(f"ERROR: Missing environment variable: {name}")
        raise SystemExit(2)
    return value


def parse_recipients(raw: str) -> list[str]:
    # EMAIL_TO supports comma/semicolon separated addresses.
    values = [x.strip() for x in raw.replace(";", ",").split(",")]
    return [x for x in values if x]


def main() -> int:
    email_user = env("EMAIL_USER")
    # Google app passwords are often displayed with spaces; tolerate either form.
    app_password = env("EMAIL_APP_PASSWORD").replace(" ", "")
    recipients = parse_recipients(env("EMAIL_TO"))

    if not recipients:
        print("ERROR: EMAIL_TO has no valid recipients")
        return 2

    if not OFFLINE_HTML.exists():
        print(f"ERROR: Offline dashboard not found: {OFFLINE_HTML}")
        print("Run src/build_offline_dashboard.py first.")
        return 3

    china_now = datetime.now(ZoneInfo("Asia/Shanghai"))
    attachment_name = f"SBLC_태풍_물류대시보드_{china_now:%Y%m%d_%H%M}_CN.html"

    msg = EmailMessage()
    msg["From"] = email_user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = SUBJECT
    msg.set_content(BODY)

    data = OFFLINE_HTML.read_bytes()
    msg.add_attachment(
        data,
        maintype="text",
        subtype="html",
        filename=attachment_name,
    )

    print("Preparing email")
    print(" From:", email_user)
    print(" To:", ", ".join(recipients))
    print(" Subject:", SUBJECT)
    print(" Attachment:", attachment_name)
    print(" Attachment size:", len(data), "bytes")

    # Gmail SMTP over SSL.
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(email_user, app_password)
        smtp.send_message(msg)

    print("EMAIL SENT SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
