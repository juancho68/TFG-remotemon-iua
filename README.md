# RemoteMon – Backend + Frontend  
Sistema IoT de Monitoreo en Tiempo Real con ESP32 · AWS IoT Core · FastAPI · DynamoDB · Chart.js

---

## 📡 Descripción General

RemoteMon es un sistema completo de monitoreo IoT en tiempo real que integra:

- **Backend** en FastAPI  
- **Frontend** en HTML/JS/CSS  
- **AWS IoT Core** para comunicación MQTT segura  
- **DynamoDB** (Local o AWS) como base NoSQL  
- **Machine Learning** (Isolation Forest + EWMA)  
- **WebSockets** para transmisión instantánea al dashboard  

Permite monitorear dispositivos ESP32, controlar LEDs, configurar umbrales, detectar anomalías, gestionar alarmas y administrar usuarios y permisos.


```
iot_backend/
│
├── certs/
│   ├── AmazonRootCA1.perm
│   ├── AmazonRootCA3.perm
│   ├── deviceCert.pem.crt
│   ├── private.pem.key
│   └── public.pem.key
│
├── fastapi_app/
│   ├── main.py
│   ├── db.py
│   ├── auth.py
│   ├── iot_mqtt.py
│   ├── mqtt_utils.py  
│   ├── models.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routes/
│   │   ├── admin.py
│   │   ├── alarms.py
│   │   └── devices.py
│   ├── services/
│   │   ├── alarm_service.py
│   │   └── device_user_cache.py
│   └── utils/
│       ├── dynamodb_setup.py
│       ├── email_service.py
│       ├── ml_utils.py
│       ├── permissions.py
│       ├── security.py
│       └── ws_manager.py
│    
├── frontend/
│   ├── css/
│   │   ├── admin.css
│   │   ├── alarms.css
│   │   ├── auth.css
│   │   ├── charts.css
│   │   ├── dashboard.css
│   │   ├── thresholds.css
│   │   └── style.css
│   ├── img/
│   │   ├── favicon_64x64.png
│   │   ├── favicon.ico
│   │   └── RemoteMon.png
│   ├── js/
│   │   ├── admin.js
│   │   ├── alarms.js
│   │   ├── auth.js
│   │   ├── charts.js
│   │   ├── common.js
│   │   ├── config.js
│   │   ├── dashboard.js
│   │   ├── nav-active.js
│   │   ├── thresholds.js
│   │   ├── utils.js
│   │   └── ws_client.js
│   │
│   ├── admin.html
│   ├── alarms.html
│   ├── charts.html
│   ├── dashboard.html
│   ├── index.html
│   ├── thresholds.html
│   └── history.html
│
├── .env
├── docker-compose.yml
├── README.md
└── dynamodb_data/                # Volumen persistente
```

## 🔧 ESP32

- Certificados X.509  
- Publicación de:
  - temperatura  
  - humedad  
  - estados digitales  
- Interrupción para manejo del botón  
- Mensajes MQTT a AWS IoT Core

---

## 🧪 Modo Desarrollo

- AWS IoT Core  
- Backend+Frontend local (Docker)  
- DynamoDB Local (Docker)  
- ESP32 real o simulador  

---

## 🚀 Modo Producción

- AWS IoT Core  
- DynamoDB AWS  
- Backend en EC2/ECS  
- Certificados únicos por dispositivo  
- Monitoreo CloudWatch  

---

## 📞 Contacto

Juan L. Scardino  
jlscardino.dev@gmail.com

Proyecto RemoteMon - 2025





