# services/device_user_cache.py
from utils.dynamodb_setup import users_table
from typing import Dict, List
import threading

# Cache global: device_id → lista de usuarios completos
device_user_cache: Dict[str, List[dict]] = {}
lock = threading.Lock()


# ============================================================
#   Construcción inicial del cache
# ============================================================
def build_device_user_cache():
    """
    Construye el cache completo desde DynamoDB.
    Cada entrada contiene al usuario completo,
    incluyendo allowed_devices con permissions, thresholds y notifications.
    """
    global device_user_cache

    print("🔄 Construyendo device_user_cache...")

    users = users_table.scan().get("Items", [])
    new_cache = {}

    for user in users:
        allowed_devices = user.get("allowed_devices", [])

        for dev in allowed_devices:
            device_id = dev.get("device_id")
            if not device_id:
                continue

            # agregar usuario a ese device
            new_cache.setdefault(device_id, []).append(user)

    # actualizar cache global
    with lock:
        device_user_cache = new_cache

    print(f"✅ Cache armado: {len(device_user_cache)} dispositivos cargados.")


# ============================================================
#   Obtener usuarios asignados a un device
# ============================================================
def get_users_for_device(device_id: str) -> List[dict]:
    """
    Devuelve lista de usuarios asignados a ese dispositivo.
    Cada usuario incluye:
      · allowed_devices (con permissions, thresholds, notifications)
      · role
      · email
    """
    return device_user_cache.get(device_id, [])


# ============================================================
#   Refrescar un usuario puntual (cuando se edita en Admin)
# ============================================================
def refresh_user_entry(user: dict):
    """
    Actualiza SOLO a este usuario dentro del cache,
    sin tener que reconstruirlo todo.
    
    Espera un dict con al menos:
        {
          "email": "...",
          "allowed_devices": [ ... estructura completa ... ]
        }
    """
    global device_user_cache

    email = user.get("email")
    if not email:
        print("❌ refresh_user_entry fue llamado sin email")
        return

    with lock:
        # borrar usuario viejo en todas las listas
        for dev_list in device_user_cache.values():
            dev_list[:] = [u for u in dev_list if u.get("email") != email]

        # agregar usuario en cada device permitido
        for dev in user.get("allowed_devices", []):
            dev_id = dev.get("device_id")
            if not dev_id:
                continue

            device_user_cache.setdefault(dev_id, []).append(user)

    print(f"♻️ Cache actualizado para {email}")
