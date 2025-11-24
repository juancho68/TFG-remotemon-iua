

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const resetForm = document.getElementById("resetForm");

  //  Navegación entre formularios
  document.getElementById("linkRegister").onclick = () => switchForm("register");
  document.getElementById("linkLoginFromReg").onclick = () => switchForm("login");
  document.getElementById("linkReset").onclick = () => switchForm("reset");
  document.getElementById("linkLoginFromReset").onclick = () => switchForm("login");

  function switchForm(form) {
    loginForm.classList.add("hidden");
    registerForm.classList.add("hidden");
    resetForm.classList.add("hidden");
    if (form === "login") loginForm.classList.remove("hidden");
    if (form === "register") registerForm.classList.remove("hidden");
    if (form === "reset") resetForm.classList.remove("hidden");
  }

  // ========================================
  //  LOGIN
  // ========================================
  document.getElementById("btnLogin").onclick = async () => {
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const msg = document.getElementById("msg");

    if (!email || !password) {
      msg.textContent = "⚠️ Ingresá usuario y contraseña";
      return;
    }

    try {
      const res = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (res.ok) {
        console.log("✅ Token recibido:", data.access_token?.slice(0, 30) + "...");
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("role", data.role);
        localStorage.setItem("user_email", data.email);

        setTimeout(() => {
          location.href = "dashboard.html";
        }, 300);
      } else {
        msg.textContent = data.detail || "❌ Error al iniciar sesión";
      }
    } catch (err) {
      console.error("Error en login:", err);
      msg.textContent = "❌ Error de conexión con el servidor.";
    }

    
  };

  // ========================================
  //  REGISTRO
  // ========================================
  document.getElementById("btnRegister").onclick = async () => {
    const email = document.getElementById("regEmail").value.trim();
    const password = document.getElementById("regPassword").value.trim();
    const msg = document.getElementById("msgReg");

    if (!email || !password) {
      msg.textContent = "⚠️ Ingresá correo y contraseña";
      return;
    }

    try {
      const res = await fetch(`${API}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (res.ok) {
        msg.style.color = "green";
        msg.textContent = "✅ Cuenta creada. Verificá tu correo para activarla.";
        // limpiar campos
        document.getElementById("regEmail").value = "";
        document.getElementById("regPassword").value = "";
      } else {
        msg.style.color = "red";
        msg.textContent = data.detail || "❌ No se pudo crear la cuenta";
      }
    } catch (err) {
      console.error("Error en registro:", err);
      msg.style.color = "red";
      msg.textContent = "❌ Error de conexión con el servidor.";
    }
  };

  // ========================================
  //  RESET PASSWORD
  // ========================================
  document.getElementById("btnReset").onclick = async () => {
    const email = document.getElementById("resetEmail").value.trim();
    const msg = document.getElementById("msgReset");

    if (!email) {
      msg.textContent = "⚠️ Ingresá tu correo";
      return;
    }

    try {
      const res = await fetch(`${API}/password/forgot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const data = await res.json();

      if (res.ok) {
        msg.style.color = "green";
        msg.textContent = "✅ Se envió un correo con instrucciones para restablecer tu contraseña.";
      } else {
        msg.style.color = "red";
        msg.textContent = data.detail || "❌ No se pudo enviar el correo.";
      }
    } catch (err) {
      console.error("Error en reset:", err);
      msg.style.color = "red";
      msg.textContent = "❌ Error de conexión con el servidor.";
    }
  };

  // Evitar comportamiento por defecto en los links #
  ["linkRegister","linkLoginFromReg","linkReset","linkLoginFromReset"].forEach(id => {
    const a = document.getElementById(id);
    if (a) a.addEventListener("click", (e) => e.preventDefault(), { capture: true });
  });

  document.getElementById("btnReset").onclick = async () => {
    const email = document.getElementById("resetEmail").value.trim();
    const msg = document.getElementById("msgReset");

    if (!email) {
      msg.textContent = "⚠️ Ingresá tu correo";
      msg.style.color = "orange";
      return;
    }

    //  Función temporal (a desarrollar)
    msg.style.color = "gray";
    msg.textContent = "⏳ Enviando solicitud...";

    await new Promise(r => setTimeout(r, 1000)); // pequeña espera simulada

    msg.style.color = "blue";
    msg.textContent = "💡 Esta función aún está en desarrollo. Próximamente podrás restablecer tu contraseña por correo.";
  };
});
