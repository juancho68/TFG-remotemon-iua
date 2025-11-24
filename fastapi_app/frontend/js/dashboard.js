//const API = "/api";

document.addEventListener("DOMContentLoaded", async () => {
  const token = localStorage.getItem("token");
  const userEmail = localStorage.getItem("user_email");
  const deviceList = document.getElementById("deviceList");

  if (!token) return location.href = "index.html";

  document.getElementById("userInfo").textContent = userEmail;

  document.getElementById("btnLogout").onclick = () => {
    localStorage.clear();
    location.href = "index.html";
  };

  // -------------------------------------------
  //  1) Cargar datos del usuario desde /api/me
  // -------------------------------------------
  async function loadUserProfile() {
    try {
      const res = await fetch(`${API}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Error al obtener perfil");

      return await res.json();
    } catch (e) {
      console.error("❌ Error en /api/me:", e);
      return null;
    }
  }

  // -------------------------------------------
  //  2) Cargar resumen de un dispositivo
  // -------------------------------------------
  async function loadDeviceSummary(deviceId) {
    try {
      const res = await fetch(`${API}/devices/${deviceId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) return null;

      return await res.json();
    } catch (e) {
      console.error("❌ Error cargando summary:", e);
      return null;
    }
  }

  // -------------------------------------------
  //  3) Renderizar dispositivo
  // -------------------------------------------
  function renderDevice(device) {
    const card = document.createElement("div");
    card.className = "device-card";
    card.id = `dev-${device.device_id}`;

    const estado = device.estado || "—";
    const temp = device.temperature ?? "--";
    const hum = device.humidity ?? "--";

    card.innerHTML = `
      <h3>${device.device_id}</h3>

      <div class="conn-status" id="conn-${device.device_id}">
        <span class="dot gray"></span> <span>Desconocido</span>
      </div>

      <p><b>Estado:</b> <span id="state-${device.device_id}">${estado}</span></p>

      <p>🌡️ <b>Temp:</b> 
        <span id="temp-${device.device_id}">${temp}</span> °C
      </p>

      <p>💧 <b>Hum:</b> 
        <span id="hum-${device.device_id}">${hum}</span> %
      </p>

      <div class="led-container">
        <span class="led led-red ${device.led_red ? "on" : "off"}" id="led-red-${device.device_id}"></span>
        <span class="led led-green ${device.led_green ? "on" : "off"}" id="led-green-${device.device_id}"></span>
      </div>

      <div class="btn-group">
        <button class="btn-led" onclick="toggleLed('${device.device_id}','rojo')">LED Rojo</button>
        <button class="btn-led" onclick="toggleLed('${device.device_id}','verde')">LED Verde</button>
      </div>


      <button class="reconnect-btn" id="recon-${device.device_id}" style="display:none;">
        🔄 Reconectar
      </button>
    `;

    deviceList.appendChild(card);
  }

  // -------------------------------------------
  //  4) Toggle LED vía API
  // -------------------------------------------
  window.toggleLed = async (deviceId, color) => {
    try {
      const res = await fetch(`${API}/devices/${deviceId}/led/${color}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Error al cambiar LED");
      }
    } catch (e) {
      console.error("❌ toggleLed:", e);
    }
  };

  // -------------------------------------------
  //  5) Actualización de LEDs / estado (WS)
  // -------------------------------------------
  function updateDeviceStatus(deviceId, status) {
    const red = status.led_red;
    const green = status.led_green;

    const ledR = document.getElementById(`led-red-${deviceId}`);
    const ledG = document.getElementById(`led-green-${deviceId}`);

    if (ledR) ledR.className = `led led-red ${red ? "on" : "off"}`;
    if (ledG) ledG.className = `led led-green ${green ? "on" : "off"}`;

    const stateEl = document.getElementById(`state-${deviceId}`);
    if (stateEl) stateEl.textContent = "activo";
  }

  // -------------------------------------------
  //  6) Actualización de datos (WS)
  // -------------------------------------------
  function updateDeviceData(deviceId, values) {
    const tempEl = document.getElementById(`temp-${deviceId}`);
    const humEl = document.getElementById(`hum-${deviceId}`);

    if (tempEl && values.temperature !== undefined)
      tempEl.textContent = values.temperature.toFixed(1);

    if (humEl && values.humidity !== undefined)
      humEl.textContent = values.humidity.toFixed(1);
  }

  // -------------------------------------------
  //  WSClient → Escuchar eventos globales
  // -------------------------------------------
  WSClient.on("data", (msg) => {
    // { type:"data", device_id:"esp32_1", values:{...} }
    updateDeviceData(msg.device_id, msg.values);
  });

  WSClient.on("status", (msg) => {
    // { type:"status", device_id:"esp32_1", status:{...} }
    updateDeviceStatus(msg.device_id, msg.status);

    const el = document.getElementById(`conn-${msg.device_id}`);
    if (el) el.innerHTML = `<span class="dot green"></span> <span>Conectado</span>`;
  });

  WSClient.on("disconnect", (msg) => {
    // { type:"disconnect", device_id:"esp32_1" }
    const el = document.getElementById(`conn-${msg.device_id}`);
    if (el) el.innerHTML = `<span class="dot red"></span> <span>Desconectado</span>`;
  });

  WSClient.on("alarm", (msg) => {
    // TODO: alarm widget en cards
    console.log("🔥 ALARMA WS:", msg);
  });





  // -------------------------------------------
  // 🔥 8) Inicialización completa
  // -------------------------------------------
  const profile = await loadUserProfile();
  if (!profile) return;

  deviceList.innerHTML = ""; // limpia leyenda "cargando dispositivos..."

  const deviceIds = [];

  for (const d of profile.allowed_devices) {
    const dev = await loadDeviceSummary(d.device_id);
    if (dev) {
      renderDevice(dev);
      deviceIds.push(d.device_id);
    }
  }

  // if (deviceIds.length > 0) {
  //   connectWS(deviceIds);
  // }
  WSClient.send({ type: "subscribe", devices: deviceIds });
});
