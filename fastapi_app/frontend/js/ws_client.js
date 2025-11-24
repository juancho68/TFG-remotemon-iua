// ======================================================
//  WebSocket Client Global
// ======================================================
//const API = "/api";
const WSClient = (() => {
  const token = localStorage.getItem("token");
  const listeners = {};

  let ws = null;
  let reconnectTimer = null;

  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";

    //  RUTA PARA EL BACKEND
    const url = `${protocol}://${location.host}/api/ws?token=${token}`;

    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log("🟢 WebSocket conectado");
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    ws.onclose = () => {
      console.warn("🔄 WS desconectado, reintentando en 3s");
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error("❌ WS error:", err);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        dispatch(msg);
      } catch (e) {
        console.error("❌ Error al parsear WS:", event.data);
      }
    };
  }

  // ------------------------------
  //  Registrar Listener
  // ------------------------------
  function on(type, callback) {
    if (!listeners[type]) listeners[type] = [];
    listeners[type].push(callback);
  }

  // ------------------------------
  //  Enviar mensaje
  // ------------------------------
  function send(obj) {
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify(obj));
    }
  }

  // ------------------------------
  //  Despachar evento
  // ------------------------------
  function dispatch(msg) {
    if (!msg.type) {
      console.warn("Mensaje WS sin 'type':", msg);
      return;
    }

    const handlers = listeners[msg.type] || [];
    handlers.forEach((fn) => fn(msg));
  }

  // iniciar conexión
  connect();

  return {
    on,
    send
  };
})();
