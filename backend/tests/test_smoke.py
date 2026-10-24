from httpx import AsyncClient


async def test_greeting(client: AsyncClient):
    response = await client.get("/api/v1/")  # chiama il nostro endpoint che restituisce Hello World
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


async def test_me_requires_login(client: AsyncClient):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401