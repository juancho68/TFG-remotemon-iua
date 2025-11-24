
from fastapi import APIRouter, Depends, HTTPException
from utils.security import get_current_user, get_password_hash
from utils.permissions import require_admin
from utils.dynamodb_setup import dynamodb, USERS_TABLE_NAME
from typing import List, Optional
from pydantic import BaseModel
from services.device_user_cache import refresh_user_entry

router = APIRouter(prefix="/api/admin", tags=["admin"])

users_table = dynamodb.Table(USERS_TABLE_NAME)

# ---------------------------------------------------------
# MODELOS
# ---------------------------------------------------------

class Permissions(BaseModel):
    read_data: bool = False
    write_data: bool = False
    led_green: bool = False
    led_red: bool = False


class Notifications(BaseModel):
    email: bool = False
    temp: bool = True
    hum: bool = True


class DevicePermission(BaseModel):
    device_id: str
    permissions: Permissions
    notifications: Notifications
    thresholds: Optional[dict] = None


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "user"


# ---------------------------------------------------------
# LISTAR USUARIOS
# ---------------------------------------------------------
@router.get("/users")
def list_users(user=Depends(get_current_user)):
    require_admin(user)
    return {"users": users_table.scan().get("Items", [])}


# ---------------------------------------------------------
#  Eliminar usuario
# ---------------------------------------------------------
@router.delete("/users/{email}")
def delete_user(email: str, user=Depends(get_current_user)):
    """Elimina un usuario completamente (solo admin)."""
    require_admin(user)

    # Buscar usuario
    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": email}
    )
    items = resp.get("Items", [])

    if not items:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_item = items[0]

    # Detectar clave primaria
    table_key = users_table.key_schema[0]["AttributeName"]
    key_value = user_item[table_key]

    # Eliminar
    users_table.delete_item(Key={table_key: key_value})

    # ❗ Sacarlo del cache device_user_cache
    refresh_user_entry({
        "email": email,
        "allowed_devices": []   # vaciamos los devices para asegurarnos que se elimine
    })

    return {"msg": f"🗑️ Usuario {email} eliminado correctamente"}


# ---------------------------------------------------------
# OBTENER PERMISOS DE UN USUARIO
# ---------------------------------------------------------
@router.get("/users/{email}/permissions")
def get_user_permissions(email: str, user=Depends(get_current_user)):
    require_admin(user)

    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": email}
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return items[0].get("allowed_devices", [])


# ---------------------------------------------------------
# ACTUALIZAR PERMISOS DE UN USUARIO
# ---------------------------------------------------------
@router.put("/users/{email}/permissions")
def update_user_permissions(email: str, new_permissions: List[DevicePermission], user=Depends(get_current_user)):
    require_admin(user)

    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": email}
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_item = items[0]

    # Convertir Pydantic → dict
    perms_list = []
    for p in new_permissions:
        d = p.dict()

        # Garantizar thresholds
        d.setdefault("thresholds", {
            "temp_min": None,
            "temp_max": None,
            "hum_min": None,
            "hum_max": None
        })

        perms_list.append(d)

    # Detectar clave primaria
    table_key = users_table.key_schema[0]["AttributeName"]
    key_value = user_item[table_key]

    # Guardar en DynamoDB
    users_table.update_item(
        Key={table_key: key_value},
        UpdateExpression="SET allowed_devices = :p",
        ExpressionAttributeValues={":p": perms_list}
    )

    # Refrescar cache
    refresh_user_entry({
        "email": user_item["email"],
        "allowed_devices": perms_list
    })

    return {"msg": f"✅ Permisos actualizados para {email}"}


# ---------------------------------------------------------
# Crear usuario 
# ---------------------------------------------------------
@router.post("/users")
def create_user(data: UserCreate, user=Depends(get_current_user)):
    require_admin(user)

    # Verificar si existe
    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": data.email}
    )
    if resp.get("Items"):
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    # 🔍 Obtener lista de dispositivos desde DeviceStatus
    try:
        devices_table = dynamodb.Table("DeviceStatus")
        devices_scan = devices_table.scan().get("Items", [])
    except Exception as e:
        print(f"⚠️ No se pudo leer DeviceStatus: {e}")
        devices_scan = []

    allowed_list = []
    seen = set()

    for d in devices_scan:
        dev_id = (
            d.get("device_id") or
            d.get("id") or
            d.get("name") or
            None
        )
        if not dev_id or dev_id in seen:
            continue
        seen.add(dev_id)

        allowed_list.append({
            "device_id": dev_id,
            "permissions": {
                "read_data": False,
                "write_data": False,
                "led_green": False,
                "led_red": False
            },
            "notifications": {
                "email": False,
                "temp": True,
                "hum": True
            },
            "thresholds": {
                "temp_min": None,
                "temp_max": None,
                "hum_min": None,
                "hum_max": None
            }
        })

    # Crear usuario final
    new_user_item = {
        "email": data.email,
        "password_hash": get_password_hash(data.password),
        "role": data.role,
        "is_verified": True,
        "allowed_devices": allowed_list
    }

    users_table.put_item(Item=new_user_item)

    # 🔄 Refrescar cache
    refresh_user_entry({
        "email": data.email,
        "allowed_devices": allowed_list
    })

    return {"message": f"✅ Usuario {data.email} creado exitosamente"}


