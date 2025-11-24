// ---------------------------------------------------------
//  Token helper
// ---------------------------------------------------------
function getToken() {
  return localStorage.getItem("token");
}

// ---------------------------------------------------------
//  INIT
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  const role = localStorage.getItem("role");
  const email = localStorage.getItem("user_email");

  const userInfoEl = document.getElementById("userInfo");
  if (userInfoEl) userInfoEl.textContent = email || "";

  if (!email || role !== "admin") {
    alert("Acceso restringido: solo administradores.");
    location.href = "index.html";
    return;
  }

  initTabs();

  await loadUsuarios();
  await loadDispositivos();

  initPermisos();
  initUmbrales();
  initNotificaciones();
  initAjustes();       // cooldown + reset global
});

// ---------------------------------------------------------
//  TABS
// ---------------------------------------------------------
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  const sections = document.querySelectorAll(".tab");

  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabs.forEach((b) => b.classList.remove("active"));
      sections.forEach((s) => s.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
  });
}

// ---------------------------------------------------------
//  USUARIOS
// ---------------------------------------------------------
async function loadUsuarios() {
  const tbody = document.querySelector("#tblUsuarios tbody");

  const selPerm = document.getElementById("selUsuarioPerm");
  const selUmb = document.getElementById("selUsuarioUmbrales");
  const selNotif = document.getElementById("selUsuarioNotificaciones");

  try {
    const res = await fetch("/api/admin/users", {
      headers: { Authorization: "Bearer " + getToken() }
    });

    const data = await res.json();
    const users = data.users || [];

    tbody.innerHTML = "";
    selPerm.innerHTML = "";
    selUmb.innerHTML = "";
    selNotif.innerHTML = "";

    users.forEach((u) => {
      // tabla usuarios
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.email}</td>
        <td>
          <select class="user-role" data-email="${u.email}">
            <option value="user" ${u.role === "user" ? "selected" : ""}>Usuario</option>
            <option value="admin" ${u.role === "admin" ? "selected" : ""}>Admin</option>
          </select>
        </td>
        <td><button class="btnDelete" data-email="${u.email}">🗑️</button></td>
      `;
      tbody.appendChild(tr);

      const opt = document.createElement("option");
      opt.value = u.email;
      opt.textContent = u.email;

      selPerm.appendChild(opt.cloneNode(true));
      selUmb.appendChild(opt.cloneNode(true));
      selNotif.appendChild(opt.cloneNode(true));
    });

    // Cambiar rol
    document.querySelectorAll(".user-role").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await fetch(`/api/admin/users/${sel.dataset.email}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + getToken()
          },
          body: JSON.stringify({ role: sel.value })
        });
        alert("Rol actualizado");
      });
    });

    // Eliminar usuario
    document.querySelectorAll(".btnDelete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const email = btn.dataset.email;
        if (!confirm(`¿Eliminar usuario ${email}?`)) return;

        await fetch(`/api/admin/users/${email}`, {
          method: "DELETE",
          headers: { Authorization: "Bearer " + getToken() }
        });

        await loadUsuarios();
      });
    });

  } catch (err) {
    console.error("Error loading users:", err);
  }
}

