#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard - Step 8
Build one dashboard summary JSON

Inputs:
    data/typhoon_compare.json
    data/typhoon_risk.json
    data/flights.json

Output:
    data/dashboard.json

Purpose:
    One simple file for dashboard/email rendering.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]

COMPARE_PATH = BASE_DIR / "data" / "typhoon_compare.json"
RISK_PATH = BASE_DIR / "data" / "typhoon_risk.json"
FLIGHTS_PATH = BASE_DIR / "data" / "flights.json"
OUTPUT_PATH = BASE_DIR / "data" / "dashboard.json"

PARSER_VERSION = "8.0"

LOCATION_ORDER = ["SUZHOU", "PVG", "ICN", "HAN", "CRK"]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def simplify_location(item: Dict[str, Any]) -> Dict[str, Any]:
    weather = item.get("weather", {})
    typhoon = item.get("typhoon", {})
    risk = item.get("risk", {})

    return {
        "name_ko": item.get("name_ko"),
        "score": item.get("score"),
        "risk": {
            "emoji": risk.get("emoji"),
            "label_ko": risk.get("label_ko"),
        },
        "reason_ko": item.get("reason_ko"),
        "closest_distance_km": typhoon.get("closest_distance_km"),
        "closest_time": typhoon.get("closest_time"),
        "trend_ko": typhoon.get("trend_ko"),
        "current_weather": {
            "rain_mm": weather.get("current_rain_mm"),
            "wind_mps": weather.get("current_wind_mps"),
            "gust_mps": weather.get("current_gust_mps"),
        },
        "forecast_72h": {
            "max_rain_mm": weather.get("max_72h_rain_mm"),
            "max_rain_time": weather.get("max_72h_rain_time"),
            "max_wind_mps": weather.get("max_72h_wind_mps"),
            "max_wind_time": weather.get("max_72h_wind_time"),
            "max_gust_mps": weather.get("max_72h_gust_mps"),
            "max_gust_time": weather.get("max_72h_gust_time"),
        },
    }


def simplify_flight(item: Dict[str, Any]) -> Dict[str, Any]:
    dep = item.get("departure", {})
    arr = item.get("arrival", {})
    status = item.get("status", {})

    return {
        "flight_iata": item.get("flight_iata"),
        "route": item.get("route"),
        "status": {
            "emoji": status.get("emoji"),
            "label_ko": status.get("label_ko"),
        },
        "departure": {
            "scheduled_local": dep.get("scheduled_local"),
            "actual_local": dep.get("actual_local"),
            "display_time_local": dep.get("display_time_local"),
            "delay_minutes": dep.get("calculated_delay_minutes"),
            "timezone_label_ko": dep.get("timezone_label_ko"),
        },
        "arrival": {
            "scheduled_local": arr.get("scheduled_local"),
            "actual_local": arr.get("actual_local"),
            "display_time_local": arr.get("display_time_local"),
            "delay_minutes": arr.get("calculated_delay_minutes"),
            "timezone_label_ko": arr.get("timezone_label_ko"),
        },
    }


def main() -> int:
    compare = load_json(COMPARE_PATH)
    risk = load_json(RISK_PATH)
    flights = load_json(FLIGHTS_PATH)

    compare_summary = compare.get("summary", {})
    compare_overall = compare_summary.get("overall", {})

    risk_locations = risk.get("locations", {})
    locations = {}

    for code in LOCATION_ORDER:
        item = risk_locations.get(code)
        if isinstance(item, dict):
            locations[code] = simplify_location(item)

    route_summaries: List[Dict[str, Any]] = []
    for route in risk.get("routes", []):
        if not isinstance(route, dict):
            continue
        r = route.get("risk", {})
        route_summaries.append({
            "code": route.get("code"),
            "name_ko": route.get("name_ko"),
            "score": route.get("score"),
            "risk": {
                "emoji": r.get("emoji"),
                "label_ko": r.get("label_ko"),
            },
            "reason_ko": route.get("reason_ko"),
        })

    flight_summaries = [
        simplify_flight(x)
        for x in flights.get("flights", [])
        if isinstance(x, dict)
    ]

    output = {
        "source": "SBLC Typhoon Dashboard",
        "product": "Dashboard Summary",
        "parser_version": PARSER_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "typhoon": risk.get("typhoon"),
        "forecast_comparison": {
            "emoji": compare_overall.get("emoji", "⚪"),
            "label_ko": compare_overall.get("label_ko", "비교자료 없음"),
            "average_difference_km": compare_summary.get("average_difference_km"),
            "max_difference_km": compare_summary.get("max_difference_km"),
        },
        "locations": locations,
        "routes": route_summaries,
        "flights": flight_summaries,
        "attribution": [
            "Japan Meteorological Agency (JMA)",
            "Korea Meteorological Administration (KMA)",
            "Powered by WeatherAPI.com",
            "Aviationstack",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Dashboard summary version: {PARSER_VERSION}")
    print(f"Updated: {OUTPUT_PATH}")
    print(f"Locations: {len(locations)}")
    print(f"Routes: {len(route_summaries)}")
    print(f"Flights: {len(flight_summaries)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
