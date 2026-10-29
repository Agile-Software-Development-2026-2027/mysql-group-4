import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi_users import exceptions
from httpx import AsyncClient

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

# API Integration Tests

@pytest.mark.asyncio
async def test_password_reset_api_flow(client: AsyncClient):
    # 1. Register a user
    user_data = {
        "email": "antonio@mysol.com",
        "password": "InitialPassword123!",
        "name": "Antonio",
        "surname": "DAmbrosio",
        "fiscal_code": "DMBNTN05C23D086C",
        "department": "DEMACS",
        "employment_level": "ricercatore",
    }
    with patch("app.security.user_manager.send_email", new_callable=AsyncMock):
        reg_response = await client.post("/auth/register", json=user_data)
        assert reg_response.status_code == 201

    # 2. Request forgot-password via API and intercept sent email
    with patch("app.services.mail_service.fast_mail.send_message", new_callable=AsyncMock) as mock_send:
        fp_response = await client.post("/auth/forgot-password", json={"email": user_data["email"]})
        assert fp_response.status_code == 202
        mock_send.assert_awaited_once()

    sent_message = mock_send.call_args[0][0]
    expected_link_prefix = f"{settings.FRONTEND_URL}/reset-password?token="
    assert expected_link_prefix in sent_message.body

    match = re.search(
        rf"{re.escape(settings.FRONTEND_URL)}/reset-password\?token=([a-zA-Z0-9_\.\-]+)",
        sent_message.body,
    )
    assert match is not None
    token = match.group(1)

    # 3. Reset password via API with the extracted token
    new_password = "NewSecurePassword123!"
    reset_response = await client.post(
        "/auth/reset-password",
        json={"token": token, "password": new_password},
    )
    assert reset_response.status_code == 200

    # 4. Verify login succeeds with the new password
    login_new = await client.post(
        "/auth/jwt/login",
        data={"username": user_data["email"], "password": new_password},
    )
    assert login_new.status_code == 204
    assert "auth_token" in login_new.cookies


@pytest.mark.asyncio
async def test_reset_password_api_invalid_token(client: AsyncClient):
    response = await client.post( "/auth/reset-password", json={"token": "invalid.jwt.token", "password": "NewSecurePassword123!"}, )
    assert response.status_code == 400
    assert response.json()["detail"] == "RESET_PASSWORD_BAD_TOKEN"
