from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import smtplib

ROOT = Path(__file__).resolve().parents[1]
# Convenience fallback when tested outside repo/src.
if not (ROOT / "data").exists():
    ROOT = Path.cwd()

DASHBOARD_JSON = ROOT / "data" / "dashboard.json"
SIMILARITY_JSON = ROOT / "data" / "typhoon_similarity.json"
OFFLINE_HTML = ROOT / "output" / "typhoon_dashboard_offline.html"

SUBJECT = "[물류] SBLC 태풍 물류대시보드"
PLAIN_BODY = """안녕하세요.

SBLC 태풍 물류대시보드 현황을 메일 본문에 표시했습니다.
전체 화면은 첨부된 오프라인 HTML 파일에서 확인해 주세요.

※ 메일 본문과 첨부파일은 발송 시점의 데이터를 기준으로 생성됩니다.
※ 첨부 HTML은 인터넷 연결 없이 확인할 수 있습니다.
"""


def env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        print(f"ERROR: Missing environment variable: {name}")
        raise SystemExit(2)
    return value


def parse_recipients(raw: str) -> list[str]:
    values = [x.strip() for x in raw.replace(";", ",").split(",")]
    return [x for x in values if x]


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def esc(v, fallback="-") -> str:
    if v is None or v == "":
        return fallback
    return escape(str(v))


def num(v, suffix="", digits=0) -> str:
    if v is None or v == "":
        return "-"
    try:
        n = float(v)
        if digits == 0 and n.is_integer():
            s = f"{int(n):,}"
        else:
            s = f"{n:,.{digits}f}"
        return f"{s}{suffix}"
    except Exception:
        return f"{esc(v)}{escape(suffix)}"


def risk_style(label: str = "", level: str = "") -> tuple[str, str, str]:
    text = (label or "").lower()
    lvl = (level or "").upper()
    if "높" in text or lvl in {"RED", "HIGH"}:
        return "#ff666d", "#3a171d", "#703038"
    if "주의" in text or "중간" in text or lvl in {"YELLOW", "ORANGE", "WARN"}:
        return "#ffd35a", "#332a12", "#66551d"
    if "없음" in text or lvl == "NO_DATA":
        return "#aab7c5", "#1d2732", "#405061"
    return "#55dd91", "#112d23", "#225b42"


def badge(label: str, emoji: str = "", level: str = "") -> str:
    fg, bg, border = risk_style(label, level)
    text = f"{emoji} {label}".strip()
    return (
        f'<span style="display:inline-block;padding:4px 8px;border-radius:999px;'
        f'font-size:11px;font-weight:700;color:{fg};background:{bg};border:1px solid {border};">'
        f'{esc(text)}</span>'
    )


def direction_ko(v) -> str:
    mapping = {
        "北": "북", "北北東": "북북동", "北東": "북동", "東北東": "동북동",
        "東": "동", "東南東": "동남동", "南東": "남동", "南南東": "남남동",
        "南": "남", "南南西": "남남서", "南西": "남서", "西南西": "서남서",
        "西": "서", "西北西": "서북서", "北西": "북서", "北北西": "북북서",
    }
    return mapping.get(str(v), str(v) if v else "-")


def to_china_time(iso_value) -> str:
    if not iso_value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso_value).replace("T", " ")[:16]


def td(content, *, align="left", width=None, muted=False, strong=False) -> str:
    w = f"width:{width};" if width else ""
    color = "#8fa7c0" if muted else "#e9f3ff"
    weight = "font-weight:700;" if strong else ""
    return (
        f'<td style="{w}padding:8px 8px;border-bottom:1px solid #20364f;vertical-align:middle;'
        f'text-align:{align};font-size:11px;line-height:1.45;color:{color};{weight}">{content}</td>'
    )


def section_title(title: str, note: str = "") -> str:
    note_html = (
        f'<span style="font-size:10px;color:#7892ad;font-weight:400;margin-left:8px;">{esc(note)}</span>'
        if note else ""
    )
    return (
        '<tr><td style="padding:18px 0 8px 0;">'
        f'<div style="font-size:15px;font-weight:800;color:#f3f8ff;">{esc(title)}{note_html}</div>'
        '</td></tr>'
    )


