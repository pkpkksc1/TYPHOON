#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard - Step 7.1
Manual flight status fetch: ICN -> PVG

Flights:
    KE315
    KE249

Changes in v7.1:
- Compute departure/arrival delay directly from scheduled vs actual/estimated time
- Display ICN times in Korea time (UTC+9)
- Display PVG times in China time (UTC+8)
- Prefer actual time, then estimated time
- Clear simple status labels

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "data" / "flights.json"

API_URL = "https://api.aviationstack.com/v1/flights"
PARSER_VERSION = "7.1"
FLIGHTS = ["KE315", "KE249"]

KST = timezone(timedelta(hours=9))
CST = timezone(timedelta(hours=8))


def parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def to_local_iso(value: Any, tz: timezone) -> Optional[str]:
    dt = parse_iso(value)
    if not dt:
        return None
    return dt.astimezone(tz).isoformat()


def to_local_short(value: Any, tz: timezone) -> Optional[str]:
    dt = parse_iso(value)
    if not dt:
        return None
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def diff_minutes(start_value: Any, end_value: Any) -> Optional[int]:
    start = parse_iso(start_value)
    end = parse_iso(end_value)

    if not start or not end:
        return None

    return round((end - start).total_seconds() / 60)


def pick_operational_time(
    actual: Any,
    estimated: Any,
    scheduled: Any,
) -> Any:
    if actual:
        return actual
    if estimated:
        return estimated
    return scheduled


def make_status(
    flight_status: str,
    departure: Dict[str, Any],
    arrival: Dict[str, Any],
) -> Dict[str, Any]:
    raw_status = (flight_status or "").lower()

    if raw_status == "cancelled":
        return {
            "level": "RED",
            "emoji": "🔴",
            "label_ko": "결항",
        }

    if raw_status in ("incident", "diverted"):
        return {
            "level": "RED",
            "emoji": "🔴",
            "label_ko": "운항 문제",
        }

    dep_delay = departure.get("calculated_delay_minutes")
    arr_delay = arrival.get("calculated_delay_minutes")

    # If actual departure exists, departure delay is the clearest current status.
    if departure.get("actual"):
        if isinstance(dep_delay, int) and dep_delay >= 10:
            return {
                "level": "YELLOW",
                "emoji": "🟡",
                "label_ko": f"출발 {dep_delay}분 지연",
            }

        # Landed flight: use arrival delay if available.
        if arrival.get("actual"):
            if isinstance(arr_delay, int) and arr_delay >= 10:
                return {
                    "level": "YELLOW",
                    "emoji": "🟡",
                    "label_ko": f"도착 {arr_delay}분 지연",
                }
            return {
                "level": "GREEN",
                "emoji": "🟢",
                "label_ko": "도착 완료",
            }

        return {
            "level": "GREEN",
            "emoji": "🟢",
            "label_ko": "출발 완료",
        }

    # No actual departure yet: estimated delay can still indicate expected delay.
    if isinstance(dep_delay, int) and dep_delay >= 10:
        return {
            "level": "YELLOW",
            "emoji": "🟡",
            "label_ko": f"출발 예정 {dep_delay}분 지연",
        }

    if raw_status == "active":
        return {
            "level": "GREEN",
            "emoji": "🟢",
            "label_ko": "운항 중",
        }

    return {
        "level": "GREEN",
        "emoji": "🟢",
        "label_ko": "출발 예정",
    }


def normalize_departure(raw: Dict[str, Any]) -> Dict[str, Any]:
    scheduled = raw.get("scheduled")
    estimated = raw.get("estimated")
    actual = raw.get("actual")

    operational = pick_operational_time(
        actual,
        estimated,
        scheduled,
    )

    delay_base = actual or estimated
    calc_delay = diff_minutes(
        scheduled,
        delay_base,
    ) if delay_base else None

    return {
        "airport": raw.get("airport"),
        "iata": raw.get("iata"),
        "timezone": "Asia/Seoul",
        "timezone_label_ko": "한국시간",
        "scheduled_utc": scheduled,
        "estimated_utc": estimated,
        "actual_utc": actual,
        "scheduled_local": to_local_iso(scheduled, KST),
        "estimated_local": to_local_iso(estimated, KST),
        "actual_local": to_local_iso(actual, KST),
        "display_time_local": to_local_short(operational, KST),
        "calculated_delay_minutes": calc_delay,
        "api_delay_minutes": raw.get("delay"),
        "terminal": raw.get("terminal"),
        "gate": raw.get("gate"),
    }


