from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.currency_service import CurrencyConversionService


@pytest.mark.asyncio
async def test_resolve_currency_for_destination_via_nominatim():
    service = CurrencyConversionService()

    with patch(
        "app.services.currency_service.search_locations",
        new=AsyncMock(return_value=[{"display_name": "Ulan-Ude, Russia", "address": {"country_code": "ru"}}]),
    ):
        assert await service.resolve_currency_for_destination("Ulan-Ude, Russia") == "RUB"

    with patch(
        "app.services.currency_service.search_locations",
        new=AsyncMock(return_value=[{"display_name": "Università di Padova, Italia", "address": {"country_code": "it"}}]),
    ):
        assert await service.resolve_currency_for_destination("Università di Padova") == "EUR"

    with patch(
        "app.services.currency_service.search_locations",
        new=AsyncMock(return_value=[{"display_name": "Taipei, Taiwan", "address": {"country_code": "tw"}}]),
    ):
        assert await service.resolve_currency_for_destination("Taipei") == "TWD"

    assert await service.resolve_currency_for_destination(None) == "EUR"


@pytest.mark.asyncio
async def test_currency_conversion_eur_noop():
    service = CurrencyConversionService()
    res = await service.convert_to_eur(Decimal("120.50"), "EUR")
    assert res is not None
    assert res.original_currency == "EUR"
    assert res.converted_amount == Decimal("120.50")
    assert res.rate == Decimal("1.0")
    assert res.provider == "None (already EUR)"


@pytest.mark.asyncio
async def test_currency_conversion_frankfurter():
    service = CurrencyConversionService()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"amount": 1.0, "base": "USD", "date": "2026-11-14", "rates": {"EUR": 0.92}}

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await service.convert_to_eur(Decimal("100.00"), "USD")
        assert res is not None
        assert res.original_currency == "USD"
        assert res.converted_amount == Decimal("92.00")
        assert res.rate == Decimal("0.92")
        assert res.provider == "Frankfurter API"


@pytest.mark.asyncio
async def test_currency_conversion_aed_peg_fallback():
    service = CurrencyConversionService()
    resp_404 = MagicMock(status_code=404)
    resp_usd = MagicMock(
        status_code=200,
        json=lambda: {"amount": 1.0, "base": "USD", "date": "2026-11-14", "rates": {"EUR": 0.92}},
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[resp_404, resp_usd])):
        res = await service.convert_to_eur(Decimal("367.25"), "AED")
        assert res is not None
        assert res.original_currency == "AED"
        assert res.converted_amount == Decimal("92.00")
        assert "USD peg" in res.provider


@pytest.mark.asyncio
async def test_currency_conversion_open_er_fallback():
    service = CurrencyConversionService()
    resp_404 = MagicMock(status_code=404)
    resp_er = MagicMock(
        status_code=200,
        json=lambda: {"rates": {"EUR": 0.011}, "time_last_update_utc": "Sat, 14 Nov 2026"},
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[resp_404, resp_er])):
        res = await service.convert_to_eur(Decimal("420.00"), "RUB")
        assert res is not None
        assert res.original_currency == "RUB"
        assert res.converted_amount == Decimal("4.62")
        assert res.provider == "Open Exchange Rates API"
