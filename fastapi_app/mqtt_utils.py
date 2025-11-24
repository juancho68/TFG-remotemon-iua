import json
import ssl
import os
from aiomqtt import Client
import asyncio

AWS_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT")
PORT = 8883

# Coinciden con tus variables en docker-compose
CA_PATH = os.getenv("AWS_ROOT_CA_PATH")
CERT_PATH = os.getenv("AWS_CERT_PATH")
KEY_PATH = os.getenv("AWS_KEY_PATH")

ssl_context = None

print(f"🌐 AWS_IOT_ENDPOINT = {AWS_IOT_ENDPOINT}")
if not AWS_IOT_ENDPOINT:
    print("⚠️ No se configuró el endpoint de AWS IoT (variable AWS_IOT_ENDPOINT vacía)")


if all([CA_PATH, CERT_PATH, KEY_PATH]):
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(CA_PATH)
        ssl_context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
        print(f"✅ Certificados AWS IoT cargados correctamente desde {CA_PATH}")
        
    except Exception as e:
        print(f"❌ Error cargando certificados AWS IoT: {e}")

else:
    print("⚠️ Certificados AWS IoT no configurados correctamente (faltan variables o rutas inválidas)")
    print(f"   AWS_ROOT_CA_PATH={CA_PATH}")
    print(f"   AWS_CERT_PATH={CERT_PATH}")
    print(f"   AWS_KEY_PATH={KEY_PATH}")

async def mqtt_publish_message(topic: str, message: dict):
    """Publica un mensaje JSON a AWS IoT Core."""
    if not ssl_context or not AWS_IOT_ENDPOINT:
        print("❌ Certificados AWS IoT no configurados correctamente, no se puede publicar mensaje")
        return

    try:
        async with Client(
            hostname=AWS_IOT_ENDPOINT,
            port=PORT,
            #ssl=ssl_context
            tls_context=ssl_context,
            keepalive=60
        ) as client:
            payload = json.dumps(message)
            print(f"📡 Conectado a AWS IoT ({AWS_IOT_ENDPOINT}) → publicando en {topic}")
            await client.publish(topic, payload, qos=1)  # QoS asegura entrega
            await asyncio.sleep(0.5)  # 🔹 Espera medio segundo antes de cerrar
            print(f"📤 Mensaje publicado en {topic}: {payload}")
    except Exception as e:
        print(f"❌ Error enviando mensaje a AWS IoT Core: {e}")
