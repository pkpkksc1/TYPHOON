#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SBLC Typhoon Dashboard
Flight Status Fetch v7.3

Target:
    KE315
    ICN -> PVG

Changes:
1. KE249 완전 제거
2. KE315만 조회
3. Aviationstack 시간의 시/분 값을 공항 현지시간으로 사용
4. ICN 출발 = 한국시간
5. PVG 도착 = 중국시간
6. 예정/실제 차이로 지연시간 직접 계산

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
from typing import Any, Dict, List, Optional


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "flights.json"
)

API_URL = (
    "https://api.aviationstack.com/v1/flights"
)

PARSER_VERSION = "7.3"


# =========================================================
# 조회 항공편
# KE249 제거
# =========================================================

FLIGHTS = [
    "KE315",
]


# =========================================================
# ISO 시간 파싱
#
# 중요:
# Aviationstack KE315 응답에서는
#
# 23:10:00+00:00
#
# 형태로 들어오지만,
# KE315 실제 스케줄 확인 결과
# 23:10은 ICN 현지시간이다.
#
# 따라서 UTC +9 변환하지 않고
# 날짜/시/분 자체를 현지시간으로 사용한다.
# =========================================================

def parse_local_clock(
    value: Any
) -> Optional[datetime]:

    if not value:
        return None

    text = str(value).strip()

    try:

        # timezone 부분 제거
        # 예:
        # 2026-08-19T23:10:00+00:00
        # →
        # 2026-08-19T23:10:00

        if "T" in text:

            date_part = text[:19]

            return datetime.strptime(
                date_part,
                "%Y-%m-%dT%H:%M:%S"
            )

    except ValueError:
        return None

    return None


# =========================================================
# 현지시간 ISO 표시
# =========================================================

def local_iso(
    value: Any,
    offset_text: str
) -> Optional[str]:

    dt = parse_local_clock(value)

    if not dt:
        return None

    return (
        dt.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        + offset_text
    )


# =========================================================
# 대시보드 표시용
# =========================================================

def local_short(
    value: Any
) -> Optional[str]:

    dt = parse_local_clock(value)

    if not dt:
        return None

    return dt.strftime(
        "%Y-%m-%d %H:%M"
    )


# =========================================================
# 지연시간 계산
# =========================================================

def diff_minutes(
    scheduled: Any,
    actual_or_estimated: Any
) -> Optional[int]:

    start = parse_local_clock(
        scheduled
    )

    end = parse_local_clock(
        actual_or_estimated
    )

    if not start or not end:
        return None


    # 자정을 넘어간 경우 보정
    #
    # 예:
    # 예정 23:50
    # 실제 00:20

    if end < start:

        from datetime import timedelta

        end = end + timedelta(
            days=1
        )


    minutes = (
        end - start
    ).total_seconds() / 60


    return round(
        minutes
    )


# =========================================================
# 실제 → 예상 → 예정 순서
# =========================================================

def select_display_time(
    actual: Any,
    estimated: Any,
    scheduled: Any
) -> Any:

    if actual:
        return actual

    if estimated:
        return estimated

    return scheduled


# =========================================================
# 출발 데이터
# ICN = 한국시간
# =========================================================

def normalize_departure(
    raw: Dict[str, Any]
) -> Dict[str, Any]:

    scheduled = raw.get(
        "scheduled"
    )

    estimated = raw.get(
        "estimated"
    )

    actual = raw.get(
        "actual"
    )


    operational_time = (
        select_display_time(
            actual,
            estimated,
            scheduled
        )
    )


    delay_target = (
        actual
        or estimated
    )


    calculated_delay = None

    if delay_target:

        calculated_delay = (
            diff_minutes(
                scheduled,
                delay_target
            )
        )


    return {

        "airport":
            raw.get("airport"),

        "iata":
            raw.get("iata"),

        "timezone":
            "Asia/Seoul",

        "timezone_label_ko":
            "한국시간",


        # Aviationstack 원본
        "scheduled_raw":
            scheduled,

        "estimated_raw":
            estimated,

        "actual_raw":
            actual,


        # 현지시간
        "scheduled_local":
            local_iso(
                scheduled,
                "+09:00"
            ),

        "estimated_local":
            local_iso(
                estimated,
                "+09:00"
            ),

        "actual_local":
            local_iso(
                actual,
                "+09:00"
            ),


        "display_time_local":
            local_short(
                operational_time
            ),


        "calculated_delay_minutes":
            calculated_delay,


        "api_delay_minutes":
            raw.get("delay"),


        "terminal":
            raw.get("terminal"),

        "gate":
            raw.get("gate"),
    }


