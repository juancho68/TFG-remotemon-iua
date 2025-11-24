from fastapi import APIRouter, Depends, HTTPException, Query
from utils.security import get_current_user
from utils.permissions import require_admin
from utils.dynamodb_setup import dynamodb, ALARM_LOG_TABLE
from boto3.dynamodb.conditions import Key, Attr
from services.alarm_service import set_cooldown_minutes, get_cooldown_minutes
from pydantic import BaseModel
from utils.email_service import send_email

router = APIRouter(prefix="/api", tags=["alarms"])

alarm_table = dynamodb.Table(ALARM_LOG_TABLE)

class CooldownConfig(BaseModel):
    minutes: int


# =====================================================
# Usuario → ver SUS alarmas
# =====================================================
@router.get("/alarms")
def get_user_alarms(
    device_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    user = Depends(get_current_user)
):
    email = user["email"]

    # Query base: Buscar alarmas del usuario
    filter_exp = Attr("user_email").eq(email)

    if device_id:
        filter_exp = filter_exp & Attr("device_id").eq(device_id)

    if since:
        filter_exp = filter_exp & Attr("timestamp").gte(since)

    if until:
        filter_exp = filter_exp & Attr("timestamp").lte(until)

    resp = alarm_table.scan(
        FilterExpression=filter_exp
    )

    alarms = resp.get("Items", [])
    alarms.sort(key=lambda x: x["timestamp"], reverse=True)

    return {"count": len(alarms), "items": alarms}


# =====================================================
# ADMIN → ver TODAS las alarmas
# =====================================================
@router.get("/admin/alarms")
def admin_list_alarms(
    device_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    user = Depends(get_current_user)
):
    require_admin(user)

    filter_exp = None

    if device_id:
        filter_exp = Attr("device_id").eq(device_id)

    if since:
        exp = Attr("timestamp").gte(since)
        filter_exp = exp if filter_exp is None else (filter_exp & exp)

    if until:
        exp = Attr("timestamp").lte(until)
        filter_exp = exp if filter_exp is None else (filter_exp & exp)

    if filter_exp:
        resp = alarm_table.scan(FilterExpression=filter_exp)
    else:
        resp = alarm_table.scan()

    alarms = resp.get("Items", [])
    alarms.sort(key=lambda x: x["timestamp"], reverse=True)

    return {"count": len(alarms), "items": alarms}


# =====================================================
# ADMIN → borra alarmas
# =====================================================
@router.post("/alarms/reset")
def reset_all_alarms(user=Depends(get_current_user)):
    """Elimina todas las alarmas registradas."""
    require_admin(user)

    try:
        from utils.dynamodb_setup import dynamodb, ALARM_LOG_TABLE
        table = dynamodb.Table(ALARM_LOG_TABLE)

        # Escanear todos los registros
        items = table.scan().get("Items", [])

        for item in items:
            table.delete_item(Key={"alarm_id": item["alarm_id"]})

        return {"msg": f"🧹 {len(items)} alarmas eliminadas correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al resetear alarmas: {str(e)}")


# =====================================================
# ADMIN → actualiza minutos COOLDOWN
# =====================================================
@router.post("/alarms/cooldown")
def update_cooldown(cfg: CooldownConfig, user=Depends(get_current_user)):
    """Actualiza el cooldown de alarmas dinámicamente."""
    require_admin(user)

    if cfg.minutes < 0 or cfg.minutes > 1440:
        raise HTTPException(status_code=400, detail="Cooldown inválido (0–1440 min)")

    set_cooldown_minutes(cfg.minutes)

    return {"msg": f"⏱️ Cooldown actualizado a {cfg.minutes} minutos"}


# =====================================================
# ADMIN → testea envío mail
# =====================================================
@router.post("/test_email")
def test_email(to: str):
    try:
        send_email(to, "Test alarm email", "Este es un test desde el backend")
        return {"msg": "Email enviado (si SMTP funciona)"}
    except Exception as e:
        return {"error": str(e)}





# ---------------------------------------------------------
#  GET /api/alarms/cooldown  → obtiene cooldown global
# ---------------------------------------------------------
@router.get("/alarms/cooldown")
def get_cooldown(user=Depends(get_current_user)):
    """Obtiene el cooldown global de alarmas."""
    require_admin(user)

    try:
        minutes = get_cooldown_minutes()
        return {"cooldown": minutes}

    except Exception as e:
        print("❌ Error obteniendo cooldown:", e)
        raise HTTPException(status_code=500, detail="No se pudo obtener el cooldown actual")