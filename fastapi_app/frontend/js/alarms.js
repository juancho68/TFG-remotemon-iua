

//const API = "/api";
const token = localStorage.getItem("token");
if (!token) location.href = "index.html";

document.addEventListener("DOMContentLoaded", () => {
  const userEmail = localStorage.getItem("user_email");
  const userInfo = document.getElementById("userInfo");
  if (userInfo) {
    userInfo.textContent = userEmail ? `Usuario: ${userEmail}` : "";
  }

  const btnLogout = document.getElementById("btnLogout");
  if (btnLogout) {
    btnLogout.onclick = () => {
      localStorage.clear();
      location.href = "index.html";
    };
  }

  setupClockUTC();
  loadDevices();
  loadAlarms();

  document.getElementById("btnFilter").onclick = () => loadAlarms();
  document.getElementById("btnClear").onclick = clearFilters;
});

// =======================================================
// RELOJ UTC
// =======================================================
function setupClockUTC() {
  const el = document.getElementById("clockUTC");
  if (!el) return;

  const update = () => {
    const now = new Date();
    const utc = now.toLocaleString("es-AR", {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    });
    el.textContent = `🕒 ${utc} UTC`;
  };

  update();
  setInterval(update, 1000);
}

// =======================================================
// CARGAR DISPOSITIVOS PARA FILTRO (solo allowed_devices)
// =======================================================
async function loadDevices() {
  const select = document.getElementById("deviceSelect");
  if (!select) return;

  select.innerHTML = `<option value="">Todos</option>`;

  try {
    const resMe = await fetch(`${API}/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!resMe.ok) {
      console.error("Error /api/me", await resMe.text());
      return;
    }

    const user = await resMe.json();

    (user.allowed_devices || [])
      .filter(d => d.permissions && d.permissions.read_data)
      .forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.device_id;
        opt.textContent = d.device_id;
        select.appendChild(opt);
      });

  } catch (err) {
    console.error("Error cargando dispositivos:", err);
  }
}

// =======================================================
// LIMPIAR FILTROS
// =======================================================
function clearFilters() {
  const sel = document.getElementById("deviceSelect");
  const from = document.getElementById("dateFrom");
  const to = document.getElementById("dateTo");

  if (sel) sel.value = "";
  if (from) from.value = "";
  if (to) to.value = "";

  loadAlarms();
}

// =======================================================
// CARGAR ALARMAS
// =======================================================
async function loadAlarms() {
  const device = document.getElementById("deviceSelect").value;
  const since = document.getElementById("dateFrom").value;
  const until = document.getElementById("dateTo").value;

  const url = new URL(`${API}/alarms`, window.location.origin);

  if (device) url.searchParams.append("device_id", device);
  if (since) url.searchParams.append("since", since);
  if (until) url.searchParams.append("until", until);

  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!res.ok) {
      console.error("Error /api/alarms:", await res.text());
      renderAlarms([]);
      return;
    }

    const data = await res.json();
    // asumo que tu endpoint devuelve { items: [...] }
    renderAlarms(data.items || data);

  } catch (err) {
    console.error("Error cargando alarmas:", err);
    renderAlarms([]);
  }
}

// =======================================================
// RENDERIZAR ALARMAS EN TABLA
// =======================================================
function renderAlarms(alarms) {
  const body = document.getElementById("alarmsBody");
  body.innerHTML = "";

  if (!alarms || alarms.length === 0) {
    body.innerHTML = `<tr><td colspan="6" class="no-data">Sin alarmas registradas</td></tr>`;
    return;
  }

  alarms.forEach(a => {
    const tr = document.createElement("tr");

    const date = new Date(a.timestamp).toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });

    tr.innerHTML = `
      <td>${date}</td>
      <td>${a.device_id}</td>
      <td class="${colorAlarm(a.type)}">${a.type}</td>
      <td>${a.value}</td>
      <td>${a.threshold}</td>
      <td>${a.sent_email ? "📧 Sí" : "—"}</td>
    `;

    body.appendChild(tr);
  });
}

// =======================================================
// COLORES PARA TIPOS DE ALARMA
// =======================================================
function colorAlarm(type) {
  if (!type) return "";
  if (type.includes("HIGH")) return "alarm-high";
  if (type.includes("LOW")) return "alarm-low";
  return "";
}
