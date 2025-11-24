# utils/ws_manager.py
from __future__ import annotations
from typing import Optional, Set, Dict, Any, List
from dataclasses import dataclass
import json
import asyncio
from fastapi import WebSocket


@dataclass
class Client:
    ws: WebSocket
    filter_devices: Optional[Set[str]] = None       # filtros enviados por ?devices=
    allowed_devices: Optional[Set[str]] = None      # permisos del token
    email: Optional[str] = None
    role: Optional[str] = None


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: List[Client] = []
        self._lock = asyncio.Lock()

    # ---------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------
    async def connect(
        self,
        websocket: WebSocket,
        filter_devices: Optional[Set[str]] = None,
        allowed_devices: Optional[Set[str]] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:

        await websocket.accept()
        async with self._lock:
            self._clients.append(
                Client(
                    ws=websocket,
                    filter_devices=filter_devices,
                    allowed_devices=allowed_devices,
                    email=email,
                    role=role,
                )
            )

        print(f"🔗 Cliente conectado | email={email} | filtros={filter_devices} | allowed={allowed_devices}")

    # ---------------------------------------------------------
    # DISCONNECT
    # ---------------------------------------------------------
    def disconnect(self, websocket: WebSocket) -> None:
        for i, c in enumerate(self._clients):
            if c.ws is websocket:
                print(f"❌ Cliente desconectado | email={c.email}")
                self._clients.pop(i)
                break

    # ---------------------------------------------------------
    # MATCH RULES
    # ---------------------------------------------------------
    def _matches(self, client: Client, device_id: Optional[str]) -> bool:
        if device_id is None:
            return True

        # filtro explícito enviado por el cliente
        if client.filter_devices is not None and device_id not in client.filter_devices:
            return False

        # permisos del token
        if client.allowed_devices is not None and device_id not in client.allowed_devices:
            return False

        return True

    # ---------------------------------------------------------
    # CLIENT → BACKEND
    # ---------------------------------------------------------
    async def handle_client_message(self, client_ws: WebSocket, client: Client, data: str):
        """
        Procesa los mensajes enviados por el frontend vía WebSocket.
        Ejemplo:
            {"type": "subscribe", "devices": ["esp32_01"]}
        """
        try:
            msg = json.loads(data)
        except Exception:
            print("⚠️ WS mensaje no JSON:", data)
            return

        msg_type = msg.get("type")

        # ---------------------------------------
        # SUBSCRIBE
        # ---------------------------------------
        if msg_type == "subscribe":
            devs = msg.get("devices", [])
            devs = {str(d) for d in devs}

            async with self._lock:
                client.filter_devices = devs

            print(f"📡 Cliente update SUBSCRIBE → {devs}")
            return

        # ---------------------------------------
        # UNSUBSCRIBE
        # ---------------------------------------
        if msg_type == "unsubscribe":
            async with self._lock:
                client.filter_devices = None
            print("📡 Cliente UNSUBSCRIBE (ver todos los permitidos)")
            return

        print(f"ℹ️ Mensaje WS desconocido: {msg}")

    # ---------------------------------------------------------
    # BROADCAST PÚBLICO
    # ---------------------------------------------------------
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast normal. Puede venir con o sin device_id.
        """
        await self._broadcast_internal(message, message.get("device_id"))

    async def broadcast_device_update(self, device_id: str, data: Dict[str, Any]) -> None:
        """
        Utility para mandar un update de dispositivo con device_id garantizado.
        """
        payload = {"device_id": device_id, **data}
        await self._broadcast_internal(payload, device_id)

    # ---------------------------------------------------------
    # BROADCAST INTERNO (con filtrado y type automático)
    # ---------------------------------------------------------
    async def _broadcast_internal(self, message: Dict[str, Any], device_id: Optional[str]) -> None:
        """
        Envío interno del mensaje, agregando 'type' si no está presente.
        Maneja filtrado por clientes y elimina desconectados.
        """

        # -----------------------------
        # 🔥 Normalizar mensaje
        # -----------------------------
        msg = message.copy()

        # Asegurar que todos los mensajes tengan type
        if "type" not in msg:
            msg["type"] = "device_update"

        txt = json.dumps(msg, default=str)
        dead: List[Client] = []

        # Filtrar clientes
        async with self._lock:
            targets = [c for c in self._clients if self._matches(c, device_id)]

        # Enviar a cada cliente sin bloquear el lock
        for c in targets:
            try:
                await c.ws.send_text(txt)
            except Exception:
                dead.append(c)

        # Limpiar conexiones rotas
        if dead:
            async with self._lock:
                for d in dead:
                    try:
                        self._clients.remove(d)
                    except ValueError:
                        pass


# Instancia global
manager = ConnectionManager()
