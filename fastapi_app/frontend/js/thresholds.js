
//const API = "/api";
const token = localStorage.getItem("token");
if (!token) location.href = "index.html";

let userProfile = null;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const userEmail = localStorage.getItem("user_email");
  document.getElementById("userInfo").textContent = userEmail || "";

  document.getElementById("btnLogout").onclick = () => {
    localStorage.clear();
    location.href = "index.html";
  };

  await loadUserProfile();
  setupDeviceSelector();

  document.getElementById("deviceSelect").addEventListener("change", showThresholds);
  document.getElementById("btnSave").addEventListener("click", saveThresholds);
}

// ---------------------------------------------
// Cargar /api/me
// ---------------------------------------------
async function loadUserProfile() {
  try {
    const res = await fetch(`${API}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("Error al obtener perfil");
    userProfile = await res.json();
  } catch (e) {
    console.error("❌ Error obteniendo usuario:", e);
    alert("Error de sesión, iniciá nuevamente.");
    localStorage.clear();
    location.href = "index.html";
  }
}

// ---------------------------------------------
// Llenar selector con solo dispositivos con permiso WRITE
// ---------------------------------------------
function setupDeviceSelector() {
  const select = document.getElementById("deviceSelect");
  select.innerHTML = "<option value=''>Seleccionar...</option>";

  const devices = userProfile.allowed_devices || [];
  const writable = devices.filter(d => d.permissions?.write_data);

  if (!writable.length) {
    select.innerHTML = "<option value=''>No tenés permisos para modificar umbrales</option>";
    return;
  }

  writable.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.device_id;
    opt.textContent = d.device_id;
    select.appendChild(opt);
  });
}

// ---------------------------------------------
// Mostrar umbrales actuales de ese dispositivo
// (vienen directamente de /api/me)
// ---------------------------------------------
function showThresholds() {
  const deviceId = document.getElementById("deviceSelect").value;
  const form = document.getElementById("thresholdForm");
  const msg = document.getElementById("message");
  msg.textContent = "";

  if (!deviceId) {
    form.style.display = "none";
    return;
  }

  const device = userProfile.allowed_devices.find(d => d.device_id === deviceId);
  if (!device) {
    msg.textContent = "⚠ No se encontró este dispositivo.";
    form.style.display = "none";
    return;
  }

  const th = device.thresholds || {};

  document.getElementById("temp_min").value = th.temp_min ?? "";
  document.getElementById("temp_max").value = th.temp_max ?? "";
  document.getElementById("hum_min").value = th.hum_min ?? "";
  document.getElementById("hum_max").value = th.hum_max ?? "";

  form.style.display = "block";
}

// ---------------------------------------------
// Guardar umbrales via PUT admin
// ---------------------------------------------
async function saveThresholds() {
  const deviceId = document.getElementById("deviceSelect").value;
  const msg = document.getElementById("message");

  if (!deviceId) {
    msg.style.color = "orange";
    msg.textContent = "Seleccioná un dispositivo.";
    return;
  }

  const payload = {
    temp_min: parseFloat(document.getElementById("temp_min").value) || null,
    temp_max: parseFloat(document.getElementById("temp_max").value) || null,
    hum_min: parseFloat(document.getElementById("hum_min").value) || null,
    hum_max: parseFloat(document.getElementById("hum_max").value) || null,
  };

  // Nulls si el input está vacío
  Object.keys(payload).forEach(k => {
    if (isNaN(payload[k])) payload[k] = null;
  });

  try {
    const userEmail = userProfile.email;

    const res = await fetch(`${API}/devices/${deviceId}/thresholds`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail ?? "Error al guardar");

    msg.style.color = "green";
    msg.textContent = "✅ Umbrales guardados correctamente.";

    // actualizar cache local para mostrar valores correctos
    const dev = userProfile.allowed_devices.find(d => d.device_id === deviceId);
    if (dev) dev.thresholds = { ...payload };

    setTimeout(() => msg.textContent = "", 3000);

  } catch (e) {
    console.error("❌ Error guardando umbrales:", e);
    msg.style.color = "red";
    msg.textContent = "❌ No se pudieron guardar los cambios.";
  }
}