def build_html_body(dashboard: dict, similarity: dict) -> str:
    ty = dashboard.get("typhoon") or {}
    cur = ty.get("current") or {}
    comp = dashboard.get("forecast_comparison") or {}
    locations = dashboard.get("locations") or {}
    routes = dashboard.get("routes") or []
    flights = dashboard.get("flights") or []

    generated = to_china_time(dashboard.get("generated_at_utc"))
    typhoon_name = f"{esc(ty.get('number'))} {esc(ty.get('name'))}".strip()
    if not typhoon_name:
        typhoon_name = "현재 태풍"

    # Current typhoon metric cells
    metric_cells = []
    metrics = [
        ("중심기압", num(cur.get("pressure_hpa"), " hPa")),
        ("최대풍속", num(cur.get("max_wind_mps"), " m/s", 1)),
        ("이동방향", esc(direction_ko(cur.get("movement_direction")))),
        ("이동속도", num(cur.get("movement_speed_kmh"), " km/h", 1)),
    ]
    for title, value in metrics:
        metric_cells.append(
            '<td width="25%" style="padding:7px 4px;vertical-align:top;">'
            '<div style="background:#0f2035;border:1px solid #223b57;border-radius:8px;padding:10px 8px;">'
            f'<div style="font-size:10px;color:#7f9ab5;">{esc(title)}</div>'
            f'<div style="margin-top:4px;font-size:14px;font-weight:800;color:#f2f7ff;">{value}</div>'
            '</div></td>'
        )

    # Location rows
    loc_rows = []
    for code in ["SUZHOU", "PVG", "ICN", "MNL", "HAN", "CRK"]:
        item = locations.get(code)
        if not item:
            continue
        risk = item.get("risk") or {}
        fw = item.get("forecast_72h") or {}
        current_d = item.get("current_distance_km")
        closest_d = item.get("closest_distance_km")
        loc_rows.append(
            "<tr>"
            + td(f'<b>{esc(item.get("name_ko", code))}</b><br><span style="color:#6f89a3;font-size:9px;">{esc(code)}</span>', strong=False)
            + td(num(current_d, " km"), align="right")
            + td(num(closest_d, " km"), align="right")
            + td(num(fw.get("max_rain_mm"), " mm", 2), align="right")
            + td(num(fw.get("max_wind_mps"), " m/s", 1), align="right")
            + td(badge(risk.get("label_ko", "-"), risk.get("emoji", "")), align="center")
            + "</tr>"
        )

    # Flight rows
    flight_rows = []
    for f in flights:
        dep = f.get("departure") or {}
        arr = f.get("arrival") or {}
        st = f.get("status") or {}
        route = f.get("route") or "-"
        group = "WF수입" if str(route).strip().startswith("ICN") else "수출"
        dep_text = esc(dep.get("display_time_local"))
        arr_text = esc(arr.get("display_time_local"))
        dep_tz = esc(dep.get("timezone_label_ko"), "")
        arr_tz = esc(arr.get("timezone_label_ko"), "")
        flight_rows.append(
            "<tr>"
            + td(f'<b>{esc(f.get("flight_iata"))}</b><br><span style="color:#6f89a3;font-size:9px;">{esc(group)}</span>')
            + td(esc(route))
            + td(f'{dep_text}<br><span style="color:#6f89a3;font-size:9px;">{dep_tz}</span>')
            + td(f'{arr_text}<br><span style="color:#6f89a3;font-size:9px;">{arr_tz}</span>')
            + td(badge(st.get("label_ko", "-"), st.get("emoji", ""), st.get("level", "")), align="center")
            + "</tr>"
        )

    # Route rows
    route_rows = []
    for r in routes:
        risk = r.get("risk") or {}
        route_rows.append(
            "<tr>"
            + td(f'<b>{esc(r.get("name_ko"))}</b>')
            + td(esc(r.get("reason_ko")), muted=True)
            + td(badge(risk.get("label_ko", "-"), risk.get("emoji", "")), align="center")
            + "</tr>"
        )

    # Similarity block (optional)
    similarity_html = ""
    comps = similarity.get("comparisons") if isinstance(similarity, dict) else None
    if isinstance(comps, list) and comps:
        sim_rows = []
        ordered = sorted(comps, key=lambda x: float(x.get("similarity_pct") or 0), reverse=True)[:2]
        for x in ordered:
            name = x.get("benchmark_name") or x.get("benchmark_id") or "과거 태풍"
            score = x.get("similarity_pct")
            sim_rows.append(
                "<tr>"
                + td(f'<b>{esc(name)}</b>')
                + td(num(score, "%", 1), align="right", strong=True)
                + "</tr>"
            )
        similarity_html = (
            section_title("과거 태풍 유사도", "참고용 · 실제 영향 예측 아님")
            + '<tr><td><table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
              'style="border-collapse:collapse;background:#0b1b2e;border:1px solid #223b57;border-radius:10px;overflow:hidden;">'
            + '<tr>'
              '<td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">비교 태풍</td>'
              '<td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:right;border-bottom:1px solid #20364f;">유사도</td>'
              '</tr>'
            + "".join(sim_rows)
            + '</table></td></tr>'
        )

    comp_label = comp.get("label_ko") or "-"
    comp_avg = comp.get("average_difference_km")
    comp_max = comp.get("max_difference_km")

    html = f'''<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#071321;font-family:Arial,'Noto Sans KR','Malgun Gothic',sans-serif;color:#e9f3ff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#071321;margin:0;padding:0;">
<tr><td align="center" style="padding:18px 8px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:880px;border-collapse:collapse;">
  <tr><td style="padding:18px 18px;background:#0a1a2d;border:1px solid #223b57;border-radius:12px;">
    <div style="font-size:10px;letter-spacing:1.2px;color:#67b9ff;font-weight:700;">SBLC · TYPHOON LOGISTICS CONTROL</div>
    <div style="margin-top:6px;font-size:23px;line-height:1.25;font-weight:900;color:#ffffff;">태풍 물류대시보드</div>
    <div style="margin-top:6px;font-size:11px;color:#829bb4;">발송 데이터 기준 · {esc(generated)} 중국시간</div>
  </td></tr>

  {section_title('현재 태풍')}
  <tr><td style="background:#0b1b2e;border:1px solid #223b57;border-radius:10px;padding:12px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
      <td style="padding:4px;vertical-align:middle;">
        <div style="font-size:17px;font-weight:900;color:#ffffff;">{typhoon_name}</div>
        <div style="margin-top:4px;font-size:10px;color:#7f9ab5;">JMA 예보 비교 · {esc(comp.get('emoji',''))} {esc(comp_label)} · 평균 {num(comp_avg,' km')} / 최대 {num(comp_max,' km')}</div>
      </td>
    </tr></table>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>{''.join(metric_cells)}</tr></table>
  </td></tr>

  {section_title('물류 거점 상태', '현재거리 / 5일 내 최접근 / 72시간 강수·풍속')}
  <tr><td><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#0b1b2e;border:1px solid #223b57;">
    <tr>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">거점</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:right;border-bottom:1px solid #20364f;">현재거리</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:right;border-bottom:1px solid #20364f;">5일 최접근</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:right;border-bottom:1px solid #20364f;">강수</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:right;border-bottom:1px solid #20364f;">풍속</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:center;border-bottom:1px solid #20364f;">위험도</td>
    </tr>{''.join(loc_rows)}
  </table></td></tr>

  {section_title('대표 항공편')}
  <tr><td><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#0b1b2e;border:1px solid #223b57;">
    <tr>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">항공편</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">노선</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">출발</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">도착</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:center;border-bottom:1px solid #20364f;">상태</td>
    </tr>{''.join(flight_rows)}
  </table></td></tr>

  {section_title('주요 노선')}
  <tr><td><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#0b1b2e;border:1px solid #223b57;">
    <tr>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">노선</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;border-bottom:1px solid #20364f;">판단 근거</td>
      <td style="padding:8px;color:#7892ad;font-size:10px;font-weight:700;text-align:center;border-bottom:1px solid #20364f;">위험도</td>
    </tr>{''.join(route_rows)}
  </table></td></tr>

  {similarity_html}

  <tr><td style="padding:18px 0 0 0;">
    <div style="padding:12px 14px;background:#0a1a2d;border:1px solid #223b57;border-radius:10px;font-size:11px;line-height:1.65;color:#9cb0c4;">
      <b style="color:#dbeaff;">전체 대시보드:</b> 메일에 첨부된 HTML 파일을 열어 확인해 주세요.<br>
      첨부파일은 발송 시점의 데이터가 포함된 오프라인 버전이며 인터넷 연결 없이 사용할 수 있습니다.<br>
      ※ 메일 보안정책상 본문에서는 JavaScript 기능과 지도 인터랙션이 제외됩니다.
    </div>
  </td></tr>

  <tr><td style="padding:12px 2px 4px 2px;font-size:9px;color:#5f7892;line-height:1.5;">
    데이터 출처: JMA · KMA · CMA · JTWC · WeatherAPI · Aviationstack<br>
    본 메일은 SBLC 태풍 물류 모니터링용 자동 생성 메일입니다.
  </td></tr>
</table>
</td></tr></table>
</body></html>'''
    return html


