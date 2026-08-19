#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard - Step 4
Logistics hub / route impact from JMA forecast distances

Input:
    data/jma_typhoon.json
    data/typhoon_compare.json

Output:
    data/typhoon_impact.json

Simple distance-only risk:
    <= 300 km   : RED    / 높음
    <= 700 km   : YELLOW / 주의
    > 700 km    : GREEN  / 낮음

IMPORTANT:
This is NOT a flight-delay forecast.
Rain / local wind / airport operations will be added in later steps.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]

JMA_PATH = BASE_DIR / "data" / "jma_typhoon.json"
COMPARE_PATH = BASE_DIR / "data" / "typhoon_compare.json"
OUTPUT_PATH = BASE_DIR / "data" / "typhoon_impact.json"

PARSER_VERSION = "4.0"

RED_MAX_KM = 300
YELLOW_MAX_KM = 700

LOCATION_ORDER = ["SUZHOU", "PVG", "ICN", "HAN", "CRK"]

ROUTES = [
    {
        "code": "SUZHOU_PVG_ICN",
        "name_ko": "쑤저우 → PVG → 한국",
        "locations": ["SUZHOU", "PVG", "ICN"],
    },
    {
        "code": "SUZHOU_PVG_HAN",
        "name_ko": "쑤저우 → PVG → 하노이",
        "locations": ["SUZHOU", "PVG", "HAN"],
    },
    {
        "code": "SUZHOU_PVG_CRK",
        "name_ko": "쑤저우 → PVG → 클락",
        "locations": ["SUZHOU", "PVG", "CRK"],
    },
    {
        "code": "ICN_PVG",
        "name_ko": "한국 → PVG",
        "locations": ["ICN", "PVG"],
    },
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def risk_from_distance(distance_km: Optional[float]) -> Dict[str, str]:
    if distance_km is None:
        return {
            "level": "NO_DATA",
            "emoji": "⚪",
            "label_ko": "자료 없음",
        }

    if distance_km <= RED_MAX_KM:
        return {
            "level": "RED",
            "emoji": "🔴",
            "label_ko": "높음",
        }

    if distance_km <= YELLOW_MAX_KM:
        return {
            "level": "YELLOW",
            "emoji": "🟡",
            "label_ko": "주의",
        }

    return {
        "level": "GREEN",
        "emoji": "🟢",
        "label_ko": "낮음",
    }


def risk_rank(level: str) -> int:
    return {
        "NO_DATA": 0,
        "GREEN": 1,
        "YELLOW": 2,
        "RED": 3,
    }.get(level, 0)


def get_primary_typhoon(jma: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    typhoons = jma.get("typhoons", [])
    if not isinstance(typhoons, list) or not typhoons:
        return None
    return typhoons[0]


def build_timeline(typhoon: Dict[str, Any]) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []

    analysis = typhoon.get("analysis")
    if isinstance(analysis, dict):
        timeline.append({
            "forecast_hour": 0,
            "time": analysis.get("time"),
            "distances_km": analysis.get("distances_km", {}),
        })

    forecasts = typhoon.get("forecast", [])
    if isinstance(forecasts, list):
        for item in forecasts:
            if not isinstance(item, dict):
                continue
            timeline.append({
                "forecast_hour": item.get("forecast_hour"),
                "time": item.get("time"),
                "distances_km": item.get("distances_km", {}),
            })

    timeline.sort(
        key=lambda x: (
            x.get("forecast_hour") is None,
            x.get("forecast_hour") or 0,
        )
    )

    return timeline


def location_summary(
    code: str,
    timeline: List[Dict[str, Any]],
    location_meta: Dict[str, Any],
) -> Dict[str, Any]:
    points = []

    for point in timeline:
        distances = point.get("distances_km", {})
        if not isinstance(distances, dict):
            continue

        value = distances.get(code)
        if not isinstance(value, (int, float)):
            continue

        points.append({
            "forecast_hour": point.get("forecast_hour"),
            "time": point.get("time"),
            "distance_km": round(value),
        })

    if not points:
        return {
            "code": code,
            "name_ko": location_meta.get("name_ko", code),
            "current_distance_km": None,
            "closest_distance_km": None,
            "closest_time": None,
            "closest_forecast_hour": None,
            "trend": "UNKNOWN",
            "trend_ko": "자료 없음",
            "risk": risk_from_distance(None),
            "timeline": [],
        }

    current = points[0]["distance_km"]
    closest = min(points, key=lambda x: x["distance_km"])
    last = points[-1]["distance_km"]

    if last < current:
        trend = "APPROACHING"
        trend_ko = "접근 중"
        trend_emoji = "↘"
    elif last > current:
        trend = "MOVING_AWAY"
        trend_ko = "멀어지는 중"
        trend_emoji = "↗"
    else:
        trend = "STABLE"
        trend_ko = "큰 변화 없음"
        trend_emoji = "→"

    return {
        "code": code,
        "name_ko": location_meta.get("name_ko", code),
        "current_distance_km": current,
        "closest_distance_km": closest["distance_km"],
        "closest_time": closest["time"],
        "closest_forecast_hour": closest["forecast_hour"],
        "trend": trend,
        "trend_ko": trend_ko,
        "trend_emoji": trend_emoji,
        "risk": risk_from_distance(closest["distance_km"]),
        "timeline": points,
    }


def route_summary(
    route: Dict[str, Any],
    locations: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    route_locations = [
        locations[code]
        for code in route["locations"]
        if code in locations
    ]

    if not route_locations:
        return {
            "code": route["code"],
            "name_ko": route["name_ko"],
            "risk": risk_from_distance(None),
            "reason_ko": "자료 없음",
        }

    worst = max(
        route_locations,
        key=lambda x: risk_rank(x["risk"]["level"]),
    )

    return {
        "code": route["code"],
        "name_ko": route["name_ko"],
        "risk": worst["risk"],
        "reason_ko": (
            f"{worst['name_ko']} 최접근 "
            f"{worst['closest_distance_km']} km"
        ),
        "locations": route["locations"],
    }


def semantic_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    clone = json.loads(json.dumps(data, ensure_ascii=False))
    clone.pop("generated_at_utc", None)
    return clone


def write_if_changed(data: Dict[str, Any]) -> bool:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        try:
            old = load_json(OUTPUT_PATH)
            if semantic_payload(old) == semantic_payload(data):
                print("No impact data change.")
                return False
        except Exception:
            pass

    data["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {OUTPUT_PATH}")
    return True


def main() -> int:
    print(f"Typhoon impact parser: {PARSER_VERSION}")

    jma = load_json(JMA_PATH)

    compare = {}
    if COMPARE_PATH.exists():
        try:
            compare = load_json(COMPARE_PATH)
        except Exception:
            compare = {}

    typhoon = get_primary_typhoon(jma)

    if not typhoon:
        output = {
            "source": "JMA + JMA/KMA comparison",
            "product": "Logistics Typhoon Impact",
            "parser_version": PARSER_VERSION,
            "status": "NO_TYPHOON",
            "message_ko": "활동 중인 태풍 정보 없음",
            "locations": {},
            "routes": [],
        }
        write_if_changed(output)
        return 0

    timeline = build_timeline(typhoon)
    location_meta = jma.get("locations", {})

    locations: Dict[str, Dict[str, Any]] = {}

    for code in LOCATION_ORDER:
        meta = location_meta.get(code, {})
        locations[code] = location_summary(
            code,
            timeline,
            meta,
        )

    routes = [
        route_summary(route, locations)
        for route in ROUTES
    ]

    typhoon_meta = typhoon.get("typhoon", {})

    compare_summary = compare.get("summary", {})
    compare_overall = compare_summary.get("overall", {})

    output = {
        "source": "JMA + JMA/KMA comparison",
        "product": "Logistics Typhoon Impact",
        "parser_version": PARSER_VERSION,
        "status": "OK",
        "note_ko": "현재 위험도는 태풍과의 거리 기준입니다. 강수·공항풍속·항공편 운항정보는 이후 단계에서 추가됩니다.",
        "typhoon": {
            "number": typhoon_meta.get("number"),
            "name": typhoon_meta.get("name"),
        },
        "forecast_confidence": {
            "emoji": compare_overall.get("emoji", "⚪"),
            "label_ko": compare_overall.get("label_ko", "비교자료 없음"),
            "average_difference_km": compare_summary.get(
                "average_difference_km"
            ),
        },
        "risk_rule": {
            "red": f"0~{RED_MAX_KM} km",
            "yellow": f"{RED_MAX_KM + 1}~{YELLOW_MAX_KM} km",
            "green": f"{YELLOW_MAX_KM + 1} km 이상",
        },
        "locations": locations,
        "routes": routes,
    }

    write_if_changed(output)

    print("")
    print("=== LOCATION IMPACT ===")
    for code in LOCATION_ORDER:
        item = locations[code]
        print(
            f"{item['risk']['emoji']} "
            f"{item['name_ko']}: "
            f"closest {item['closest_distance_km']} km / "
            f"{item['trend_ko']}"
        )

    print("")
    print("=== ROUTE IMPACT ===")
    for route in routes:
        print(
            f"{route['risk']['emoji']} "
            f"{route['name_ko']} - "
            f"{route['risk']['label_ko']} "
            f"({route['reason_ko']})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