def normalize_arrival(raw: Dict[str, Any]) -> Dict[str, Any]:
    scheduled = raw.get("scheduled")
    estimated = raw.get("estimated")
    actual = raw.get("actual")

    operational = pick_operational_time(
        actual,
        estimated,
        scheduled,
    )

    delay_base = actual or estimated
    calc_delay = diff_minutes(
        scheduled,
        delay_base,
    ) if delay_base else None

    return {
        "airport": raw.get("airport"),
        "iata": raw.get("iata"),
        "timezone": "Asia/Shanghai",
        "timezone_label_ko": "중국시간",
        "scheduled_utc": scheduled,
        "estimated_utc": estimated,
        "actual_utc": actual,
        "scheduled_local": to_local_iso(scheduled, CST),
        "estimated_local": to_local_iso(estimated, CST),
        "actual_local": to_local_iso(actual, CST),
        "display_time_local": to_local_short(operational, CST),
        "calculated_delay_minutes": calc_delay,
        "api_delay_minutes": raw.get("delay"),
        "terminal": raw.get("terminal"),
        "gate": raw.get("gate"),
    }


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
        headers={
            "User-Agent": "sblc-typhoon-dashboard/7.1",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(
            response.read().decode("utf-8")
        )

    if payload.get("error"):
        raise RuntimeError(
            f"Aviationstack error for {flight_iata}: "
            f"{payload['error']}"
        )

    rows = payload.get("data", [])

    if not rows:
        return {
            "flight_iata": flight_iata,
            "route": "ICN → PVG",
            "found": False,
            "status": {
                "level": "NO_DATA",
                "emoji": "⚪",
                "label_ko": "조회 결과 없음",
            },
        }

    row = rows[0]

    for candidate in rows:
        dep_iata = candidate.get(
            "departure", {}
        ).get("iata")

        arr_iata = candidate.get(
            "arrival", {}
        ).get("iata")

        if dep_iata == "ICN" and arr_iata == "PVG":
            row = candidate
            break

    raw_departure = row.get("departure", {})
    raw_arrival = row.get("arrival", {})

    departure = normalize_departure(
        raw_departure
    )

    arrival = normalize_arrival(
        raw_arrival
    )

    status = make_status(
        row.get("flight_status"),
        departure,
        arrival,
    )

    flight = row.get("flight", {})

    return {
        "flight_iata": (
            flight.get("iata")
            or flight_iata
        ),
        "flight_number": flight.get("number"),
        "route": "ICN → PVG",
        "found": True,
        "status_raw": row.get("flight_status"),
        "status": status,
        "departure": departure,
        "arrival": arrival,
        "airline": row.get(
            "airline", {}
        ).get("name"),
        "flight_date": row.get("flight_date"),
    }


def main() -> int:
    print(f"Flight fetch version: {PARSER_VERSION}")

    api_key = os.environ.get(
        "AVIATIONSTACK_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "AVIATIONSTACK_API_KEY secret is missing."
        )

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for flight in FLIGHTS:
        print(
            f"Fetching {flight} ICN -> PVG"
        )

        try:
            results.append(
                load_flight(
                    api_key,
                    flight,
                )
            )
        except Exception as exc:
            errors.append({
                "flight_iata": flight,
                "error": str(exc),
            })

            print(
                f"ERROR {flight}: {exc}"
            )

    output = {
        "source": "Aviationstack",
        "product": "Manual Flight Status",
        "parser_version": PARSER_VERSION,
        "route": "ICN → PVG",
        "tracked_flights": FLIGHTS,
        "time_display": {
            "departure": "한국시간",
            "arrival": "중국시간",
        },
        "flights": results,
        "errors": errors,
        "generated_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {OUTPUT_PATH}")
    print(
        f"Flights returned: {len(results)}"
    )
    print(
        f"Errors: {len(errors)}"
    )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