def main() -> int:
    email_user = env("EMAIL_USER")
    app_password = env("EMAIL_APP_PASSWORD").replace(" ", "")
    recipients = parse_recipients(env("EMAIL_TO"))

    if not recipients:
        print("ERROR: EMAIL_TO has no valid recipients")
        return 2
    if not DASHBOARD_JSON.exists():
        print(f"ERROR: Dashboard data not found: {DASHBOARD_JSON}")
        return 3
    if not OFFLINE_HTML.exists():
        print(f"ERROR: Offline dashboard not found: {OFFLINE_HTML}")
        print("Run src/build_offline_dashboard.py first.")
        return 4

    dashboard = load_json(DASHBOARD_JSON, {})
    similarity = load_json(SIMILARITY_JSON, {})
    html_body = build_html_body(dashboard, similarity)

    china_now = datetime.now(ZoneInfo("Asia/Shanghai"))
    attachment_name = f"SBLC_태풍_물류대시보드_{china_now:%Y%m%d_%H%M}_CN.html"

    msg = EmailMessage()
    msg["From"] = email_user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = SUBJECT
    msg.set_content(PLAIN_BODY)
    msg.add_alternative(html_body, subtype="html")

    data = OFFLINE_HTML.read_bytes()
    msg.add_attachment(data, maintype="text", subtype="html", filename=attachment_name)

    print("Preparing HTML-body email")
    print(" From:", email_user)
    print(" To:", ", ".join(recipients))
    print(" Subject:", SUBJECT)
    print(" HTML body size:", len(html_body.encode("utf-8")), "bytes")
    print(" Attachment:", attachment_name)
    print(" Attachment size:", len(data), "bytes")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(email_user, app_password)
        smtp.send_message(msg)

    print("EMAIL SENT SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
