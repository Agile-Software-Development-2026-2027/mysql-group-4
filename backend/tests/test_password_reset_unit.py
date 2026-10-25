import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi_users import exceptions

from app.core.config import settings
from app.db.models import User
from app.security.user_manager import UserManager
from app.services.mail_service import send_password_reset_email


def make_user():
    return User(id=uuid.uuid4(),  email="antonio@mysol.com",name="Antonio", surname="DAmbrosio", fiscal_code="DMBNTN05C23D086C", department="DEMACS")

@pytest.mark.asyncio
async def test_send_password_reset_email_success():
    with patch("app.services.mail_service.fast_mail.send_message", new_callable=AsyncMock) as mock_send:
        await send_password_reset_email(
            name="Antonio",
            email="antonio@mysol.com",
            token="secure-token-yee",
        )

    mock_send.assert_awaited_once()
    sent_message =  mock_send.call_args[0][0]

    expected_link = settings.FRONTEND_URL  +  "/reset-password?token=secure-token-yee"

    assert "antonio@mysol.com" in str(sent_message.recipients)
    assert sent_message.subject == "Password Reset - mySOL"
    assert "Antonio" in sent_message.body
    assert expected_link in sent_message.body


@pytest.mark.asyncio
async def test_send_password_reset_email_catches_error(caplog):
    with patch( "app.services.mail_service.fast_mail.send_message", new_callable=AsyncMock, side_effect=Exception("SMTP connection failed") ) as  mock_send:
        await send_password_reset_email(name="Antonio", email="antonio@mysol.com", token="secure-token-yee")

    mock_send.assert_awaited_once()
    assert "SMTP connection failed" in caplog.text

@pytest.mark.asyncio
async def test_user_manager_on_after_forgot_password():

    user = make_user()
    user_manager = UserManager( user_db=MagicMock() )

    with patch("app.security.user_manager.send_password_reset_email", new_callable=AsyncMock) as mock_send_email:
        await user_manager.on_after_forgot_password(user, "secure-token-yee")

    mock_send_email.assert_awaited_once_with(name="Antonio", email="antonio@mysol.com", token="secure-token-yee")


@pytest.mark.asyncio
async def test_validate_password_success():
    user = make_user()
    user_manager = UserManager(user_db=MagicMock())

    await user_manager.validate_password("SecureP@ss123", user)

@pytest.mark.asyncio
async def test_validate_password_7_chars_is_too_short():
    user = make_user()
    user_manager = UserManager( user_db=MagicMock() )
    with pytest.raises(exceptions.InvalidPasswordException):
        await user_manager.validate_password("1234567", user)

@pytest.mark.asyncio
async def test_validate_password_empty():
    user = make_user()
    user_manager = UserManager( user_db=MagicMock() )
    with pytest.raises(exceptions.InvalidPasswordException):
        await user_manager.validate_password("", user)

