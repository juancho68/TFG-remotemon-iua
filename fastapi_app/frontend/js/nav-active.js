const page = location.pathname;

if (page.includes("dashboard")) navDashboard.classList.add("active");
if (page.includes("charts")) navCharts.classList.add("active");
if (page.includes("thresholds")) navThresholds.classList.add("active");
if (page.includes("alarms")) navAlarms.classList.add("active");
if (page.includes("admin")) navAdmin.classList.add("active");

document.addEventListener("DOMContentLoaded", () => {
  const role = localStorage.getItem("role");

  // Ocultar opción Panel Admin si no es admin
  const adminLink = document.getElementById("navAdmin");
if (adminLink && role !== "admin") {
    adminLink.remove();  // elimina el nodo del DOM
}


  const toggle = document.getElementById("menuToggle");
  const nav = document.querySelector(".nav-center");

  if (toggle) {
    toggle.onclick = () => {
      nav.classList.toggle("show");
    };
  }
});