
# iot_mqtt.py
import os, ssl, json, asyncio
import numpy as np
from aiomqtt import Client
from datetime import datetime

from db import save_sensor_data, save_status, get_thresholds
from utils.ml_utils import update_and_predict
from utils.ws_manager import manager  # broadcast WS

#  Alarmas + Cache de usuarios por dispositivo
from services.alarm_service import check_user_threshold_alarms
from services.device_user_cache import get_users_for_device

# ============================================================
# AWS IoT Config
# ============================================================
AWS_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT", "")
AWS_ROOT_CA_PATH = os.getenv("AWS_ROOT_CA_PATH", "")
AWS_CERT_PATH = os.getenv("AWS_CERT_PATH", "")
AWS_KEY_PATH = os.getenv("AWS_KEY_PATH", "")
PORT = 8883

# ============================================================
# SSL Config
# ============================================================
ssl_context = ssl.create_default_context()
if AWS_ROOT_CA_PATH and AWS_CERT_PATH and AWS_KEY_PATH:
    ssl_context.load_verify_locations(AWS_ROOT_CA_PATH)
    ssl_context.load_cert_chain(certfile=AWS_CERT_PATH, keyfile=AWS_KEY_PATH)

# ============================================================
# Buffers por dispositivo
# ============================================================
buffers = {}  # device_id → última N lecturas


# ============================================================
# Cálculo de umbrales dinámicos (media ± 3*std)
# ============================================================
def compute_dynamic_thresholds(device_id):
    readings = buffers.get(device_id, [])
    if len(readings) < 5:
        return None

    temps = np.array([r.get("temperature") for r in readings if "temperature" in r])
    hums = np.array([r.get("humidity") for r in readings if "humidity" in r])

    if temps.size == 0 or hums.size == 0:
        return None

    return {
        "temp_min": float(np.mean(temps) - 3 * np.std(temps)),
        "temp_max": float(np.mean(temps) + 3 * np.std(temps)),
        "hum_min": float(np.mean(hums) - 3 * np.std(hums)),
        "hum_max": float(np.mean(hums) + 3 * np.std(hums)),
    }


# ============================================================
# Listener principal MQTT
# ============================================================
async def start_mqtt_listener(broadcast_callback=None):
    print("🚀 Iniciando listener MQTT...")

    # fallback para broadcast WS
    async def default_broadcast(msg: dict):
        try:
            await manager.broadcast(msg)
            print(f"📡 [WS] Enviado → {msg.get('device_id')} ({msg.get('type')})")
        except Exception as e:
            print(f"⚠️ Error enviando WS: {e}")

    broadcast = broadcast_callback or default_broadcast

    # ========================================================
    # Bucle de reconexión a MQTT
    # ========================================================
    while True:
        try:
            async with Client(
                hostname=AWS_IOT_ENDPOINT,
                port=PORT,
                tls_context=ssl_context,
                keepalive=60,
            ) as client:

                print(f"✅ Conectado a AWS IoT Core → {AWS_IOT_ENDPOINT}")
                await client.subscribe("+/data")
                await client.subscribe("+/status")
                print("📡 Suscrito a '/data' y '/status'")

                # ====================================================
                # Bucle de mensajes MQTT
                # ====================================================
                async for message in client.messages:
                    try:
                        topic = message.topic.value
                        payload_raw = message.payload.decode()

                        print(f"\n📨 [MQTT] Mensaje en {topic}")
                        print(f"    Raw: {payload_raw}")

                        payload = json.loads(payload_raw)
                        device_id = payload.get("device_id") or payload.get("thing")
                        msg_type = "data" if "/data" in topic else "status"

                        if not device_id:
                            print("⚠️ device_id no encontrado, ignorando.")
                            continue

                        # ====================================================
                        #   DATA (Lecturas del sensor)
                        # ====================================================
                        if msg_type == "data":
                            temp = payload.get("temperature")
                            hum = payload.get("humidity")

                            # --- Umbrales configurados en DB ---
                            thresholds_db = await get_thresholds(device_id)
                            thresholds_dyn = compute_dynamic_thresholds(device_id)

                            # Merge: DB override, dinámico fallback
                            thresholds = {
                                "temp_min": thresholds_db.get("temp_min") if thresholds_db else None,
                                "temp_max": thresholds_db.get("temp_max") if thresholds_db else None,
                                "hum_min": thresholds_db.get("hum_min") if thresholds_db else None,
                                "hum_max": thresholds_db.get("hum_max") if thresholds_db else None,
                            }
                            for k, v in (thresholds_dyn or {}).items():
                                if thresholds.get(k) is None:
                                    thresholds[k] = v

                            # --- Detección simple ---
                            temp_anom = hum_anom = False
                            if temp is not None and hum is not None and all(thresholds.values()):
                                temp_anom = not (thresholds["temp_min"] <= temp <= thresholds["temp_max"])
                                hum_anom = not (thresholds["hum_min"] <= hum <= thresholds["hum_max"])

                            # --- ML Predictivo ---
                            ml_results = update_and_predict(temp, hum)

                            # --- Buffer para umbrales dinámicos ---
                            buffers.setdefault(device_id, []).append(payload)
                            buffers[device_id] = buffers[device_id][-100:]

                            # --- Registro final ---
                            record = {
                                "device_id": device_id,
                                "timestamp": datetime.utcnow().isoformat(),
                                "temperature": temp,
                                "humidity": hum,
                                "temp_anomaly": temp_anom,
                                "hum_anomaly": hum_anom,
                                "method": "stat+ml",
                                "calculated_thresholds": thresholds_dyn or {},
                                **ml_results,
                            }

                            print(f"📝 [DB] Guardando lectura → {device_id}")
                            await save_sensor_data(record)

                            # --- Broadcast WS ---
                            await broadcast({
                                "type": "data",
                                "device_id": device_id,
                                "timestamp": record["timestamp"],
                                "values": {
                                    "temperature": temp,
                                    "humidity": hum,
                                    "temp_anomaly": temp_anom,
                                    "hum_anomaly": hum_anom,
                                },
                            })

                            # ====================================================
                            #  PROCESAR ALARMAS POR USUARIO
                            # ====================================================
                            users = get_users_for_device(device_id)

                            if users:
                                for user in users:
                                    try:
                                        check_user_threshold_alarms(
                                            user=user,
                                            device_id=device_id,
                                            value_temp=temp,
                                            value_hum=hum
                                        )
                                    except Exception as e:
                                        print(f"⚠️ Error en alarmas de {user.get('email')}: {e}")
                            else:
                                print(f"ℹ️ No hay usuarios asignados a {device_id}")

                        # ====================================================
                        #   STATUS (LEDs, botón, online/offline)
                        # ====================================================
                        elif msg_type == "status":
                            print(f"🟢 [STATUS] Estado de {device_id}: {payload}")

                            await save_status(payload)
                            print(f"📝 [DB] Guardado estado → {device_id}")

                            await broadcast({
                                "type": "status",
                                "device_id": device_id,
                                "timestamp": datetime.utcnow().isoformat(),
                                "status": {
                                    "led_red": payload.get("led_red"),
                                    "led_green": payload.get("led_green"),
                                    "online": payload.get("online", True),
                                },
                            })

                            print(f"📡 [WS] Status enviado → {device_id}")

                    except Exception as e:
                        print(f"❌ Error procesando mensaje MQTT: {e}")

        except Exception as e:
            print(f"⚠️ Error MQTT: {e}")
            print("⏳ Reintentando en 5s...")
            await asyncio.sleep(5)

