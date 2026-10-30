import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

@pytest.mark.asyncio
@patch("app.services.geocoding.httpx.AsyncClient")
async def test_autocomplete_success(mock_httpx_cls, client: AsyncClient):
    fake_nominatim_data=[{"display_name": "Università della Calabria, Rende, Cosenza", "lat": "39.3621", "lon": "16.2260", "type": "university", "address": {"city": "Rende", "country": "Italia"}}]

    #mock sincrono per la risposta HTTP
    mock_response=MagicMock()
    mock_response.status_code=200
    mock_response.json.return_value=fake_nominatim_data
    mock_response.raise_for_status=MagicMock()

    #mock asincrono per il client HTTP interno a geocoding.py
    mock_client_instance=AsyncMock()
    mock_client_instance.get.return_value=mock_response
    mock_httpx_cls.return_value.__aenter__.return_value=mock_client_instance

    response=await client.get("/api/v1/locations/autocomplete?q=Calabria")
    assert response.status_code==200
    data=response.json()
    assert len(data)==1
    assert data[0]["display_name"]=="Università della Calabria, Rende, Cosenza"
    assert data[0]["lat"]=="39.3621"

#verifica che query con meno di 3 caratteri vengano bloccate da FastAPI senza invocare la rete
@pytest.mark.asyncio
async def test_autocomplete_query_too_short(client: AsyncClient):
    response=await client.get("/api/v1/locations/autocomplete?q=Un")
    assert response.status_code==422

#verifica che se il servizio esterno fallisce o va in timeout, il backend restituisce un 502 Bad Gateway
@pytest.mark.asyncio
@patch("app.services.geocoding.httpx.AsyncClient")
async def test_autocomplete_service_error(mock_httpx_cls, client: AsyncClient):
    mock_client_instance=AsyncMock()
    mock_client_instance.get.side_effect=Exception("Network error")
    mock_httpx_cls.return_value.__aenter__.return_value=mock_client_instance
    response=await client.get("/api/v1/locations/autocomplete?q=Università")
    assert response.status_code==502
    assert(response.json()["detail"]=="Service currently not available.")