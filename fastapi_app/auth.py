
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from pydantic import BaseModel, EmailStr, Field
from boto3.dynamodb.conditions import Key
from utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from utils.dynamodb_setup import dynamodb, USERS_TABLE_NAME
from fastapi.responses import JSONResponse
from urllib.parse import parse_qs
from typing import Optional
import uuid

# =====================================================
#  Configuración inicial
# =====================================================

router = APIRouter(prefix="/api", tags=["auth"])
users_table = dynamodb.Table(USERS_TABLE_NAME)

# =====================================================
#  MODELOS Pydantic
# =====================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=3)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# =====================================================
#  REGISTRO DE USUARIO
# =====================================================

@router.post("/register")
def register(req: RegisterRequest):
    """Registra un nuevo usuario."""
    email = req.email.lower()
    password = req.password

    # Verificar si ya existe
    response = users_table.query(KeyConditionExpression=Key("email").eq(email))
    if response.get("Items"):
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    hashed = hash_password(password)
    user_id = str(uuid.uuid4())

    # Crear usuario sin dispositivos asignados aún
    users_table.put_item(Item={
        "user_id": user_id,
        "email": email,
        "password_hash": hashed,
        "role": "user",
        "notify_email": False,
        "notify_temp": True,
        "notify_hum": True,
        "allowed_devices": []
    })

    print(f"🧩 Nuevo usuario registrado: {email}")
    return {"message": f"✅ Usuario {email} registrado correctamente"}

# =====================================================
#  LOGIN
# =====================================================

@router.post("/login")
async def login(request: Request):
    """Inicia sesión con JSON o con formulario."""
    try:
        content_type = request.headers.get("content-type", "")
        email = password = None

        # 🟢 JSON
        if "application/json" in content_type:
            data = await request.json()
            email = data.get("email")
            password = data.get("password")

        # 🔵 Form-urlencoded (Swagger)
        elif "application/x-www-form-urlencoded" in content_type:
            body = await request.body()
            form = parse_qs(body.decode())
            email = form.get("username", [None])[0] or form.get("email", [None])[0]
            password = form.get("password", [None])[0]

        if not email or not password:
            raise HTTPException(status_code=400, detail="Faltan credenciales")

        email = email.lower()
        response = users_table.query(KeyConditionExpression=Key("email").eq(email))
        items = response.get("Items", [])
        if not items:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")

        user = items[0]
        if not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")

        token = create_access_token({"sub": user["email"]})
        print(f"🔐 Usuario autenticado: {user['email']}")

        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "email": user["email"],
            "role": user.get("role", "user")
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en login: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# =====================================================
#  PERFIL DEL USUARIO AUTENTICADO (mejorado)
# =====================================================

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    """
    Devuelve la información completa del usuario autenticado:
    - email, role, user_id
    - allowed_devices con permisos
    - thresholds (umbrales) por dispositivo
    """
    try:
        # Buscar usuario actualizado
        response = users_table.query(KeyConditionExpression=Key("email").eq(user["email"]))
        items = response.get("Items", [])
        if not items:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_item = items[0]

        allowed_devices = user_item.get("allowed_devices", [])

        # Asegurar estructura completa
        for dev in allowed_devices:
            dev.setdefault("permissions", {
                "read_data": False,
                "write_data": False,
                "led_red": False,
                "led_green": False
            })
            dev.setdefault("thresholds", {
                "temp_min": None,
                "temp_max": None,
                "hum_min": None,
                "hum_max": None
            })

        return {
            "email": user_item.get("email"),
            "role": user_item.get("role", "user"),
            "user_id": user_item.get("user_id"),
            "allowed_devices": allowed_devices
        }

    except Exception as e:
        print(f"❌ Error al obtener perfil: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener perfil: {str(e)}")

# =====================================================
#  CREAR ADMIN TEMPORAL
# =====================================================

@router.post("/create_admin")
def create_admin(email: str, password: str):
    """
    ⚠️ Endpoint temporal para crear el primer usuario admin.
    """
    email = email.lower()
    response = users_table.query(KeyConditionExpression=Key("email").eq(email))
    if response.get("Items"):
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    users_table.put_item(Item={
        "user_id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "notify_email": False,
        "notify_temp": True,
        "notify_hum": True,
        "allowed_devices": []
    })

    print(f"👑 Usuario admin creado: {email}")
    return {"msg": f"✅ Usuario admin {email} creado correctamente"}