# ---------------------------------------------------------
# OBTENER UMBRALES
# ---------------------------------------------------------
@router.get("/users/{email}/thresholds/{device_id}")
def get_user_thresholds(email: str, device_id: str, user=Depends(get_current_user)):
    require_admin(user)

    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": email}
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    for dev in items[0].get("allowed_devices", []):
        if dev["device_id"] == device_id:
            return dev.get("thresholds", {})

    raise HTTPException(status_code=404, detail="Dispositivo no asignado al usuario")


# ---------------------------------------------------------
# ACTUALIZAR UMBRALES
# ---------------------------------------------------------
@router.put("/users/{email}/thresholds/{device_id}")
def update_user_thresholds(email: str, device_id: str, thresholds: dict, user=Depends(get_current_user)):
    require_admin(user)

    resp = users_table.scan(
        FilterExpression="email = :email",
        ExpressionAttributeValues={":email": email}
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_item = items[0]
    allowed = user_item.get("allowed_devices", [])

    found = False
    for dev in allowed:
        if dev["device_id"] == device_id:
            dev["thresholds"] = thresholds
            found = True
            break

    if not found:
        allowed.append({
            "device_id": device_id,
            "permissions": {
                "read_data": False,
                "write_data": False,
                "led_green": False,
                "led_red": False
            },
            "notifications": {
                "email": False,
                "temp": True,
                "hum": True
            },
            "thresholds": thresholds
        })

    # Guardar en DB
    table_key = users_table.key_schema[0]["AttributeName"]
    key_value = user_item[table_key]

    users_table.update_item(
        Key={table_key: key_value},
        UpdateExpression="SET allowed_devices = :d",
        ExpressionAttributeValues={":d": allowed}
    )

    # Cache
    refresh_user_entry({
        "email": user_item["email"],
        "allowed_devices": allowed
    })

    return {"msg": f"✅ Umbrales actualizados para {email} → {device_id}"}

# ---------------------------------------------------------
# Obtener notificaciones por usuario/dispositivo
# ---------------------------------------------------------
@router.get("/users/{email}/notifications/{device_id}")
def get_user_notifications(email: str, device_id: str, user=Depends(get_current_user)):
    require_admin(user)

    users_table = dynamodb.Table(USERS_TABLE_NAME)
    res = users_table.get_item(Key={"email": email})

    if "Item" not in res:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    allowed_devices = res["Item"].get("allowed_devices", [])

    for dev in allowed_devices:
        if dev.get("device_id") == device_id:
            return dev.get("notifications", {})

    raise HTTPException(status_code=404, detail="Dispositivo sin config de notificaciones")

# ---------------------------------------------------------
# Actualizar config notificaciones
# ---------------------------------------------------------
@router.put("/users/{email}/notifications/{device_id}")
def update_user_notifications(email: str, device_id: str, payload: dict, user=Depends(get_current_user)):
    require_admin(user)

    users_table = dynamodb.Table(USERS_TABLE_NAME)
    res = users_table.get_item(Key={"email": email})

    if "Item" not in res:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    item = res["Item"]
    allowed_devices = item.get("allowed_devices", [])

    found = False
    for dev in allowed_devices:
        if dev.get("device_id") == device_id:
            dev.setdefault("notifications", {})
            dev["notifications"].update(payload)
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Dispositivo no asociado a usuario")

    users_table.put_item(Item=item)

    return {"msg": "Notificaciones actualizadas correctamente"}


#################
@router.get("/debug/cache")
def debug_cache():
    from services.device_user_cache import device_user_cache
    return device_user_cache

#############
@router.post("/debug/rebuild_cache")
def rebuild_cache():
    from services.device_user_cache import build_device_user_cache
    build_device_user_cache()
    return {"msg": "cache rebuilt"}