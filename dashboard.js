const DATA_URL = "./data/dashboard.json";

const $ = (id) => document.getElementById(id);

const safe = (v, fallback = "-") =>
  v === null || v === undefined || v === "" ? fallback : v;

function riskClass(label) {
  if (label === "높음") return "risk-red";
  if (label === "주의") return "risk-yellow";
  return "risk-green";
}

function shortDate(v) {
  if (!v) return "-";
  return String(v).replace("T", " ").slice(5, 16);
}

function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "-";
  return `${v}${suffix}`;
}

async function loadDashboard() {
  const res = await fetch(`${DATA_URL}?t=${Date.now()}`);

  if (!res.ok) {
    throw new Error(`dashboard.json ${res.status}`);
  }

  const d = await res.json();

  // =========================
  // 현재 태풍
  // =========================

  const t = d.typhoon || {};
  const c = t.current || {};

  $("typhoonName").textContent =
    `${safe(t.number, "")} ${safe(t.name, "")}`.trim() || "-";

  $("typhoonPosition").textContent =
    c.lat != null && c.lon != null
      ? `${c.lat}°N / ${c.lon}°E`
      : "-";

  $("pressure").textContent =
    fmt(c.pressure_hpa, " hPa");

  $("maxWind").textContent =
    fmt(c.max_wind_mps, " m/s");

  $("moveDir").textContent =
    safe(c.movement_direction);

  $("moveSpeed").textContent =
    fmt(c.movement_speed_kmh, " km/h");


  // =========================
  // JMA / KMA 비교
  // =========================

  const comp = d.forecast_comparison || {};

  $("compareBadge").textContent =
    `${safe(comp.emoji, "⚪")} ${safe(
      comp.label_ko,
      "비교자료 없음"
    )}`;

  $("compareAvg").textContent =
    fmt(comp.average_difference_km, " km");

  $("compareMax").textContent =
    fmt(comp.max_difference_km, " km");


  // =========================
  // 태풍 예상 경로
  // =========================

  const track = $("track");

  track.innerHTML = "";

  const currentItem = {
    forecast_hour: 0,
    time: c.time,
    lat: c.lat,
    lon: c.lon,
    pressure_hpa: c.pressure_hpa,
    max_wind_mps: c.max_wind_mps
  };

  [
    currentItem,
    ...(t.forecast_track || [])
  ].forEach((p) => {

    const div =
      document.createElement("div");

    div.className = "track-item";

    div.innerHTML = `
      <div class="hour">
        ${
          p.forecast_hour === 0
            ? "현재"
            : `${p.forecast_hour}시간 후`
        }
      </div>

      <div class="coord">
        ${safe(p.lat)} / ${safe(p.lon)}
      </div>

      <div class="sub">
        ${shortDate(p.time)}
      </div>

      <div class="sub">
        ${fmt(p.pressure_hpa, " hPa")}
        ·
        ${fmt(p.max_wind_mps, " m/s")}
      </div>
    `;

    track.appendChild(div);
  });


  // =========================
  // 물류 거점
  // =========================

  const locations = $("locations");

  locations.innerHTML = "";

  Object.entries(
    d.locations || {}
  ).forEach(([code, item]) => {

    const risk =
      item.risk || {};

    const w =
      item.current_weather || {};

    const div =
      document.createElement("article");

    div.className =
      "location-card";

    div.innerHTML = `
      <div class="location-top">

        <div>

          <div class="location-name">
            ${safe(item.name_ko, code)}
          </div>

          <div class="muted">
            ${code}
            ·
            ${safe(item.trend_ko)}
          </div>

        </div>

        <div class="
          risk-pill
          ${riskClass(risk.label_ko)}
        ">
          ${safe(risk.emoji)}
          ${safe(risk.label_ko)}
        </div>

      </div>

      <div class="location-distance">

        ${fmt(
          item.closest_distance_km,
          " km"
        )}

        <small>
          최접근
        </small>

      </div>

      <div class="muted">
        ${safe(item.reason_ko)}
      </div>

      <div class="weather-row">

        <div>
          <span>현재 강수</span>
          <b>
            ${fmt(w.rain_mm, " mm")}
          </b>
        </div>

        <div>
          <span>풍속</span>
          <b>
            ${fmt(w.wind_mps, " m/s")}
          </b>
        </div>

        <div>
          <span>돌풍</span>
          <b>
            ${fmt(w.gust_mps, " m/s")}
          </b>
        </div>

      </div>
    `;

    locations.appendChild(div);
  });


  // =========================
  // 물류 노선
  // =========================

  const routes =
    $("routes");

  routes.innerHTML = "";

  (d.routes || []).forEach((r) => {

    const risk =
      r.risk || {};

    const div =
      document.createElement("div");

    div.className =
      "list-row";

    div.innerHTML = `
      <div>

        <div class="list-main">
          ${safe(r.name_ko)}
        </div>

        <div class="list-sub">
          ${safe(r.reason_ko)}
        </div>

      </div>

      <div class="
        risk-pill
        ${riskClass(risk.label_ko)}
      ">
        ${safe(risk.emoji)}
        ${safe(risk.label_ko)}
      </div>
    `;

    routes.appendChild(div);
  });


  // =========================
  // 항공편
  // =========================

  const flights =
    $("flights");

  flights.innerHTML = "";

  (d.flights || []).forEach((f) => {

    const status =
      f.status || {};

    const dep =
      f.departure || {};

    const arr =
      f.arrival || {};

    const div =
      document.createElement("div");

    div.className =
      "list-row";

    div.innerHTML = `
      <div>

        <div class="list-main">
          ${safe(f.flight_iata)}
          ·
          ${safe(f.route)}
        </div>

        <div class="list-sub">
          ${safe(status.emoji)}
          ${safe(status.label_ko)}
        </div>

      </div>

      <div class="flight-times">

        출발
        ${shortDate(
          dep.display_time_local
        )}
        (${safe(
          dep.timezone_label_ko
        )})

        <br>

        도착
        ${shortDate(
          arr.display_time_local
        )}
        (${safe(
          arr.timezone_label_ko
        )})

      </div>
    `;

    flights.appendChild(div);
  });


  // =========================
  // 업데이트 시간 / 출처
  // =========================

  $("updatedAt").textContent =
    `통합 데이터 생성: ${
      shortDate(
        d.generated_at_utc
      )
    } UTC`;

  $("attribution").textContent =
    (d.attribution || []).join(
      " · "
    );
}


// =========================
// 새로고침 버튼
// =========================

$("refreshBtn").addEventListener(
  "click",
  () => {

    loadDashboard().catch(
      (err) => {

        $("updatedAt").textContent =
          `오류: ${err.message}`;

      }
    );

  }
);


// =========================
// 최초 실행
// =========================

loadDashboard().catch(
  (err) => {

    $("updatedAt").textContent =
      `데이터 로드 실패: ${err.message}`;

  }
);
