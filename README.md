# SBLC 태풍 대시보드 — Step 1: JMA

이 단계의 목적은 **JMA(일본기상청)의 5일 태풍 분석·예보 XML을 GitHub Actions가 자동 수집해서 `data/jma_typhoon.json`으로 저장**하는 것입니다.

## 현재 포함된 물류 거점

- SUZHOU — 쑤저우
- PVG — 상하이 푸동국제공항
- ICN — 인천국제공항
- CRK — 필리핀 클락국제공항
- HAN — 베트남 하노이 노이바이 국제공항

## JMA 원본

- 고빈도 수시 Feed: `https://www.data.jma.go.jp/developer/xml/feed/extra.xml`
- 장기 수시 Feed: `https://www.data.jma.go.jp/developer/xml/feed/extra_l.xml`
- 대상: `台風解析・予報情報（５日予報）`
- 현재 제품 계열: VPTW60 ~ VPTW65

스크립트는 고빈도 Feed와 장기 Feed를 같이 읽습니다.
고빈도 Feed에 최근 10분 데이터만 남아 있어도 장기 Feed를 fallback으로 사용합니다.

## GitHub에 올리는 방법

이 ZIP의 내용물을 GitHub 저장소 루트에 그대로 넣습니다.

구조:

```text
.github/
  workflows/
    jma_typhoon.yml
config/
  locations.json
data/
  jma_typhoon.json
src/
  fetch_jma_typhoon.py
README.md
```

## 최초 테스트

GitHub 저장소에서:

1. `Actions`
2. `JMA Typhoon Fetch`
3. `Run workflow`
4. 실행 완료 후 `data/jma_typhoon.json` 확인

태풍이 활동 중이면 `typhoons` 배열에 데이터가 들어갑니다.
활동 중인 태풍이 없으면 `active_count: 0`이 정상입니다.

## 자동 실행

현재 30분마다 실행하도록 설정했습니다.

```yaml
- cron: "7,37 * * * *"
```

GitHub Actions의 cron은 UTC 기준입니다.

## JSON에서 바로 확인할 수 있는 값

각 태풍에 대해:

- 태풍 번호 / 영문명
- JMA 발표시각
- 현재 중심 위도·경도
- 중심기압
- 최대풍속 / 최대순간풍속
- 이동방향 / 이동속도
- 미래 예상 위치
- 예보원 반경(제공되는 경우)
- 태풍 중심과 SUZHOU / PVG / ICN / CRK / HAN 사이 거리(km)

예:

```json
{
  "analysis": {
    "lat": 26.1,
    "lon": 131.2,
    "pressure_hpa": 965,
    "distances_km": {
      "SUZHOU": 1200,
      "PVG": 1100,
      "ICN": 980,
      "CRK": 1600,
      "HAN": 1850
    }
  }
}
```

## 중요

JMA XML의 실제 데이터가 있는 시점에 GitHub에서 최초 1회 수동 실행해
`data/jma_typhoon.json`을 확인하는 것이 Step 1 검증입니다.

다음 단계에서는 이 JSON을 바탕으로:

1. JMA 현재 경로 표시
2. PVG / SUZHOU / ICN / CRK / HAN 거리
3. 24/48/72/96/120h 접근거리
4. 최접근 시간 계산

을 대시보드 카드로 만듭니다.
