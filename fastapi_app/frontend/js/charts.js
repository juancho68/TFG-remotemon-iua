
delete window.ResizeObserver;

const token = localStorage.getItem("token");
if (!token) location.href = "index.html";

const chartRefs = {};
const MAX_POINTS = 500;

let userProfile = null;

///////////////////////////////////////////////////////////////
// INIT
///////////////////////////////////////////////////////////////
document.addEventListener("DOMContentLoaded", async () => {
  const userEmail = localStorage.getItem("user_email");
  const infoEl = document.getElementById("userInfo");
  if (infoEl) infoEl.textContent = userEmail || "";

  const logoutBtn = document.getElementById("btnLogout");
  if (logoutBtn) {
    logoutBtn.onclick = () => {
      localStorage.clear();
      location.href = "index.html";
    };
  }

  restoreFilters();

  await loadUserProfile();    // /api/me
  await fetchDevices();       // permisos read_data
  setupClockUTC();

  ["deviceSelect", "sampleSelect", "sinceInput", "untilInput"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", () => {
        saveFilters();
        loadCharts();
      });
    }
  });

  const reloadBtn = document.getElementById("btnReload");
  if (reloadBtn) reloadBtn.onclick = () => loadCharts();
});

///////////////////////////////////////////////////////////////
// /api/me → perfil usuario
///////////////////////////////////////////////////////////////
async function loadUserProfile() {
  try {
    const res = await fetch(`${API}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("No se pudo obtener /api/me");
    userProfile = await res.json();
    console.log("👤 /api/me:", userProfile);
  } catch (err) {
    console.error("❌ Error cargando /api/me:", err);
    alert("Error de sesión, volvé a iniciar.");
    localStorage.clear();
    location.href = "index.html";
  }
}

///////////////////////////////////////////////////////////////
// DEVICES desde userProfile.allowed_devices (solo read_data)
///////////////////////////////////////////////////////////////
async function fetchDevices() {
  try {
    const devices = (userProfile && userProfile.allowed_devices) || [];
    const select = document.getElementById("deviceSelect");
    if (!select) return;

    select.innerHTML = `<option value="">Seleccionar...</option>`;

    devices.forEach((d) => {
      if (d.permissions?.read_data) {
        const opt = document.createElement("option");
        opt.value = d.device_id;
        opt.textContent = d.device_id;
        select.appendChild(opt);
      }
    });

    const savedDevice = localStorage.getItem("chart_device");
    if (savedDevice) select.value = savedDevice;

    if (select.value) loadCharts();
  } catch (err) {
    console.error("❌ Error cargando dispositivos:", err);
  }
}

///////////////////////////////////////////////////////////////
// PERSISTENCIA DE FILTROS
///////////////////////////////////////////////////////////////
function saveFilters() {
  localStorage.setItem("chart_device", document.getElementById("deviceSelect")?.value || "");
  localStorage.setItem("chart_limit", document.getElementById("sampleSelect")?.value || "");
  localStorage.setItem("chart_since", document.getElementById("sinceInput")?.value || "");
  localStorage.setItem("chart_until", document.getElementById("untilInput")?.value || "");
}

function restoreFilters() {
  const limit = localStorage.getItem("chart_limit");
  const since = localStorage.getItem("chart_since");
  const until = localStorage.getItem("chart_until");

  if (limit && document.getElementById("sampleSelect")) {
    document.getElementById("sampleSelect").value = limit;
  }
  if (since && document.getElementById("sinceInput")) {
    document.getElementById("sinceInput").value = since;
  }
  if (until && document.getElementById("untilInput")) {
    document.getElementById("untilInput").value = until;
  }
}

///////////////////////////////////////////////////////////////
// CLOCK
///////////////////////////////////////////////////////////////
function setupClockUTC() {
  const clock = document.getElementById("clockDisplay");
  if (!clock) return;

  const update = () => {
    const now = new Date();
    const utcText = now.toLocaleString("es-AR", {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    clock.textContent = `🕒 ${utcText} UTC`;
  };

  update();
  setInterval(update, 1000);
}

///////////////////////////////////////////////////////////////
// FORMATEO DE TIMESTAMP (para labels)
///////////////////////////////////////////////////////////////
function formatTimestampLabel(ts) {
  try {
    return new Date(ts).toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return String(ts);
  }
}

///////////////////////////////////////////////////////////////
// LOAD CHARTS (inicial)
///////////////////////////////////////////////////////////////
async function loadCharts() {
  const deviceId = document.getElementById("deviceSelect")?.value;
  if (!deviceId) return;

  const limit = document.getElementById("sampleSelect")?.value || 100;
  const since = document.getElementById("sinceInput")?.value;
  const until = document.getElementById("untilInput")?.value;

  const url = new URL(`${API}/${deviceId}/data`, window.location.origin);
  url.searchParams.append("limit", limit);
  if (since) url.searchParams.append("since", since);
  if (until) url.searchParams.append("until", until);

  try {
    const resData = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const readings = await resData.json();

    if (!Array.isArray(readings) || readings.length === 0) {
      clearCharts();
      return;
    }

    const filtered = readings.filter(
      (r) => Number.isFinite(r.temperature) && Number.isFinite(r.humidity)
    );

    const sampled =
      filtered.length > MAX_POINTS
        ? filtered.filter((_, i) => i % Math.ceil(filtered.length / MAX_POINTS) === 0)
        : filtered;

    const userTh = getUserThresholds(deviceId);
    const calcSeries = buildThresholdSeries(sampled);

    renderCharts(deviceId, sampled, userTh, calcSeries);

    // Suscribirse a tiempo real para este dispositivo
    WSClient.send({ type: "subscribe", devices: [deviceId] });
  } catch (err) {
    console.error("❌ Error cargando lecturas:", err);
  }
}

///////////////////////////////////////////////////////////////
// USER THRESHOLDS desde /api/me
///////////////////////////////////////////////////////////////
function getUserThresholds(deviceId) {
  const dev = userProfile?.allowed_devices?.find((d) => d.device_id === deviceId);
  return dev?.thresholds || {};
}

///////////////////////////////////////////////////////////////
// BUILD THRESHOLD SERIES (por muestra)
// Usa calculated_thresholds de CADA fila para graficar curvas.
///////////////////////////////////////////////////////////////
function buildThresholdSeries(rows) {
  const result = {
    tempMin: [],
    tempMax: [],
    humMin: [],
    humMax: [],
  };

  function safeNum(v) {
    return v === undefined || v === null || isNaN(v) ? null : Number(v);
  }

  for (const r of rows) {
    const th = r.calculated_thresholds || {};
    result.tempMin.push(safeNum(th.temp_min));
    result.tempMax.push(safeNum(th.temp_max));
    result.humMin.push(safeNum(th.hum_min));
    result.humMax.push(safeNum(th.hum_max));
  }

  return result;
}

///////////////////////////////////////////////////////////////
function clearCharts() {
  const container = document.getElementById("chartsContainer");
  if (!container) return;

  container.innerHTML = `<p style="color: gray;">Sin datos disponibles.</p>`;
  Object.values(chartRefs).forEach((ch) => ch?.destroy());
}

///////////////////////////////////////////////////////////////
// RENDER CHARTS
///////////////////////////////////////////////////////////////
function renderCharts(deviceId, data, userTh, calcSeries) {
  clearCharts();

  const container = document.getElementById("chartsContainer");
  if (!container) return;

  const labels = data.map((r) => formatTimestampLabel(r.timestamp));

  const temp = data.map((r) => r.temperature);
  const hum = data.map((r) => r.humidity);
  const expectedTemp = data.map((r) => r.expected_temp ?? null);
  const expectedHum = data.map((r) => r.expected_hum ?? null);

  // CONTROLES UI
  container.innerHTML = `
    <div class="chart-controls" style="margin-bottom: 20px;">
      <h4>Temperatura</h4>
      <label><input type="checkbox" data-ds="tempReal" checked> Temperatura</label>
      <label><input type="checkbox" data-ds="tempExpected" checked> Esperada</label>
      <label><input type="checkbox" data-ds="tempCalc" checked> Umbrales Calc</label>
      <label><input type="checkbox" data-ds="tempUser" checked> Umbrales Usuario</label>

      <h4 style="margin-top:20px;">Humedad</h4>
      <label><input type="checkbox" data-ds="humReal" checked> Humedad</label>
      <label><input type="checkbox" data-ds="humExpected" checked> Esperada</label>
      <label><input type="checkbox" data-ds="humCalc" checked> Umbrales Calc</label>
      <label><input type="checkbox" data-ds="humUser" checked> Umbrales Usuario</label>
    </div>
  `;

  // Crear canvas
  const tempCanvas = document.createElement("canvas");
  tempCanvas.width = 900;
  tempCanvas.height = 300;

  const humCanvas = document.createElement("canvas");
  humCanvas.width = 900;
  humCanvas.height = 300;

  container.appendChild(tempCanvas);
  container.appendChild(humCanvas);

  const calcTempSeries = {
    min: calcSeries.tempMin,
    max: calcSeries.tempMax,
  };
  const calcHumSeries = {
    min: calcSeries.humMin,
    max: calcSeries.humMax,
  };

  chartRefs.temperature = createChart(
    tempCanvas,
    labels,
    temp,
    expectedTemp,
    calcTempSeries,
    userTh,
    "temperature"
  );

  chartRefs.humidity = createChart(
    humCanvas,
    labels,
    hum,
    expectedHum,
    calcHumSeries,
    userTh,
    "humidity"
  );

  // Conectar toggles
  container.querySelectorAll("input[type='checkbox']").forEach((chk) => {
    chk.onchange = () => {
      const id = chk.dataset.ds;
      toggleDataset(id, chk.checked);
    };
  });
}

///////////////////////////////////////////////////////////////
// CHART CREATOR
///////////////////////////////////////////////////////////////
function createChart(canvas, labels, primary, expected, calcSeries, userTh, type) {
  const isTemp = type === "temperature";

  function safeNum(v) {
    return v === undefined || v === null || isNaN(v) ? null : Number(v);
  }

  // User thresholds → líneas planas
  const userMinVal = safeNum(userTh?.[isTemp ? "temp_min" : "hum_min"]);
  const userMaxVal = safeNum(userTh?.[isTemp ? "temp_max" : "hum_max"]);
  const userMinSeries = labels.map(() => userMinVal);
  const userMaxSeries = labels.map(() => userMaxVal);

  // Calculated thresholds → curvas por muestra
  const calcMinSeries = calcSeries?.min || labels.map(() => null);
  const calcMaxSeries = calcSeries?.max || labels.map(() => null);

  return new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          datasetId: isTemp ? "tempReal" : "humReal",
          label: isTemp ? "Temperatura (°C)" : "Humedad (%)",
          data: primary,
          borderColor: isTemp ? "red" : "blue",
          fill: false,
        },
        {
          datasetId: isTemp ? "tempExpected" : "humExpected",
          label: "Esperada",
          data: expected,
          borderColor: "orange",
          borderDash: [5, 5],
          fill: false,
        },
        {
          datasetId: isTemp ? "tempCalcMin" : "humCalcMin",
          label: "Th Min Calc",
          data: calcMinSeries,
          borderColor: "cyan",
          borderDash: [4, 2],
          fill: false,
        },
        {
          datasetId: isTemp ? "tempCalcMax" : "humCalcMax",
          label: "Th Max Calc",
          data: calcMaxSeries,
          borderColor: "cyan",
          borderDash: [4, 2],
          fill: false,
        },
        {
          datasetId: isTemp ? "tempUserMin" : "humUserMin",
          label: "Th Min User",
          data: userMinSeries,
          borderColor: "green",
          borderDash: [3, 2],
          fill: false,
        },
        {
          datasetId: isTemp ? "tempUserMax" : "humUserMax",
          label: "Th Max User",
          data: userMaxSeries,
          borderColor: "green",
          borderDash: [3, 2],
          fill: false,
        },
      ],
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          display: true,
          onClick: (e, legendItem, legend) => {
            const chart = legend.chart;
            const dsIndex = legendItem.datasetIndex;
            const datasetId = chart.data.datasets[dsIndex].datasetId;

            chart.data.datasets.forEach((ds) => {
              if (ds.datasetId.startsWith(datasetId.replace("Min", "").replace("Max", ""))) {
                ds.hidden = !ds.hidden;
              }
            });

            chart.update();
          },
        },
      },
    },
  });
}

///////////////////////////////////////////////////////////////
// TOGGLE datasets desde los checkboxes
///////////////////////////////////////////////////////////////
function toggleDataset(id, visible) {
  for (const chart of Object.values(chartRefs)) {
    if (!chart) continue;
    chart.data.datasets.forEach((ds) => {
      if (ds.datasetId.startsWith(id)) ds.hidden = !visible;
    });
    chart.update();
  }
}

///////////////////////////////////////////////////////////////
//  WSClient — escucha de datos en tiempo real
// Se espera mensajes tipo:
// { type: "data", device_id: "esp32_01", values: { ...misma forma que el JSON del endpoint... } }
///////////////////////////////////////////////////////////////
WSClient.on("data", (msg) => {
  const selected = document.getElementById("deviceSelect")?.value;
  if (!selected) return;
  if (msg.device_id !== selected) return;

  if (msg.values) {
    updateChart(msg.values);
  }
});

///////////////////////////////////////////////////////////////
// UPDATE CHART (tiempo real) usando calculated_thresholds
///////////////////////////////////////////////////////////////
function updateChart(values) {
  if (!values) return;

  const label = formatTimestampLabel(values.timestamp);
  const calc = values.calculated_thresholds || {};

  function appendToChart(chart, isTemp) {
    if (!chart) return;

    chart.data.labels.push(label);

    const primaryVal = isTemp ? values.temperature : values.humidity;
    const expectedVal = isTemp ? values.expected_temp : values.expected_hum;
    const calcMinVal = isTemp ? calc.temp_min : calc.hum_min;
    const calcMaxVal = isTemp ? calc.temp_max : calc.hum_max;

    chart.data.datasets.forEach((ds) => {
      const id = ds.datasetId;

      let newVal = null;

      if (id === (isTemp ? "tempReal" : "humReal")) {
        newVal = Number.isFinite(primaryVal) ? primaryVal : null;
      } else if (id === (isTemp ? "tempExpected" : "humExpected")) {
        newVal = Number.isFinite(expectedVal) ? expectedVal : null;
      } else if (id === (isTemp ? "tempCalcMin" : "humCalcMin")) {
        newVal = calcMinVal ?? (ds.data.length ? ds.data[ds.data.length - 1] : null);
      } else if (id === (isTemp ? "tempCalcMax" : "humCalcMax")) {
        newVal = calcMaxVal ?? (ds.data.length ? ds.data[ds.data.length - 1] : null);
      } else if (id === (isTemp ? "tempUserMin" : "humUserMin")) {
        // User thresholds: mantener valor fijo
        newVal = ds.data.length ? ds.data[ds.data.length - 1] : null;
      } else if (id === (isTemp ? "tempUserMax" : "humUserMax")) {
        newVal = ds.data.length ? ds.data[ds.data.length - 1] : null;
      } else {
        // Cualquier otra serie, repetir último valor
        newVal = ds.data.length ? ds.data[ds.data.length - 1] : null;
      }

      ds.data.push(newVal);
    });

    // Limitar a MAX_POINTS
    if (chart.data.labels.length > MAX_POINTS) {
      chart.data.labels.shift();
      chart.data.datasets.forEach((d) => d.data.shift());
    }

    chart.update("none");
  }

  appendToChart(chartRefs.temperature, true);
  appendToChart(chartRefs.humidity, false);
}
