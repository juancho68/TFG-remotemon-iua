
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from boto3.dynamodb.conditions import Key
import os

# Importar conexión centralizada
from utils.dynamodb_setup import dynamodb, USERS_TABLE_NAME

# =====================================================
#  CONFIGURACIÓN GENERAL
# =====================================================
SECRET_KEY = os.getenv("JWT_SECRET", "supersecreto123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# FastAPI - esquema OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# Contexto de encriptación (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tabla de usuarios
users_table = dynamodb.Table(USERS_TABLE_NAME)

# =====================================================
#  UTILIDADES DE CONTRASEÑA
# =====================================================
def get_password_hash(password: str) -> str:
    """
    Encripta una contraseña usando bcrypt (alias compatible con otros módulos).
    Llama internamente a hash_password() para mantener compatibilidad.
    """
    return pwd_context.hash(password[:72])

def hash_password(password: str) -> str:
    """Encripta una contraseña usando bcrypt (máx 72 caracteres)."""
    return pwd_context.hash(password[:72])

def verify_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña con su hash."""
    return pwd_context.verify(plain[:72], hashed)

# =====================================================
#  TOKENS JWT
# =====================================================
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Crea un JWT con expiración."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =====================================================
#  AUTENTICACIÓN / AUTORIZACIÓN
# =====================================================
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtiene y valida el usuario actual a partir del token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        #  Decodificar token JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception

        #  Buscar usuario en DynamoDB
        response = users_table.query(KeyConditionExpression=Key("email").eq(email))
        items = response.get("Items", [])
        if not items:
            raise credentials_exception

        user = items[0]
        print(f"✅ Usuario autenticado: {user.get('email')}")
        return user

    except JWTError:
        raise credentials_exception
    except Exception as e:
        print(f"❌ Error en get_current_user(): {e}")
        raise credentials_exception
