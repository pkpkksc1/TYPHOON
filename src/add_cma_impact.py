#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard - Step 4.6
Add CMA current wind-radius cross-check to existing JTWC impact output.

Inputs:
    data/jma_typhoon.json
    data/cma_typhoon.json
    data/typhoon_impact.json   # existing v4.3 JTWC result

Output:
    data/typhoon_impact.json   # enriched v4.6 result

Logic:
- Future 5-day logistics risk remains JTWC-based because CMA forecast
  currently contains forecast position/pressure/wind but not forecast
  quadrant wind radii.
- CMA current 30kt directional wind radius is used as an independent
  current cross-check.
- Combined current risk = more severe of:
    JTWC current point risk
    CMA current 30kt risk
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parents[1]

JMA_PATH = BASE_DIR / "data" / "jma_typhoon.json"
CMA_PATH = BASE_DIR / "data" / "cma_typhoon.json"
IMPACT_PATH = BASE_DIR / "data" / "typhoon_impact.json"

PARSER_VERSION = "4.6-CMA"
CMA_CAUTION_MULTIPLIER = 1.5

LOCATION_ORDER = ["SUZHOU", "PVG", "ICN", "HAN", "CRK"]

FALLBACK_LOCATIONS = {
    "SUZHOU": {"name_ko": "쑤저우", "lat": 31.2989, "lon": 120.5853},
    "PVG": {"name_ko": "푸동국제공항", "lat": 31.1443, "lon": 121.8083},
    "ICN": {"name_ko": "인천국제공항", "lat": 37.4602, "lon": 126.4407},
    "HAN": {"name_ko": "하노이 노이바이 국제공항", "lat": 21.2211, "lon": 105.8070},
    "CRK": {"name_ko": "클락국제공항", "lat": 15.1859, "lon": 120.5603},
}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(v: Any) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_compact_utc(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_iso_utc(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def find_jtwc_current_time(impact: Dict[str, Any]) -> Optional[datetime]:
    # Prefer first timeline point because existing v4.3 impact is JTWC-based.
    for code in LOCATION_ORDER:
        item = impact.get("locations", {}).get(code, {})
        timeline = item.get("timeline", [])
        if isinstance(timeline, list) and timeline:
            first = timeline[0]
            if isinstance(first, dict):
                for key in ("time", "time_utc", "valid_time_utc", "forecast_time_utc", "datetime_utc"):
                    dt = parse_iso_utc(first.get(key))
                    if dt:
                        return dt
                    dt = parse_compact_utc(first.get(key))
                    if dt:
                        return dt

    # Fallback to common metadata fields.
    for container_key in ("jtwc", "typhoon", "source_meta"):
        container = impact.get(container_key, {})
        if isinstance(container, dict):
            for key in ("time_utc", "base_time_utc", "analysis_time_utc", "current_time_utc"):
                dt = parse_iso_utc(container.get(key))
                if dt:
                    return dt
                dt = parse_compact_utc(container.get(key))
                if dt:
                    return dt
    return None


def display_cn_time(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    from datetime import timedelta
    cn = dt.astimezone(timezone(timedelta(hours=8)))
    return cn.strftime("%m/%d %H:%M")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)

    y = math.sin(dl) * math.cos(p2)
    x = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dl)
    )

    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def quadrant(b: float) -> str:
    if 0 <= b < 90:
        return "NE"
    if 90 <= b < 180:
        return "SE"
    if 180 <= b < 270:
        return "SW"
    return "NW"


def risk_obj(level: str, label: str, rank: int, basis: str) -> Dict[str, Any]:
    emoji = {
        "GREEN": "🟢",
        "YELLOW": "🟡",
        "RED": "🔴",
        "NO_DATA": "⚪",
    }.get(level, "⚪")

    return {
        "level": level,
        "emoji": emoji,
        "label_ko": label,
        "severity_rank": rank,
        "basis": basis,
    }


def cma_risk(distance: float, radius30: Optional[float]) -> Dict[str, Any]:
    if radius30 is None:
        return risk_obj("NO_DATA", "자료 없음", 0, "CMA 강풍 영향권 자료 없음")

    if radius30 <= 0:
        return risk_obj("GREEN", "낮음", 1, "해당 방향 CMA 강풍 영향권 없음")

    if distance <= radius30:
        return risk_obj("RED", "높음", 3, "CMA 강풍 영향권 내부")

    if distance <= radius30 * CMA_CAUTION_MULTIPLIER:
        return risk_obj(
            "YELLOW",
            "주의",
            2,
            f"CMA 강풍 영향권 반경의 {CMA_CAUTION_MULTIPLIER:.1f}배 이내",
        )

    return risk_obj("GREEN", "낮음", 1, "CMA 강풍 영향권과 충분히 떨어짐")


