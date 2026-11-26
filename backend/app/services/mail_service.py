import html
import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.core.config import settings

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

def _build_email_html(title: str, greeting: str, content_html: str) -> str:
    return (
        '<div style="background:#f5f8fb;padding:32px 16px;font-family:\'Segoe UI\',Arial,sans-serif;color:#17324d;">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #dde5ed;border-radius:8px;overflow:hidden;">'
        '<div style="background:#be0e01;padding:16px 24px;color:#ffffff;font-size:20px;font-weight:700;letter-spacing:0.3px;">MYSOL</div>'
        '<div style="padding:24px;line-height:1.55;font-size:15px;">'
        f'<h1 style="margin:0 0 12px;font-size:20px;color:#17324d;">{title}</h1>'
        f'<p style="margin:0 0 12px;">{greeting}</p>{content_html}'
        '</div>'
        '<div style="padding:14px 24px;background:#f5f8fb;border-top:1px solid #dde5ed;font-size:12px;color:#52667a;">'
        'University of Calabria &middot; Institutional Mission Portal</div>'
        '</div></div>'
    )


async def send_email(name: str, email: str):
    body = _build_email_html(
        "Registration Confirmed",
        f"Hi {html.escape(name)},",
        '<p style="margin:0;">Your registration on the mySOL Portal has been successfully confirmed. You can now sign in with your institutional credentials.</p>',
    )
    message = MessageSchema(subject="Confirm the registration on mySOL Portal", recipients=[email], body=body, subtype=MessageType.html)
    try:
        await fast_mail.send_message(message)
        logging.log(logging.INFO, "Email sent successfully")
    except Exception as e:
        logging.error(f"Error sending email: {e}")


async def send_password_reset_email(name: str, email: str, token: str):
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    safe_url = html.escape(reset_url, quote=True)
    body = _build_email_html(
        "Password Reset Request",
        f"Hello {html.escape(name)},",
        '<p style="margin:0 0 16px;">We received a request to reset the password for your mySOL account.</p>'
        f'<p style="margin:0 0 20px;"><a href="{safe_url}" style="display:inline-block;padding:11px 22px;background:#be0e01;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;">Reset Password</a></p>'
        f'<p style="margin:0 0 12px;font-size:13px;color:#52667a;">Or copy this link into your browser:<br><a href="{safe_url}" style="color:#be0e01;word-break:break-all;">{safe_url}</a></p>'
        '<p style="margin:0;font-size:13px;color:#52667a;">If you did not request a password reset, you can safely ignore this email.</p>',
    )
    message = MessageSchema(subject="Password Reset - mySOL", recipients=[email], body=body, subtype=MessageType.html)
    try:
        await fast_mail.send_message(message)
        logging.log(logging.INFO, f"Password reset email sent successfully to {email}")
    except Exception as e:
        logging.error(f"Error sending password reset email to {email}: {e}")


