import uuid
import pytest
from httpx import AsyncClient
from main import app
from app.security import current_active_user
from app.db.models import User

@pytest.fixture
def mock_active_user():
    mock_user=User(id=uuid.uuid4(), email="fundmanager@example.com",is_active=True)
    app.dependency_overrides[current_active_user]=lambda: mock_user
    yield mock_user
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_fund_managers_success(client: AsyncClient, mock_active_user):
    response=await client.get("/api/v1/users/fund-managers")
    assert response.status_code==200
    data=response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_fund_managers_unauthorized(client: AsyncClient):
    app.dependency_overrides.clear()
    response=await client.get("/api/v1/users/fund-managers")
    assert response.status_code==401