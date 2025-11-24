
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Set

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Routers
from auth import router as auth_router
from routes.devices import router as devices_router
from routes.admin import router as admin_router
from routes.alarms import router as alarms_router

# Utils
from utils.security import get_current_user
from utils.dynamodb_setup import ensure_all_tables_exist
from utils.ws_manager import manager
from services.device_user_cache import build_device_user_cache

# MQTT
from iot_mqtt import start_mqtt_listener

# JWT
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET", "supersecreto123")
ALGORITHMS = ["HS256"]

# ------------------------------------------------------------
#  FastAPI App
# ------------------------------------------------------------
app = FastAPI(title="RemoteMon - IoT Backend")

# ------------------------------------------------------------
#  CORS
# ------------------------------------------------------------
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
#  DynamoDB init
# ------------------------------------------------------------
ensure_all_tables_exist()

# ------------------------------------------------------------
#  Helpers WS
# ------------------------------------------------------------
def _parse_devices_param(devices: Optional[str]) -> Optional[Set[str]]:
    if not devices:
        return None
    return set(d.strip() for d in devices.split(",") if d.strip())

def _allowed_set_from_user(user: dict) -> Optional[Set[str]]:
    role = user.get("role")
    if role == "admin":
        return None
    devs = user.get("allowed_devices") or []
    result = {d.get("device_id") for d in devs if d.get("device_id")}
    return result or None

def _decode_user_from_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHMS)
        return {
            "email": payload.get("sub"),
            "role": payload.get("role"),
            "allowed_devices": payload.get("allowed_devices"),
        }
    except JWTError as e:
        print(f"⚠️ WS token inválido: {e}")
        return None


# ------------------------------------------------------------
#  STARTUP
# ------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    print("🚀 Startup: preparando backend y MQTT...")
    build_device_user_cache()
    asyncio.create_task(start_mqtt_listener(manager.broadcast))


# ------------------------------------------------------------
#  RUTAS API – SIEMPRE ANTES DEL WS Y DEL FRONTEND
# ------------------------------------------------------------
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(devices_router)
app.include_router(alarms_router)


# ------------------------------------------------------------
#  WEBSOCKET — NO DEBE SER INTERCEPTADO POR STATICFILES
# ------------------------------------------------------------
@app.websocket("/api/ws")
async def ws_endpoint(
    websocket: WebSocket,
    devices: Optional[str] = Query(default=None),
    token: Optional[str] = Query(default=None),
):
    filt = _parse_devices_param(devices)
    user = _decode_user_from_token(token)

    allowed = email = role = None
    if user:
        email = user.get("email")
        role = user.get("role")
        allowed = _allowed_set_from_user(user)

    try:
        await manager.connect(
            websocket,
            filter_devices=filt,
            allowed_devices=allowed,
            email=email,
            role=role,
        )
        print(f"🔌 WS conectado | filtro={filt} | email={email} | role={role}")

        while True:
            try:
                data_task = asyncio.create_task(websocket.receive_text())

                done, pending = await asyncio.wait(
                    {data_task},
                    timeout=60,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if not done:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    continue

                data = data_task.result()

                if data.strip().lower() == "ping":
                    continue

                print(f"📩 WS data recibida: {data}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ WS error interno: {e}")
                break

    except Exception as e:
        print(f"⚠️ Error WS general: {e}")

    finally:
        manager.disconnect(websocket)
        print(f"❌ WS desconectado | email={email}")


# ------------------------------------------------------------
#  STATIC FILES — NUNCA MONTAR EN "/", SOLO FALLBACK
# ------------------------------------------------------------
# STATIC_DIR = os.path.join(os.path.dirname(__file__), "frontend")
STATIC_DIR = "/app/frontend"
# servir /js, /css, /img, etc.
#app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="frontend"
)

# SPA fallback — cualquier ruta que NO sea /api ni /api/ws va a index.html
# @app.get("/{full_path:path}")
# async def spa_fallback(full_path: str):
#     index_path = os.path.join(STATIC_DIR, "index.html")
#     return FileResponse(index_path)
