from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

fast_mail = FastMail(conf)

async def send_email(name: str, email: str):
    body = f"""
    <h1>Ciao {name} </h1>
    <p>La tua registrazione è andata a buon fine.</p>
    """
    message = MessageSchema(
        subject="Conferma registrazione sul portale mySOL",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    try:
        await fast_mail.send_message(message)
        logging.log(logging.INFO,"Email sent successfully")
    except Exception as e:
        logging.error(f"Error sending email: {e}")

