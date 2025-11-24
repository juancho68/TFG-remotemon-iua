#email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def send_email(to_email: str, subject: str, body: str):
    print(f"📨 Preparando mail → {to_email}")
    print(f"🔧 SMTP_SERVER={SMTP_SERVER}, SMTP_PORT={SMTP_PORT}")
    print(f"🔧 SMTP_USER={SMTP_USER}, SMTP_PASS={'SET' if SMTP_PASS else 'EMPTY'}")

    if not SMTP_USER or not SMTP_PASS:
        print("❌ SMTP no configurado correctamente en .env")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            print("🔌 Conectando a SMTP...")
            server.starttls()
            print("🔐 Autenticando...")
            server.login(SMTP_USER, SMTP_PASS)
            print("📤 Enviando correo...")
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"📧 Email enviado a {to_email}")
        return True

    except Exception as e:
        print(f"❌ Error enviando mail a {to_email}: {e}")
        return False
