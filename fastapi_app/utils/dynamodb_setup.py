
########

import os
import boto3

# =====================================================
# Configuración base DynamoDB
# =====================================================
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT")  # vacío = AWS real

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=DYNAMODB_ENDPOINT)
client = boto3.client("dynamodb", region_name=AWS_REGION, endpoint_url=DYNAMODB_ENDPOINT)

# Nombres de tablas
USERS_TABLE_NAME = os.getenv("USERS_TABLE_NAME", "Users")
DATA_TABLE_NAME = os.getenv("DATA_TABLE_NAME", "SensorData")
STATUS_TABLE_NAME = os.getenv("STATUS_TABLE_NAME", "DeviceStatus")
THRESHOLDS_TABLE_NAME = os.getenv("THRESHOLDS_TABLE_NAME", "Thresholds")
ALARM_LOG_TABLE = os.getenv("ALARM_LOG_TABLE", "AlarmLog")

# =====================================================
#  Helper para crear tablas
# =====================================================
def ensure_table_exists(table_name: str, key_schema, attr_definitions):
    """Crea una tabla si no existe."""
    existing_tables = [t.name for t in dynamodb.tables.all()]
    if table_name not in existing_tables:
        print(f"🧱 Creando tabla '{table_name}'...")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attr_definitions,
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"✅ Tabla '{table_name}' creada correctamente.")
    else:
        print(f"ℹ️ Tabla '{table_name}' ya existe.")

# =====================================================
#  Users
# =====================================================
def ensure_users_table_exists():
    ensure_table_exists(
        USERS_TABLE_NAME,
        key_schema=[{"AttributeName": "email", "KeyType": "HASH"}],
        attr_definitions=[{"AttributeName": "email", "AttributeType": "S"}],
    )

# =====================================================
#  SensorData
# =====================================================
def ensure_sensor_data_table_exists():
    ensure_table_exists(
        DATA_TABLE_NAME,
        key_schema=[
            {"AttributeName": "device_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        attr_definitions=[
            {"AttributeName": "device_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
    )

# =====================================================
#  DeviceStatus
# =====================================================
def ensure_status_table_exists():
    ensure_table_exists(
        STATUS_TABLE_NAME,
        key_schema=[
            {"AttributeName": "device_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        attr_definitions=[
            {"AttributeName": "device_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
    )

# =====================================================
#  Thresholds
# =====================================================
def ensure_thresholds_table_exists():
    ensure_table_exists(
        THRESHOLDS_TABLE_NAME,
        key_schema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
        attr_definitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
    )

# =====================================================
#  AlarmLog
# =====================================================
def ensure_alarm_log_table_exists():
    """
    Tabla para registrar alarmas enviadas al usuario.
    Clave primaria: alarm_id (UUID)
    """
    ensure_table_exists(
        ALARM_LOG_TABLE,
        key_schema=[{"AttributeName": "alarm_id", "KeyType": "HASH"}],
        attr_definitions=[{"AttributeName": "alarm_id", "AttributeType": "S"}],
    )

# =====================================================
#  Inicialización global
# =====================================================
def ensure_all_tables_exist():
    print("🔍 Verificando tablas DynamoDB...")

    ensure_users_table_exists()
    ensure_sensor_data_table_exists()
    ensure_status_table_exists()
    ensure_thresholds_table_exists()
    ensure_alarm_log_table_exists()

    print("✅ Todas las tablas están disponibles.")

# =====================================================
#  Tablas accesibles desde otros módulos
# =====================================================
users_table = dynamodb.Table(USERS_TABLE_NAME)
sensor_table = dynamodb.Table(DATA_TABLE_NAME)
status_table = dynamodb.Table(STATUS_TABLE_NAME)
thresholds_table = dynamodb.Table(THRESHOLDS_TABLE_NAME)
alarm_log_table = dynamodb.Table(ALARM_LOG_TABLE)

# =====================================================
#  Ejecución automática al iniciar contenedor
# =====================================================
try:
    ensure_all_tables_exist()
except Exception as e:
    print(f"⚠️ Error verificando tablas DynamoDB: {e}")
