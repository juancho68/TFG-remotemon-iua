from decimal import Decimal
from typing import Dict, Any

# Modelo para un sensor
def sensor_model(device_id: str, timestamp: str, values: Dict[str, float]) -> Dict[str, Any]:
    # Convierte floats a Decimal para DynamoDB
    values_decimal = {k: Decimal(str(v)) for k, v in values.items()}
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "values": values_decimal
    }

# Modelo para estado digital / status
def status_model(device_id: str, timestamp: str, status: Dict[str, Any]) -> Dict[str, Any]:
    # Convierte floats a Decimal si existen
    status_decimal = {k: Decimal(str(v)) if isinstance(v, float) else v for k, v in status.items()}
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "status": status_decimal
    }
