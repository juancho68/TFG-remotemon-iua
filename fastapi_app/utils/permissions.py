# utils/permissions.py
from fastapi import HTTPException, status

def check_device_permission(user: dict, device_id: str, permission_key: str):
    """
    Verifica si el usuario tiene permiso para realizar una acción específica en un dispositivo.
    Ejemplo de permission_key: 'led_red', 'led_green'
    """

    # 🔍 Debug
    print(f"🔍 Verificando permisos para {user.get('email')} → {device_id}/{permission_key}")

    # Si el usuario es admin, acceso total
    if user.get("role") == "admin":
        print("✅ Usuario admin, acceso permitido.")
        return True

    devices = user.get("allowed_devices", [])
    print(f"📋 allowed_devices = {devices}")

    # Normalización de claves (acepta led_rojo / led_verde / led_red / led_green)
    key_map = {"led_rojo": "led_red", "led_verde": "led_green"}
    inv_map = {v: k for k, v in key_map.items()}
    possible_keys = {permission_key, inv_map.get(permission_key, permission_key)}

    # Buscar dispositivo
    for d in devices:
        if d.get("device_id") == device_id:
            perms = d.get("permissions", {})
            print(f"🔎 Permisos encontrados: {perms}")

            # Buscar por cualquiera de las claves equivalentes
            for key in possible_keys:
                val = perms.get(key)

                # Si DynamoDB devolvió {"BOOL": True}, lo convertimos
                if isinstance(val, dict) and "BOOL" in val:
                    val = val["BOOL"]

                if val is True:
                    print(f"✅ Permiso concedido: {key} → {val}")
                    return True

    # Si no encontró permisos válidos:
    print(f"⛔ Acceso denegado a {device_id} para {permission_key}")
    raise HTTPException(
        status_code=403,
        detail=f"No tenés permiso para {permission_key} en {device_id}"
    )

def require_permission(user: dict, device_id: str, action: str):
    """
    Lanza una excepción HTTP 403 si el usuario no tiene el permiso requerido.
    """

    if not check_device_permission(user, device_id, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tenés permiso para realizar la acción '{action}' en el dispositivo {device_id}",
        )

def require_admin(user: dict):
    """
    Verifica si el usuario autenticado tiene rol de administrador.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requieren permisos de administrador"
        )