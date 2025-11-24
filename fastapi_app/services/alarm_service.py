# services/alarm_service.py
import uuid
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Attr
from utils.dynamodb_setup import dynamodb, ALARM_LOG_TABLE
from utils.email_service import send_email
from utils.ws_manager import manager

# ============================
#  Tablas
# ============================
alarm_table = dynamodb.Table(ALARM_LOG_TABLE)

# ============================
#  Configuración Global
# ============================
COOLDOWN_MINUTES = 2   # default; editable via API


def set_cooldown_minutes(value: int):
    """Permite cambiar el cooldown desde endpoint admin."""
    global COOLDOWN_MINUTES
    COOLDOWN_MINUTES = int(value)
    print(f"⏱️ Nuevo COOLDOWN_MINUTES = {COOLDOWN_MINUTES}")


def get_cooldown_minutes():
    """Devuelve el cooldown actual."""
    return COOLDOWN_MINUTES


def reset_alarm_log():
    """Elimina todas las alarmas del AlarmLog."""
    scan = alarm_table.scan()
    items = scan.get("Items", [])

    for it in items:
        alarm_table.delete_item(Key={"alarm_id": it["alarm_id"]})

    print("🧹 AlarmLog reseteado (todos los registros eliminados)")
    return len(items)


# ============================
#  Envío de alarmas por WS
# ============================
async def send_alarm_ws(user_email, device_id, alarm_type, value, threshold):
    """Envía una alarma por WebSocket."""
    msg = {
        "type": "alarm",
        "device_id": device_id,
        "timestamp": datetime.utcnow().isoformat(),
        "alarm": {
            "user": user_email,
            "alarm_type": alarm_type,
            "value": float(value),
            "threshold": float(threshold)
        }
    }

    try:
        await manager.broadcast(msg)
        print(f"📡 [WS] Alarma enviada → {device_id} ({alarm_type})")
    except Exception as e:
        print(f"⚠️ Error enviando alarma WS: {e}")


# ============================
#  Procesar alarmas
# ============================
def check_user_threshold_alarms(user, device_id, value_temp, value_hum):
    """
    Revisa umbrales por usuario/dispositivo.
    NOTA:
      - notifications.email → si enviar mail
      - cooldown siempre se aplica para NO spamear
    """

    # Buscar thresholds y notificaciones del usuario para ese device
    dev = None
    for ad in user.get("allowed_devices", []):
        if ad["device_id"] == device_id:
            dev = ad
            break

    if not dev:
        return

    thresholds = dev.get("thresholds", {})
    notify = dev.get("notifications", {})

    notify_email = notify.get("email", False)
    notify_temp = notify.get("temp", True)
    notify_hum = notify.get("hum", True)

    now = datetime.utcnow()

    # ------------------------------------------
    # Auxiliar para procesar una alarma puntual
    # ------------------------------------------
    def process_alarm(alarm_type, value, th, do_email):
        # Chequear cooldown
        resp = alarm_table.scan(
            FilterExpression=(
                Attr("device_id").eq(device_id)
                & Attr("user_email").eq(user["email"])
                & Attr("type").eq(alarm_type)
            )
        )

        recent = resp.get("Items", [])
        for r in recent:
            cooldown = r.get("cooldown_until")
            if cooldown:
                try:
                    dt = datetime.fromisoformat(cooldown)
                    if dt > now:
                        print(f"⏳ Cooldown activo: {alarm_type} → {user['email']}")
                        return
                except:
                    pass

        # Registrar en tabla
        alarm_id = str(uuid.uuid4())
        cooldown_until = (now + timedelta(minutes=COOLDOWN_MINUTES)).isoformat()

        alarm_table.put_item(Item={
            "alarm_id": alarm_id,
            "device_id": device_id,
            "user_email": user["email"],
            "type": alarm_type,
            "value": Decimal(str(value)),
            "threshold": Decimal(str(th)),
            "timestamp": now.isoformat(),
            "cooldown_until": cooldown_until,
            "sent_email": bool(do_email),
        })

        print(f"📢 Alarma registrada: {alarm_type} | {device_id} | {user['email']}")

        # Enviar email (si configurado)
        if do_email:
            send_email(
                user["email"],
                f"⚠️ Alarma IoT en {device_id}: {alarm_type}",
                f"Se detectó una alarma:<br><b>Valor:</b> {value}<br><b>Umbral:</b> {th}"
            )

        # Enviar por WebSocket siempre
        asyncio.create_task(
            send_alarm_ws(user["email"], device_id, alarm_type, value, th)
        )

    # ============================
    #  TEMP
    # ============================
    if value_temp is not None:
        if thresholds.get("temp_min") is not None and value_temp < thresholds["temp_min"]:
            if notify_temp:
                process_alarm("TEMP_LOW", value_temp, thresholds["temp_min"], notify_email)

        if thresholds.get("temp_max") is not None and value_temp > thresholds["temp_max"]:
            if notify_temp:
                process_alarm("TEMP_HIGH", value_temp, thresholds["temp_max"], notify_email)

    # ============================
    #  HUM
    # ============================
    if value_hum is not None:
        if thresholds.get("hum_min") is not None and value_hum < thresholds["hum_min"]:
            if notify_hum:
                process_alarm("HUM_LOW", value_hum, thresholds["hum_min"], notify_email)

        if thresholds.get("hum_max") is not None and value_hum > thresholds["hum_max"]:
            if notify_hum:
                process_alarm("HUM_HIGH", value_hum, thresholds["hum_max"], notify_email)