// Crear usuario
document.getElementById("btnAddUser")?.addEventListener("click", async () => {
  const email = document.getElementById("newEmail").value.trim();
  const pass = document.getElementById("newPass").value.trim();
  const role = document.getElementById("newRole").value;

  if (!email || !pass) return alert("Complete correo y contraseña");

  const res = await fetch(`/api/admin/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken()
    },
    body: JSON.stringify({ email, password: pass, role })
  });

  if (!res.ok) {
    const err = await res.json();
    return alert(err.detail || "No se pudo crear usuario");
  }

  alert("Usuario creado");
  await loadUsuarios();
});

// ---------------------------------------------------------
//  DISPOSITIVOS
// ---------------------------------------------------------
async function loadDispositivos() {
  const tbody = document.querySelector("#tblDispositivos tbody");
  const selUmbDev = document.getElementById("selDispositivoUmbrales");
  const selNotifDev = document.getElementById("selDispositivoNotificaciones");

  try {
    const res = await fetch("/api/devices", {
      headers: { Authorization: "Bearer " + getToken() }
    });

    const devices = await res.json();

    tbody.innerHTML = "";
    selUmbDev.innerHTML = "";
    selNotifDev.innerHTML = "";

    devices.forEach((d) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${d.device_id}</td><td>${d.name || ""}</td>`;
      tbody.appendChild(tr);

      const opt = document.createElement("option");
      opt.value = d.device_id;
      opt.textContent = d.device_id;

      selUmbDev.appendChild(opt.cloneNode(true));
      selNotifDev.appendChild(opt.cloneNode(true));
    });

  } catch (err) {
    console.error("Error loading devices:", err);
  }
}

// ---------------------------------------------------------
//  PERMISOS
// ---------------------------------------------------------
function initPermisos() {
  const sel = document.getElementById("selUsuarioPerm");

  sel.addEventListener("change", async () => {
    const email = sel.value;
    if (!email) return;

    const res = await fetch(`/api/admin/users/${email}/permissions`, {
      headers: { Authorization: "Bearer " + getToken() }
    });

    const perms = await res.json();
    renderPermisos(perms);
  });

  document.getElementById("btnGuardarPermisos").addEventListener("click", savePermisos);
}

function renderPermisos(perms) {
  const tbody = document.querySelector("#tblPermisos tbody");
  tbody.innerHTML = "";

  perms.forEach((p) => {
    const row = `
      <tr>
        <td>${p.device_id}</td>
        <td><input type="checkbox" ${p.permissions.read_data ? "checked" : ""}></td>
        <td><input type="checkbox" ${p.permissions.write_data ? "checked" : ""}></td>
        <td><input type="checkbox" ${p.permissions.led_green ? "checked" : ""}></td>
        <td><input type="checkbox" ${p.permissions.led_red ? "checked" : ""}></td>
      </tr>
    `;
    tbody.insertAdjacentHTML("beforeend", row);
  });
}

async function savePermisos() {
  const email = document.getElementById("selUsuarioPerm").value;
  if (!email) return;

  const rows = document.querySelectorAll("#tblPermisos tbody tr");

  const payload = [...rows].map((r) => {
    const tds = r.querySelectorAll("td");
    return {
      device_id: tds[0].textContent,
      permissions: {
        read_data: tds[1].querySelector("input").checked,
        write_data: tds[2].querySelector("input").checked,
        led_green: tds[3].querySelector("input").checked,
        led_red: tds[4].querySelector("input").checked
      }
    };
  });

  await fetch(`/api/admin/users/${email}/permissions`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken()
    },
    body: JSON.stringify(payload)
  });

  alert("Permisos guardados.");
}

// ---------------------------------------------------------
// ⚠️ UMBRALES
// ---------------------------------------------------------
function initUmbrales() {
  const selUser = document.getElementById("selUsuarioUmbrales");
  const selDev = document.getElementById("selDispositivoUmbrales");

  selUser.addEventListener("change", loadUmbrales);
  selDev.addEventListener("change", loadUmbrales);

  document.getElementById("btnGuardarUmbrales").addEventListener("click", saveUmbrales);
}

async function loadUmbrales() {
  const user = document.getElementById("selUsuarioUmbrales").value;
  const device = document.getElementById("selDispositivoUmbrales").value;
  const card = document.getElementById("umbralesCard");

  if (!user || !device) return (card.style.display = "none");

  try {
    const res = await fetch(`/api/admin/users/${user}/thresholds/${device}`, {
      headers: { Authorization: "Bearer " + getToken() }
    });

    const data = await res.json();

    card.style.display = "block";

    document.getElementById("tempMin").value = data.temp_min ?? "";
    document.getElementById("tempMax").value = data.temp_max ?? "";
    document.getElementById("humMin").value = data.hum_min ?? "";
    document.getElementById("humMax").value = data.hum_max ?? "";

  } catch (err) {
    console.error("Error loading thresholds:", err);
  }
}

