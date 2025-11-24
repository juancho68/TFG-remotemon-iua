
import os
import json
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from awscrt import mqtt
from awsiot import mqtt_connection_builder
import numpy as np

from utils.dynamodb_setup import (
    dynamodb,
    DATA_TABLE_NAME,
    STATUS_TABLE_NAME,
    THRESHOLDS_TABLE_NAME,
)

# =====================================================
#  Configuración AWS IoT
# =====================================================
AWS_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT", "")
ROOT_CA_PATH = os.getenv("AWS_ROOT_CA_PATH", "")
CERT_PATH = os.getenv("AWS_CERT_PATH", "")
KEY_PATH = os.getenv("AWS_KEY_PATH", "")


def sanitize_for_dynamodb(value):
    """Convierte tipos no compatibles (como np.bool_) a tipos nativos de Python."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: sanitize_for_dynamodb(v) for k, v in value.items()}
    return value


# =====================================================
#  SensorData (unificada con anomalías)
# =====================================================
async def save_sensor_data(payload: dict):
    try:
        table = dynamodb.Table(DATA_TABLE_NAME)
        item = {
            "device_id": payload.get("device_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": payload.get("temperature"),
            "humidity": payload.get("humidity"),
            "temp_anomaly": payload.get("temp_anomaly", False),
            "hum_anomaly": payload.get("hum_anomaly", False),
            "ml_temp_anomaly": payload.get("ml_temp_anomaly", False),
            "ml_hum_anomaly": payload.get("ml_hum_anomaly", False),
            "ml_score_temp": payload.get("ml_score_temp", 0),
            "ml_score_hum": payload.get("ml_score_hum", 0),
            "expected_temp": payload.get("expected_temp"),
            "expected_hum": payload.get("expected_hum"),
            "method": payload.get("method", "stat+ml"),
            "calculated_thresholds": payload.get("calculated_thresholds", {}),
        }
        item = {k: sanitize_for_dynamodb(v) for k, v in item.items()}
        table.put_item(Item=item)
        print(f"📝 [WRITE] Guardado extendido en {DATA_TABLE_NAME}: {item['device_id']}")
    except Exception as e:
        print(f"❌ Error guardando sensor data: {e}")


# =====================================================
#  DeviceStatus
# =====================================================
async def save_status(payload: dict):
    """Guarda el estado de un dispositivo (LEDs, conexión, etc.)."""
    try:
        table = dynamodb.Table(STATUS_TABLE_NAME)
        device_id = payload.get("device_id") or payload.get("thing")
        item = {
            "device_id": device_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": payload,
        }
        table.put_item(Item=item)
        print(f"📝 [WRITE] Guardado estado en {STATUS_TABLE_NAME}: {device_id}")
    except Exception as e:
        print(f"❌ Error guardando estado: {e}")


# =====================================================
#  get_status
# =====================================================
async def get_status(device_id: str):
    """Obtiene el último estado registrado de un dispositivo."""
    try:
        table = dynamodb.Table(STATUS_TABLE_NAME)
        response = table.query(
            KeyConditionExpression=Key("device_id").eq(device_id),
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            print(f"⚠️ No hay estado registrado para {device_id}")
            return None
        print(f"📄 [READ] Último estado: {items[0]}")
        return items[0]
    except Exception as e:
        print(f"❌ Error obteniendo status: {e}")
        return None


# =====================================================
#  get_sensor_data (mejorado con since/until)
# =====================================================
async def get_sensor_data(
    device_id: str,
    limit: int = 50,
    since: str = None,
    until: str = None,
    only_anomalies: bool = False,
    method: str = None,
    field: str = None,
):
    """
    Obtiene lecturas recientes de un dispositivo desde SensorData.
    Soporta filtrado por rango de tiempo y tipo de anomalía.
    """
    try:
        table = dynamodb.Table(DATA_TABLE_NAME)

        #  Condición base por clave primaria
        key_expr = Key("device_id").eq(device_id)

        #  Agregar condiciones de rango directamente en KeyConditionExpression
        if since and until:
            key_expr = key_expr & Key("timestamp").between(since, until)
        elif since:
            key_expr = key_expr & Key("timestamp").gte(since)
        elif until:
            key_expr = key_expr & Key("timestamp").lte(until)

        #  Filtro adicional (solo atributos no clave)
        filter_expr = None

        if only_anomalies:
            anom_expr = (
                Attr("temp_anomaly").eq(True)
                | Attr("hum_anomaly").eq(True)
                | Attr("ml_temp_anomaly").eq(True)
                | Attr("ml_hum_anomaly").eq(True)
            )
            filter_expr = anom_expr

        kwargs = {
            "KeyConditionExpression": key_expr,
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if filter_expr is not None:
            kwargs["FilterExpression"] = filter_expr

        response = table.query(**kwargs)
        items = response.get("Items", [])

        print(
            f"📊 [READ] {len(items)} lecturas de {device_id} "
            f"(rango: {since or 'inicio'} → {until or 'actual'}, anomalies={only_anomalies})"
        )

        #  Convertir Decimals a float
        def convert(v):
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, dict):
                return {k: convert(x) for k, x in v.items()}
            return v

        for item in items:
            for k, v in list(item.items()):
                item[k] = convert(v)

        return items

    except Exception as e:
        print(f"❌ Error leyendo data: {e}")
        return []


# =====================================================
#  Thresholds
# =====================================================
async def get_thresholds(device_id: str):
    """Obtiene los umbrales configurados para un dispositivo."""
    try:
        table = dynamodb.Table(THRESHOLDS_TABLE_NAME)
        res = table.get_item(Key={"device_id": device_id})
        return res.get("Item", {})
    except Exception as e:
        print(f"❌ Error obteniendo umbrales: {e}")
        return {}


async def save_thresholds(device_id: str, limits: dict):
    """Guarda o actualiza los umbrales configurados de un dispositivo."""
    try:
        table = dynamodb.Table(THRESHOLDS_TABLE_NAME)
        item = {
            "device_id": device_id,
            "updated_at": datetime.utcnow().isoformat(),
            "temp_min": Decimal(str(limits.get("temp_min", 0))),
            "temp_max": Decimal(str(limits.get("temp_max", 0))),
            "hum_min": Decimal(str(limits.get("hum_min", 0))),
            "hum_max": Decimal(str(limits.get("hum_max", 0))),
        }
        table.put_item(Item=item)
        print(f"💾 [WRITE] Umbrales guardados para {device_id}: {item}")
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Error guardando umbrales: {e}")
        return {"status": "error", "error": str(e)}


# =====================================================
#  AWS IoT Publish (SDK oficial)
# =====================================================
async def send_command(device_id: str, command: dict):
    """Publica un comando MQTT en AWS IoT Core con mTLS."""
    try:
        if not all([AWS_IOT_ENDPOINT, CERT_PATH, KEY_PATH, ROOT_CA_PATH]):
            raise ValueError("Certificados AWS IoT no configurados correctamente")

        topic = f"{device_id}/commands"
        print(f"📡 Enviando comando a {device_id} → {topic}")
        print(f"📦 Payload: {command}")

        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=AWS_IOT_ENDPOINT,
            cert_filepath=CERT_PATH,
            pri_key_filepath=KEY_PATH,
            ca_filepath=ROOT_CA_PATH,
            client_id=f"fastapi_{device_id}",
            clean_session=False,
            keep_alive_secs=30,
        )

        connect_future = mqtt_connection.connect()
        connect_future.result(timeout=10)
        print(f"✅ Conectado a AWS IoT → publicando en {topic}")

        message = json.dumps(command)
        mqtt_connection.publish(topic=topic, payload=message, qos=mqtt.QoS.AT_LEAST_ONCE)
        print(f"📤 Mensaje publicado en {topic}: {message}")

        mqtt_connection.disconnect()
        print("🔌 Conexión MQTT cerrada correctamente")

        return {"status": "ok", "device_id": device_id, "command": command}

    except Exception as e:
        print(f"❌ Error enviando comando a {device_id}: {e}")
        return {"status": "error", "error": str(e)}