# =========================================================
# 도착 데이터
# PVG = 중국시간
# =========================================================

def normalize_arrival(
    raw: Dict[str, Any]
) -> Dict[str, Any]:

    scheduled = raw.get(
        "scheduled"
    )

    estimated = raw.get(
        "estimated"
    )

    actual = raw.get(
        "actual"
    )


    operational_time = (
        select_display_time(
            actual,
            estimated,
            scheduled
        )
    )


    delay_target = (
        actual
        or estimated
    )


    calculated_delay = None

    if delay_target:

        calculated_delay = (
            diff_minutes(
                scheduled,
                delay_target
            )
        )


    return {

        "airport":
            raw.get("airport"),

        "iata":
            raw.get("iata"),

        "timezone":
            "Asia/Shanghai",

        "timezone_label_ko":
            "중국시간",


        # Aviationstack 원본
        "scheduled_raw":
            scheduled,

        "estimated_raw":
            estimated,

        "actual_raw":
            actual,


        # 현지시간
        "scheduled_local":
            local_iso(
                scheduled,
                "+08:00"
            ),

        "estimated_local":
            local_iso(
                estimated,
                "+08:00"
            ),

        "actual_local":
            local_iso(
                actual,
                "+08:00"
            ),


        "display_time_local":
            local_short(
                operational_time
            ),


        "calculated_delay_minutes":
            calculated_delay,


        "api_delay_minutes":
            raw.get("delay"),


        "terminal":
            raw.get("terminal"),

        "gate":
            raw.get("gate"),
    }


# =========================================================
# 항공편 상태
# =========================================================

