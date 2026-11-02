
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EmploymentLevel
from app.db.models import User
from app.security import current_active_user
from main import app


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_pwd",
        name="Mario",
        surname="Rossi",
        fiscal_code="RSSMRA80A01H501U",
        department="DIMES",
        employment_level=EmploymentLevel.RICERCATORE,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    app.dependency_overrides[current_active_user] = lambda: user
    yield user
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_profile_success(client: AsyncClient, sample_user: User):
    response = await client.patch("/api/v1/me", json={"name": "Luigi", "department": "DICES"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Luigi"
    assert data["department"] == "DICES"


@pytest.mark.asyncio
async def test_update_profile_unauthorized(client: AsyncClient):
    app.dependency_overrides.clear()
    response = await client.patch("/api/v1/me", json={"name": "Luigi"})
    assert response.status_code == 401