def matching_cma_storm(cma: Dict[str, Any], impact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    storms = cma.get("typhoons", [])
    if not isinstance(storms, list):
        return None

    meta = impact.get("typhoon", {})
    target_name = str(meta.get("name") or "").upper().strip()
    target_number = str(meta.get("number") or "").strip()

    for s in storms:
        if not isinstance(s, dict):
            continue

        if target_name and str(s.get("name_en") or "").upper().strip() == target_name:
            return s

        if target_number and str(s.get("number") or "").strip() == target_number:
            return s

    return None


def get_location_meta(jma: Dict[str, Any], code: str) -> Dict[str, Any]:
    locations = jma.get("locations", {})
    raw = locations.get(code, {}) if isinstance(locations, dict) else {}
    fallback = FALLBACK_LOCATIONS[code]

    lat = to_float(raw.get("lat"))
    lon = to_float(raw.get("lon"))

    return {
        "name_ko": raw.get("name_ko", fallback["name_ko"]),
        "lat": lat if lat is not None else fallback["lat"],
        "lon": lon if lon is not None else fallback["lon"],
    }


def find_30kt_radius(current: Dict[str, Any], q: str) -> Optional[float]:
    radii = current.get("wind_radii", [])
    if not isinstance(radii, list):
        return None

    key = {
        "NE": "ne_km",
        "SE": "se_km",
        "SW": "sw_km",
        "NW": "nw_km",
    }[q]

    for item in radii:
        if not isinstance(item, dict):
            continue
        if str(item.get("label") or "").upper() == "30KTS":
            return to_float(item.get(key))

    return None


def current_jtwc_risk(location_item: Dict[str, Any]) -> Dict[str, Any]:
    timeline = location_item.get("timeline", [])
    if isinstance(timeline, list) and timeline:
        first = timeline[0]
        if isinstance(first, dict) and isinstance(first.get("risk"), dict):
            return first["risk"]

    return risk_obj("NO_DATA", "자료 없음", 0, "JTWC 현재 위험도 자료 없음")


def choose_more_severe(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    ar = int(a.get("severity_rank", 0) or 0)
    br = int(b.get("severity_rank", 0) or 0)

    if br > ar:
        return b
    return a


def main() -> int:
    print(f"CMA impact cross-check parser: {PARSER_VERSION}")

    jma = load_json(JMA_PATH)
    cma = load_json(CMA_PATH)
    impact = load_json(IMPACT_PATH)

    storm = matching_cma_storm(cma, impact)

    if not storm:
        print("Matching CMA storm not found.")
        impact["cma_crosscheck"] = {
            "status": "NO_MATCH",
            "message_ko": "CMA에서 동일 태풍을 찾지 못함",
        }
    else:
        current = storm.get("current", {})
        storm_lat = to_float(current.get("lat"))
        storm_lon = to_float(current.get("lon"))

        if storm_lat is None or storm_lon is None:
            raise RuntimeError("CMA current lat/lon missing")

        impact["source"] = "JMA + KMA comparison + JTWC + CMA wind radii"
        impact["parser_version"] = PARSER_VERSION
        impact["calculation_mode"] = "JTWC_FORECAST + CMA_CURRENT_CROSSCHECK"

        impact["note_ko"] = (
            "향후 5일 거점 위험도는 JTWC 34/50/64kt 방향별 풍권을 주력으로 사용하고, "
            "CMA 방향별 강풍 영향권은 현재 시점 교차검증에 사용합니다. "
            "CMA 예보에는 현재 구조상 향후 풍권반경이 없어 미래 풍권 계산에는 사용하지 않습니다."
        )

        impact["cma_crosscheck"] = {
            "status": "OK",
            "name_en": storm.get("name_en"),
            "name_cn": storm.get("name_cn"),
            "number": storm.get("number"),
            "time_utc": current.get("time_utc"),
            "grade": current.get("grade"),
            "grade_ko": current.get("grade_ko"),
            "pressure_hpa": current.get("pressure_hpa"),
            "max_wind_mps": current.get("max_wind_mps"),
            "lat": storm_lat,
            "lon": storm_lon,
            "movement_direction": current.get("movement_direction"),
            "movement_direction_ko": current.get("movement_direction_ko"),
            "movement_speed_kmh": current.get("movement_speed_kmh"),
            "wind_radii": current.get("wind_radii", []),
        }

        cma_time = parse_compact_utc(current.get("time_utc"))
        jtwc_time = find_jtwc_current_time(impact)

        diff_hours = None
        if cma_time is not None and jtwc_time is not None:
            diff_hours = round(abs((cma_time - jtwc_time).total_seconds()) / 3600.0, 1)

        impact["agency_time_comparison"] = {
            "jtwc_time_utc": jtwc_time.isoformat() if jtwc_time else None,
            "cma_time_utc": cma_time.isoformat() if cma_time else None,
            "jtwc_time_china": display_cn_time(jtwc_time),
            "cma_time_china": display_cn_time(cma_time),
            "difference_hours": diff_hours,
            "label_ko": (
                f"기관 발표시각 차이 {diff_hours:g}시간"
                if diff_hours is not None
                else "기관 발표시각 차이 확인 불가"
            ),
            "note_ko": "화면에는 중국시간으로 표시하고 내부 계산은 UTC를 유지",
        }

        locations = impact.get("locations", {})

        for code in LOCATION_ORDER:
            if code not in locations:
                continue

            meta = get_location_meta(jma, code)
            dist = haversine_km(
                storm_lat, storm_lon,
                float(meta["lat"]), float(meta["lon"])
            )
            b = bearing_deg(
                storm_lat, storm_lon,
                float(meta["lat"]), float(meta["lon"])
            )
            q = quadrant(b)
            radius30 = find_30kt_radius(current, q)
            clearance = dist - radius30 if radius30 is not None else None
            ratio = (
                dist / radius30
                if radius30 is not None and radius30 > 0
                else None
            )

            crisk = cma_risk(dist, radius30)
            jrisk = current_jtwc_risk(locations[code])
            combined = choose_more_severe(jrisk, crisk)

            jrank = int(jrisk.get("severity_rank", 0) or 0)
            crank = int(crisk.get("severity_rank", 0) or 0)

            if jrank == 1 and crank == 1:
                combined = risk_obj(
                    "GREEN", "낮음", 1,
                    "JTWC · CMA 모두 강풍 영향권 밖"
                )
            elif jrank >= 3 and crank >= 3:
                combined = risk_obj(
                    "RED", "높음", 3,
                    "JTWC · CMA 모두 강풍 영향권 진입"
                )
            elif crank > jrank:
                combined["basis"] = "CMA 판정이 JTWC보다 높아 CMA 기준 적용"
            elif jrank > crank:
                combined["basis"] = "JTWC 판정이 CMA보다 높아 JTWC 기준 적용"
            elif jrank == 2 and crank == 2:
                combined["basis"] = "JTWC · CMA 모두 강풍 영향권 접근"

            if clearance is None:
                boundary = "CMA 강풍 영향권 자료 없음"
            elif radius30 == 0:
                boundary = f"해당 방향 CMA 강풍 영향권 0 km · 중심까지 {round(dist)} km"
            elif clearance < 0:
                boundary = f"CMA 강풍 영향권 내부 {round(abs(clearance))} km"
            else:
                boundary = f"CMA 강풍 영향권까지 {round(clearance)} km"

            locations[code]["current_crosscheck"] = {
                "combined_risk": combined,
                "jtwc_current_risk": jrisk,
                "cma_current_risk": crisk,
                "cma": {
                    "center_distance_km": round(dist),
                    "bearing_deg": round(b),
                    "quadrant": q,
                    "wind_zone_label_ko": "강풍 영향권",
                    "wind_standard_raw": "30KTS",
                    "wind_radius_30_km": (
                        round(radius30) if radius30 is not None else None
                    ),
                    "distance_to_30kt_boundary_km": (
                        round(clearance) if clearance is not None else None
                    ),
                    "distance_to_30kt_radius_ratio": (
                        round(ratio, 2) if ratio is not None else None
                    ),
                    "boundary_status_ko": boundary,
                },
            }

        impact["risk_rule"]["cma_current_high"] = "CMA 해당 방향 강풍 영향권 내부"
        impact["risk_rule"]["cma_current_caution"] = (
            f"CMA 해당 방향 강풍 영향권 반경의 {CMA_CAUTION_MULTIPLIER:.1f}배 이내"
        )
        impact["risk_rule"]["combined_current"] = (
            "현재 위험은 JTWC와 CMA 판정 중 더 높은 단계를 사용하며, 동일 단계면 두 기관의 공통 판정으로 표시"
        )

    impact["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    IMPACT_PATH.write_text(
        json.dumps(impact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {IMPACT_PATH}")

    for code in LOCATION_ORDER:
        item = impact.get("locations", {}).get(code, {})
        cross = item.get("current_crosscheck", {})
        if not cross:
            continue

        combined = cross.get("combined_risk", {})
        cma_detail = cross.get("cma", {})

        print(
            f"{combined.get('emoji', '⚪')} "
            f"{item.get('name_ko', code)}: "
            f"{combined.get('label_ko', '-')} / "
            f"{cma_detail.get('boundary_status_ko', '-')}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
