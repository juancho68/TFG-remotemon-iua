// =====================================================
//  common.js - Funciones globales del usuario logueado
// =====================================================

function getToken() {
  return localStorage.getItem("token");
}

function getUser() {
  const email = localStorage.getItem("user_email");
  const role = localStorage.getItem("role");
  const token = localStorage.getItem("token");
  if (!email || !token) return null;
  return { email, role, token };
}

document.addEventListener("DOMContentLoaded", () => {
  //  Validar login
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");
  const email = localStorage.getItem("user_email");

  if (!token || !email) {
    // Si no hay sesión, redirigir al login
    window.location.href = "index.html";
    return;
  }

  //  Mostrar link de panel admin si el usuario es admin
  const adminLink = document.getElementById("adminLink");
  if (adminLink) {
    if (role === "admin") {
      adminLink.style.display = "inline-block";
    } else {
      adminLink.style.display = "none";
    }
  }

  //  Cerrar sesión
  const btnLogout = document.getElementById("btnLogout");
  if (btnLogout) {
    btnLogout.addEventListener("click", () => {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      localStorage.removeItem("user_email");
      window.location.href = "index.html";
    });
  }
});
