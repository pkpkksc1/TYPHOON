#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard - Step 7
Manual flight status fetch: ICN -> PVG

Flights:
    KE315
    KE249

Required GitHub Secret:
    AVIATIONSTACK_API_KEY

Output:
    data/flights.json
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "data" / "flights.json"

API_URL = "https://api.aviationstack.com/v1/flights"
PARSER_VERSION = "7.0"
FLIGHTS = ["KE315", "KE249"]


def load_flight(api_key: str, flight_iata: str) -> Dict[str, Any]:
    params = urllib.parse.urlencode({
        "access_key": api_key,
        "flight_iata": flight_iata,
        "dep_iata": "ICN",
        "arr_iata": "PVG",
        "limit": 10,
    })

    url = f"{API_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sblc-typhoon-dashboard/7.0"},
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("error"):
        raise RuntimeError(
            f"Aviationstack error for {flight_iata}: {payload['error']}"
        )

    rows = payload.get("data", [])
    if not rows:
        return {
            "flight_iata": flight_iata,
            "route": "ICN → PVG",
            "found": False,
            "status_ko": "조회 결과 없음",
        }

    # API may return multiple records. Prefer the first ICN->PVG record.
    row = rows[0]
    for candidate in rows:
        dep = candidate.get("departure", {}).get("iata")
        arr = candidate.get("arrival", {}).get("iata")
        if dep == "ICN" and arr == "PVG":
            row = candidate
            break

    departure = row.get("departure", {})
    arrival = row.get("arrival", {})
    flight = row.get("flight", {})

    status = (row.get("flight_status") or "").lower()
    status_map = {
        "scheduled": ("🟢", "예정"),
        "active": ("🟢", "운항 중"),
        "landed": ("🟢", "도착"),
        "cancelled": ("🔴", "결항"),
        "incident": ("🔴", "운항 문제"),
        "diverted": ("🔴", "회항"),
    }
    emoji, status_ko = status_map.get(status, ("⚪", status or "상태 미확인"))

    delay = departure.get("delay")
    if isinstance(delay, (int, float)) and delay > 0 and status != "cancelled":
        emoji = "🟡"
        status_ko = f"지연 {round(delay)}분"

    return {
        "flight_iata": flight.get("iata") or flight_iata,
        "flight_number": flight.get("number"),
        "route": "ICN → PVG",
        "found": True,
        "status_raw": row.get("flight_status"),
        "status": {
            "emoji": emoji,
            "label_ko": status_ko,
        },
        "departure": {
            "airport": departure.get("airport"),
            "iata": departure.get("iata"),
            "scheduled": departure.get("scheduled"),
            "estimated": departure.get("estimated"),
            "actual": departure.get("actual"),
            "delay_minutes": departure.get("delay"),
            "terminal": departure.get("terminal"),
            "gate": departure.get("gate"),
        },
        "arrival": {
            "airport": arrival.get("airport"),
            "iata": arrival.get("iata"),
            "scheduled": arrival.get("scheduled"),
            "estimated": arrival.get("estimated"),
            "actual": arrival.get("actual"),
            "delay_minutes": arrival.get("delay"),
            "terminal": arrival.get("terminal"),
            "gate": arrival.get("gate"),
        },
        "airline": row.get("airline", {}).get("name"),
        "flight_date": row.get("flight_date"),
    }


def main() -> int:
    print(f"Flight fetch version: {PARSER_VERSION}")

    api_key = os.environ.get("AVIATIONSTACK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("AVIATIONSTACK_API_KEY secret is missing.")

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for flight in FLIGHTS:
        print(f"Fetching {flight} ICN -> PVG")
        try:
            results.append(load_flight(api_key, flight))
        except Exception as exc:
            errors.append({
                "flight_iata": flight,
                "error": str(exc),
            })
            print(f"ERROR {flight}: {exc}")

    output = {
        "source": "Aviationstack",
        "product": "Manual Flight Status",
        "parser_version": PARSER_VERSION,
        "route": "ICN → PVG",
        "tracked_flights": FLIGHTS,
        "flights": results,
        "errors": errors,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {OUTPUT_PATH}")
    print(f"Flights returned: {len(results)}")
    print(f"Errors: {len(errors)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