async function saveUmbrales() {
  const user = document.getElementById("selUsuarioUmbrales").value;
  const device = document.getElementById("selDispositivoUmbrales").value;

  const payload = {
    temp_min: Number(document.getElementById("tempMin").value) || null,
    temp_max: Number(document.getElementById("tempMax").value) || null,
    hum_min: Number(document.getElementById("humMin").value) || null,
    hum_max: Number(document.getElementById("humMax").value) || null
  };

  await fetch(`/api/admin/users/${user}/thresholds/${device}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken()
    },
    body: JSON.stringify(payload)
  });

  alert("Umbrales guardados");
}

// ---------------------------------------------------------
// 🔔 NOTIFICACIONES (por usuario/dispositivo)
// ---------------------------------------------------------
function initNotificaciones() {
  const selUser = document.getElementById("selUsuarioNotificaciones");
  const selDev = document.getElementById("selDispositivoNotificaciones");

  selUser.addEventListener("change", loadNotificaciones);
  selDev.addEventListener("change", loadNotificaciones);

  document.getElementById("btnGuardarNotificaciones")
    .addEventListener("click", saveNotificaciones);
}

async function loadNotificaciones() {
  const user = document.getElementById("selUsuarioNotificaciones").value;
  const device = document.getElementById("selDispositivoNotificaciones").value;
  const card = document.getElementById("notificacionesCard");

  if (!user || !device) return (card.style.display = "none");

  try {
    const res = await fetch(`/api/admin/users/${user}/notifications/${device}`, {
      headers: { Authorization: "Bearer " + getToken() }
    });

    const data = await res.json();
    card.style.display = "block";

    document.getElementById("notifTemp").checked = data.temp ?? false;
    document.getElementById("notifHum").checked = data.hum ?? false;
    document.getElementById("notifEmail").checked = data.email ?? false;

  } catch (err) {
    console.error("Error loading notifications:", err);
  }
}

async function saveNotificaciones() {
  const user = document.getElementById("selUsuarioNotificaciones").value;
  const device = document.getElementById("selDispositivoNotificaciones").value;

  const payload = {
    temp: document.getElementById("notifTemp").checked,
    hum: document.getElementById("notifHum").checked,
    email: document.getElementById("notifEmail").checked
  };

  await fetch(`/api/admin/users/${user}/notifications/${device}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken()
    },
    body: JSON.stringify(payload)
  });

  alert("Notificaciones guardadas.");
}

// ---------------------------------------------------------
//  AJUSTES GLOBALES (cooldown + reset)
// ---------------------------------------------------------
function initAjustes() {
  document.getElementById("btnGuardarCooldown")
    .addEventListener("click", saveCooldown);

  document.getElementById("btnResetGlobal")
    .addEventListener("click", resetGlobalAlarmas);

  loadCooldown();
}

// cargar cooldown actual
async function loadCooldown() {
  try {
    const res = await fetch("/api/alarms/cooldown", {
      headers: { Authorization: "Bearer " + getToken() }
    });
    if (!res.ok) return;

    const data = await res.json();
    document.getElementById("cooldownGlobal").value = data.cooldown ?? 60;
  } catch (err) {
    console.error("Error loading cooldown:", err);
  }
}

// guardar cooldown global
async function saveCooldown() {
  const cooldown = Number(document.getElementById("cooldownGlobal").value);

  await fetch("/api/alarms/cooldown", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken()
    },
    body: JSON.stringify({ cooldown })
  });

  alert("Cooldown global guardado");
}

// resetear TODAS las alarmas
async function resetGlobalAlarmas() {
  if (!confirm("¿Resetear TODAS las alarmas del sistema?")) return;

  await fetch("/api/alarms/reset", {
    method: "POST",
    headers: { Authorization: "Bearer " + getToken() }
  });

  alert("Todas las alarmas fueron reseteadas.");
}
