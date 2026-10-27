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
    <h1>Hi {name} </h1>
    <p>Your registration on the mySOL Portal has been successfully confirmed.</p>
    """
    message = MessageSchema(
        subject="Confirm the registration on mySOL Portal",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    try:
        await fast_mail.send_message(message)
        logging.log(logging.INFO,"Email sent successfully")
    except Exception as e:
        logging.error(f"Error sending email: {e}")


async def send_password_reset_email(name: str, email: str, token: str):
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    body = f"""
    <h1>Password Reset Request</h1>
    <p>Hello {name},</p>
    <p>We received a request to reset the password for your mySOL account.</p>
    <p>Click the link below to reset your password:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>If you did not request a password reset, you can safely ignore this email.</p>
    """
    message = MessageSchema(
        subject="Password Reset - mySOL",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    try:
        await fast_mail.send_message(message)
        logging.log(logging.INFO, f"Password reset email sent successfully to {email}")
    except Exception as e:
        logging.error(f"Error sending password reset email to {email}: {e}")


