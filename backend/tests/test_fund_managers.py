import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_fund_managers_success(client: AsyncClient):
    response=await client.get("/api/v1/users/fund-managers")
    assert response.status_code==200
    data=response.json()
    assert isinstance(data, list)