def make_status(
    flight_status: str,
    departure: Dict[str, Any],
    arrival: Dict[str, Any]
) -> Dict[str, str]:

    raw_status = (
        flight_status
        or ""
    ).lower()


    # ----------------------------
    # 결항
    # ----------------------------

    if raw_status == "cancelled":

        return {
            "level": "RED",
            "emoji": "🔴",
            "label_ko": "결항",
        }


    # ----------------------------
    # 운항 문제 / 회항
    # ----------------------------

    if raw_status in (
        "incident",
        "diverted"
    ):

        return {
            "level": "RED",
            "emoji": "🔴",
            "label_ko": "운항 문제",
        }


    dep_delay = (
        departure.get(
            "calculated_delay_minutes"
        )
    )

    arr_delay = (
        arrival.get(
            "calculated_delay_minutes"
        )
    )


    # ----------------------------
    # 실제 출발 완료
    # ----------------------------

    if departure.get(
        "actual_raw"
    ):

        if (
            isinstance(
                dep_delay,
                int
            )
            and dep_delay >= 10
        ):

            return {
                "level": "YELLOW",
                "emoji": "🟡",
                "label_ko":
                    f"출발 {dep_delay}분 지연",
            }


        # 도착까지 완료
        if arrival.get(
            "actual_raw"
        ):

            if (
                isinstance(
                    arr_delay,
                    int
                )
                and arr_delay >= 10
            ):

                return {
                    "level": "YELLOW",
                    "emoji": "🟡",
                    "label_ko":
                        f"도착 {arr_delay}분 지연",
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


    # ----------------------------
    # 아직 출발 전
    # ----------------------------

    if (
        isinstance(
            dep_delay,
            int
        )
        and dep_delay >= 10
    ):

        return {
            "level": "YELLOW",
            "emoji": "🟡",
            "label_ko":
                f"출발 예정 {dep_delay}분 지연",
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


# =========================================================
# Aviationstack API 조회
# =========================================================

def load_flight(
    api_key: str,
    flight_iata: str
) -> Dict[str, Any]:

    params = (
        urllib.parse.urlencode({
            "access_key":
                api_key,

            "flight_iata":
                flight_iata,

            "dep_iata":
                "ICN",

            "arr_iata":
                "PVG",

            "limit":
                10,
        })
    )


    url = (
        f"{API_URL}?{params}"
    )


    request = (
        urllib.request.Request(

            url,

            headers={
                "User-Agent":
                    "sblc-typhoon-dashboard/7.3"
            }
        )
    )


    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        payload = json.loads(
            response
            .read()
            .decode("utf-8")
        )


    # API 오류
    if payload.get(
        "error"
    ):

        raise RuntimeError(
            "Aviationstack error "
            f"for {flight_iata}: "
            f"{payload['error']}"
        )


    rows = (
        payload.get(
            "data",
            []
        )
    )


    # 조회 없음
    if not rows:

        return {

            "flight_iata":
                flight_iata,

            "route":
                "ICN → PVG",

            "found":
                False,

            "status": {
                "level":
                    "NO_DATA",

                "emoji":
                    "⚪",

                "label_ko":
                    "조회 결과 없음",
            },
        }


    # =====================================================
    # ICN → PVG 데이터 선택
    # =====================================================

    row = rows[0]


    for candidate in rows:

        dep_iata = (
            candidate
            .get(
                "departure",
                {}
            )
            .get(
                "iata"
            )
        )


        arr_iata = (
            candidate
            .get(
                "arrival",
                {}
            )
            .get(
                "iata"
            )
        )


        flight_data = (
            candidate.get(
                "flight",
                {}
            )
        )


        candidate_flight = (
            flight_data.get(
                "iata"
            )
        )


        if (
            dep_iata == "ICN"
            and
            arr_iata == "PVG"
            and
            candidate_flight == flight_iata
        ):

            row = candidate

            break


    # =====================================================
    # 출발 / 도착
    # =====================================================

    raw_departure = (
        row.get(
            "departure",
            {}
        )
    )


    raw_arrival = (
        row.get(
            "arrival",
            {}
        )
    )


    departure = (
        normalize_departure(
            raw_departure
        )
    )


    arrival = (
        normalize_arrival(
            raw_arrival
        )
    )


    status = (
        make_status(

            row.get(
                "flight_status"
            ),

            departure,

            arrival
        )
    )


    flight = (
        row.get(
            "flight",
            {}
        )
    )


    return {

        "flight_iata":
            flight.get(
                "iata"
            )
            or flight_iata,


        "flight_number":
            flight.get(
                "number"
            ),


        "route":
            "ICN → PVG",


        "found":
            True,


        "status_raw":
            row.get(
                "flight_status"
            ),


        "status":
            status,


        "departure":
            departure,


        "arrival":
            arrival,


        "airline":
            row.get(
                "airline",
                {}
            )
            .get(
                "name"
            ),


        "flight_date":
            row.get(
                "flight_date"
            ),
    }


# =========================================================
# MAIN
# =========================================================

def main() -> int:

    print(
        f"Flight fetch version: "
        f"{PARSER_VERSION}"
    )


    # API KEY
    api_key = (
        os.environ.get(
            "AVIATIONSTACK_API_KEY",
            ""
        )
        .strip()
    )


    if not api_key:

        raise RuntimeError(
            "AVIATIONSTACK_API_KEY "
            "secret is missing."
        )


    results: List[
        Dict[str, Any]
    ] = []


    errors: List[
        Dict[str, str]
    ] = []


    # =====================================================
    # KE315만 조회
    # =====================================================

    for flight in FLIGHTS:

        print(
            f"Fetching "
            f"{flight} "
            f"ICN -> PVG"
        )


        try:

            result = (
                load_flight(
                    api_key,
                    flight
                )
            )


            results.append(
                result
            )


        except Exception as exc:

            errors.append({
                "flight_iata":
                    flight,

                "error":
                    str(exc),
            })


            print(
                f"ERROR "
                f"{flight}: "
                f"{exc}"
            )


    # =====================================================
    # JSON
    # =====================================================

    output = {

        "source":
            "Aviationstack",


        "product":
            "Manual Flight Status",


        "parser_version":
            PARSER_VERSION,


        "route":
            "ICN → PVG",


        "tracked_flights":
            FLIGHTS,


        "time_display": {

            "departure":
                "한국시간",

            "arrival":
                "중국시간",
        },


        "flights":
            results,


        "errors":
            errors,


        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


    # =====================================================
    # 저장
    # =====================================================

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT_PATH.write_text(

        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        )
        + "\n",

        encoding="utf-8"
    )


    print(
        f"Updated: "
        f"{OUTPUT_PATH}"
    )


    print(
        f"Flights returned: "
        f"{len(results)}"
    )


    print(
        f"Errors: "
        f"{len(errors)}"
    )


    return (
        1
        if errors
        else 0
    )


if __name__ == "__main__":

    sys.exit(
        main()
    )
