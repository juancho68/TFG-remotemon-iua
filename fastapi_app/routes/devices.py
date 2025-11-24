

from db import (
    send_command,
    get_status,
    get_sensor_data,
    get_thresholds,
    save_thresholds,
    dynamodb,
    STATUS_TABLE_NAME,

)
from utils.dynamodb_setup import dynamodb, USERS_TABLE_NAME
from fastapi import APIRouter, Depends, HTTPException, Query
from utils.security import get_current_user
from utils.permissions import check_device_permission
from utils.ws_manager import manager
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime, timezone
import os, sys, asyncio
from typing import Optional

# Forzar que use el mqtt_utils.py real de la raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mqtt_utils import mqtt_publish_message

DEVICE_STATUS_TABLE = "DeviceStatus"
router = APIRouter()

users_table = dynamodb.Table(USERS_TABLE_NAME)

# ==========================================================
# 📦 Modelos
# ==========================================================
class ThresholdsModel(BaseModel):
    temp_min: float
    temp_max: float
    hum_min: float
    hum_max: float

class ThresholdsUpdate(BaseModel):
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    hum_min: Optional[float] = None
    hum_max: Optional[float] = None


# ==========================================================
#  Utils
# ==========================================================
def to_float_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def is_online(value):
    """Normaliza el campo 'online' para distintos formatos"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return False


# ==========================================================
#  Obtener último estado de LED
# ==========================================================
async def get_last_led_state(device_id: str, led_color: str) -> bool:
    print(f"🔎 [READ] Buscando último estado de {led_color} para {device_id}...")
    table = dynamodb.Table(DEVICE_STATUS_TABLE)
    try:
        response = table.query(
            KeyConditionExpression=Key("device_id").eq(device_id),
            ScanIndexForward=False,
            Limit=10,
        )
        items = response.get("Items", [])
        for item in items:
            status = item.get("status", {})
            if isinstance(status, dict) and f"led_{led_color}" in status:
                return bool(status[f"led_{led_color}"])
        return False
    except Exception as e:
        print(f"❌ [ERROR] Consultando DynamoDB: {e}")
        return False


# ==========================================================
#  Toggle LED
# ==========================================================
@router.post("/api/devices/{device_id}/led/{color}")
async def toggle_led(device_id: str, color: str, user=Depends(get_current_user)):
    LED_MAP = {"rojo": "led_red", "verde": "led_green"}
    COLOR_MAP = {"rojo": "red", "verde": "green"}

    led_key = LED_MAP.get(color)
    mqtt_color = COLOR_MAP.get(color)
    if not led_key or not mqtt_color:
        raise HTTPException(status_code=400, detail=f"Color '{color}' no soportado")

    print(f"🔍 Verificando permisos para {user['email']} → {device_id}/{led_key}")
    check_device_permission(user, device_id, led_key)

    # Estado previo
    record = await get_status(device_id)
    prev_state = record.get("status", {}).get(led_key, False) if record else False
    new_state = not prev_state
    action = "on" if new_state else "off"
    print(f"🔁 [DECIDE] {led_key}: {prev_state} → {new_state}")

    # MQTT
    payload = {"command": "led_control", "led": mqtt_color, "action": action}
    await send_command(device_id, payload)

    # Actualizar DeviceStatus
    try:
        table = dynamodb.Table(DEVICE_STATUS_TABLE)
        table.put_item(
            Item={
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": {"thing": device_id, "online": True, led_key: new_state},
            }
        )
    except Exception as e:
        print(f"⚠️ Error actualizando DeviceStatus: {e}")

    # Broadcast WS
    try:
        await manager.broadcast_device_update(
            device_id,
            {"estado": "activo", led_key: new_state, "last_update": datetime.utcnow().isoformat()},
        )
    except Exception as e:
        print(f"⚠️ WS error: {e}")

    return {"status": "ok", "device_id": device_id, "led": color, "action": action}


# ==========================================================
#  Listar dispositivos
# ==========================================================
@router.get("/api/devices")
async def list_user_devices(user=Depends(get_current_user)):
    """
    Lista los dispositivos disponibles para el usuario.
    Si es admin → lista todos los dispositivos del sistema.
    """

    sensor_table = dynamodb.Table("SensorData")
    status_table = dynamodb.Table("DeviceStatus")

    is_admin = user.get("role") == "admin"
    devices_result = []

    # ==========================================================
    #  ADMIN — ver TODOS los dispositivos reales del sistema
    # ==========================================================
    if is_admin:
        try:
            # scan_resp = sensor_table.scan()
            # items = scan_resp.get("Items", [])
            items = []
            resp = sensor_table.scan()
            items.extend(resp.get("Items", []))

            while "LastEvaluatedKey" in resp:
                resp = sensor_table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
                items.extend(resp.get("Items", []))
        except Exception as e:
            print(f"❌ Error scan SensorData: {e}")
            return []

        latest = {}

        # Obtener solo el último registro real por device
        for item in items:
            device_id = item.get("device_id")
            ts_str = item.get("timestamp")

            if not device_id or not ts_str:
                continue

            # convertir timestamp
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", ""))
            except:
                continue

            if device_id not in latest:
                latest[device_id] = {"ts": ts, "item": item}
            else:
                if ts > latest[device_id]["ts"]:
                    latest[device_id] = {"ts": ts, "item": item}

        # Construir respuesta final
        for device_id, data in latest.items():
            item = data["item"]
            temp = float(item.get("temperature", 0))
            hum = float(item.get("humidity", 0))
            ts = item.get("timestamp")

            # Estado digital
            online = led_red = led_green = None
            try:
                resp = status_table.query(
                    KeyConditionExpression=Key("device_id").eq(device_id),
                    ScanIndexForward=False,
                    Limit=20,
                )
                for s_item in resp.get("Items", []):
                    s = s_item.get("status")
                    if not isinstance(s, dict):
                        continue

                    if online is None and "online" in s:
                        online = s["online"]
                    if led_red is None and "led_red" in s:
                        led_red = s["led_red"]
                    if led_green is None and "led_green" in s:
                        led_green = s["led_green"]

                    if online is not None and led_red is not None and led_green is not None:
                        break

            except Exception as e:
                print(f"⚠️ Error leyendo DeviceStatus {device_id}: {e}")

            estado = "activo" if is_online(online) else "desconectado"

            devices_result.append(
                {
                    "device_id": device_id,
                    "temperature": temp,
                    "humidity": hum,
                    "last_update": ts,
                    "estado": estado,
                    "led_red": led_red,
                    "led_green": led_green,
                    "permissions": {
                        "read_data": True,
                        "write_data": True,
                        "led_red": True,
                        "led_green": True,
                    },
                }
            )

        return devices_result

    # ==========================================================
    # USUARIO NORMAL — ver solo sus devices permitidos
    # ==========================================================
    user_devices = user.get("allowed_devices") or []
    if not user_devices:
        return []

    for entry in user_devices:
        device_id = entry.get("device_id")
        perms = entry.get("permissions", {})

        if not device_id or not perms.get("read_data", False):
            continue

        # Últimos datos del sensor
        temperature = humidity = timestamp = None
        try:
            resp = sensor_table.query(
                KeyConditionExpression=Key("device_id").eq(device_id),
                ScanIndexForward=False,
                Limit=1,
            )
            items = resp.get("Items", [])
            if items:
                item = items[0]
                temperature = float(item.get("temperature", 0))
                humidity = float(item.get("humidity", 0))
                timestamp = item.get("timestamp")
        except Exception as e:
            print(f"⚠️ Error leyendo SensorData {device_id}: {e}")

        # Estado digital
        online = led_red = led_green = None
        try:
            resp2 = status_table.query(
                KeyConditionExpression=Key("device_id").eq(device_id),
                ScanIndexForward=False,
                Limit=20,
            )
            for s_item in resp2.get("Items", []):
                s = s_item.get("status", {})
                if not isinstance(s, dict):
                    continue

                if online is None and "online" in s:
                    online = s["online"]
                if led_red is None and "led_red" in s:
                    led_red = s["led_red"]
                if led_green is None and "led_green" in s:
                    led_green = s["led_green"]

                if online is not None and led_red is not None and led_green is not None:
                    break

        except Exception as e:
            print(f"⚠️ Error leyendo DeviceStatus {device_id}: {e}")

        estado = "activo" if is_online(online) else "desconectado"

        devices_result.append(
            {
                "device_id": device_id,
                "temperature": temperature,
                "humidity": humidity,
                "last_update": timestamp,
                "estado": estado,
                "led_red": led_red,
                "led_green": led_green,
                "permissions": perms,
            }
        )

    return devices_result


# ==========================================================
# Lectura de datos con rango horario
# ==========================================================
from datetime import datetime, timezone
from dateutil import parser as dateparser
from fastapi import Query, HTTPException, Depends

@router.get("/api/{device_id}/data")
async def get_device_data(
    device_id: str,
    limit: int = Query(50, description="Cantidad máxima de lecturas"),
    since: str = Query(None, description="Fecha y hora inicial"),
    until: str = Query(None, description="Fecha y hora final"),
    only_anomalies: bool = Query(False, description="Filtrar solo lecturas anómalas"),
    flat: bool = Query(True, description="Si True, devuelve lista plana"),
    user=Depends(get_current_user),
):
    # 🔐 Verificar permisos de lectura
    if not check_device_permission(user, device_id, "read_data"):
        raise HTTPException(status_code=403, detail="Sin permiso de lectura")

    # 🕒 Función auxiliar de parseo de fechas
    def parse_date(value: str):
        if not value:
            return None
        try:
            # Timestamps numéricos (segundos o milisegundos)
            if value.isdigit():
                ts = int(value)
                if ts > 1e12:  # milisegundos
                    ts /= 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            # ISO8601 (permite “Z”, zona, milisegundos, etc.)
            return dateparser.parse(value)
        except Exception as e:
            print(f"⚠️ No se pudo interpretar fecha '{value}': {e}")
            return None

    since_dt = parse_date(since)
    until_dt = parse_date(until)
    print(f"🕒 Filtro aplicado → since={since_dt}, until={until_dt}")

    # 📊 Obtener lecturas de DynamoDB
    try:
        readings = await get_sensor_data(
            device_id=device_id,
            limit=limit,
            since=since_dt.isoformat() if since_dt else None,
            until=until_dt.isoformat() if until_dt else None,
            only_anomalies=only_anomalies,
        )
    except TypeError:
        # Compatibilidad con versiones antiguas de get_sensor_data
        readings = await get_sensor_data(
            device_id=device_id,
            limit=limit,
            since=since_dt.isoformat() if since_dt else None,
            only_anomalies=only_anomalies,
        )

    #  Filtro manual (rango exacto en Python)
    filtered = []
    for r in readings:
        ts = r.get("timestamp")
        if not ts:
            continue
        try:
            ts_dt = dateparser.parse(ts)
        except Exception:
            continue

        if since_dt and ts_dt < since_dt:
            continue
        if until_dt and ts_dt > until_dt:
            continue
        filtered.append(r)

    readings = filtered
    readings.sort(key=lambda x: x.get("timestamp", ""))

    print(f"📊 [API] get_device_data → {len(readings)} lecturas para {device_id}")

    return readings if flat else {"device_id": device_id, "count": len(readings), "items": readings}


# ==========================================================
# Resumen dispositivo
# ==========================================================
@router.get("/api/devices/{device_id}")
async def get_device_summary(device_id: str, user=Depends(get_current_user)):
    """Devuelve el resumen de un dispositivo (última lectura + estado + permisos)"""
    sensor_table = dynamodb.Table("SensorData")
    status_table = dynamodb.Table("DeviceStatus")

    is_admin = user.get("role") == "admin"

    perms = {"read_data": False, "write_data": False, "led_red": False, "led_green": False}
    if not is_admin:
        found = next((d for d in (user.get("allowed_devices") or []) if d.get("device_id") == device_id), None)
        if not found:
            raise HTTPException(status_code=403, detail="Acceso denegado al dispositivo")
        perms = found.get("permissions", perms)
        if not perms.get("read_data"):
            raise HTTPException(status_code=403, detail="No tenés permiso de lectura")
    else:
        perms = {"read_data": True, "write_data": True, "led_red": True, "led_green": True}

    temperature = humidity = timestamp = None
    try:
        resp = sensor_table.query(KeyConditionExpression=Key("device_id").eq(device_id), ScanIndexForward=False, Limit=1)
        items = resp.get("Items", [])
        if items:
            item = items[0]
            temperature = float(item.get("temperature", 0))
            humidity = float(item.get("humidity", 0))
            timestamp = item.get("timestamp")
    except Exception as e:
        print(f"⚠️ Error leyendo SensorData {device_id}: {e}")

    online = led_red = led_green = None
    try:
        resp2 = status_table.query(KeyConditionExpression=Key("device_id").eq(device_id), ScanIndexForward=False, Limit=20)
        for s_item in resp2.get("Items", []):
            s = s_item.get("status", {})
            if not isinstance(s, dict):
                continue
            if online is None and "online" in s:
                online = s["online"]
            if led_red is None and "led_red" in s:
                led_red = s["led_red"]
            if led_green is None and "led_green" in s:
                led_green = s["led_green"]
            if online is not None and led_red is not None and led_green is not None:
                break
    except Exception as e:
        print(f"⚠️ Error leyendo DeviceStatus {device_id}: {e}")

    estado = "activo" if is_online(online) else "desconectado"

    return {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "last_update": timestamp,
        "estado": estado,
        "led_red": led_red,
        "led_green": led_green,
        "permissions": perms,
    }



#########################

@router.put("/api/devices/{device_id}/thresholds")
def update_my_thresholds(device_id: str, payload: ThresholdsUpdate, user=Depends(get_current_user)):

    email = user["email"]

    # 🔍 Obtener usuario real de DynamoDB
    resp = users_table.get_item(Key={"email": email})
    if "Item" not in resp:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_item = resp["Item"]
    allowed_devices = user_item.get("allowed_devices", [])

    # 🔍 Buscar dispositivo dentro del usuario
    idx = next((i for i, d in enumerate(allowed_devices) if d["device_id"] == device_id), None)
    if idx is None:
        raise HTTPException(403, "No tenés acceso a este dispositivo")

    dev_entry = allowed_devices[idx]

    # 🔐 Verificar permisos de escritura
    if not dev_entry["permissions"].get("write_data", False):
        raise HTTPException(403, "No tenés permiso para modificar umbrales")

    # 🧮 Conversión segura a Decimal
    def to_decimal(value):
        if value is None:
            return None
        return Decimal(str(value))

    new_thresholds = {
        "temp_min": to_decimal(payload.temp_min),
        "temp_max": to_decimal(payload.temp_max),
        "hum_min": to_decimal(payload.hum_min),
        "hum_max": to_decimal(payload.hum_max),
    }

    # 📝 Guardar dentro del user
    dev_entry["thresholds"] = new_thresholds
    allowed_devices[idx] = dev_entry
    user_item["allowed_devices"] = allowed_devices

    # 💾 Guardar el usuario completo en DynamoDB
    users_table.put_item(Item=user_item)

    return {
        "msg": "Umbrales guardados correctamente",
        "device_id": device_id,
        "thresholds": new_thresholds
    }