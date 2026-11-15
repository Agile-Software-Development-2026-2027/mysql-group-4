import logging
from decimal import Decimal
import httpx

from app.schemas.currency import CurrencyConversionDTO
from app.services.geocoding import search_locations

logger = logging.getLogger(__name__)

AED_USD_PEG = Decimal("3.6725")

# ISO 3166-1 alpha-2 country code -> ISO 4217 currency code
COUNTRY_CODE_TO_CURRENCY: dict[str, str] = {
    # Eurozone
    "AD": "EUR", "AT": "EUR", "BE": "EUR", "CY": "EUR", "DE": "EUR", "EE": "EUR",
    "ES": "EUR", "FI": "EUR", "FR": "EUR", "GR": "EUR", "HR": "EUR", "IE": "EUR",
    "IT": "EUR", "LT": "EUR", "LU": "EUR", "LV": "EUR", "MC": "EUR", "ME": "EUR",
    "MT": "EUR", "NL": "EUR", "PT": "EUR", "SI": "EUR", "SK": "EUR", "SM": "EUR",
    "VA": "EUR", "XK": "EUR",
    # Non-Eurozone Europe
    "BG": "BGN", "CH": "CHF", "CZ": "CZK", "DK": "DKK", "GB": "GBP", "HU": "HUF",
    "IS": "ISK", "LI": "CHF", "NO": "NOK", "PL": "PLN", "RO": "RON", "RS": "RSD",
    "RU": "RUB", "SE": "SEK", "TR": "TRY", "UA": "UAH", "BY": "BYN",
    # Americas
    "AR": "ARS", "BR": "BRL", "CA": "CAD", "CL": "CLP", "CO": "COP", "MX": "MXN",
    "PE": "PEN", "US": "USD",
    # Asia & Oceania
    "AE": "AED", "AU": "AUD", "CN": "CNY", "HK": "HKD", "ID": "IDR", "IL": "ILS",
    "IN": "INR", "JP": "JPY", "KR": "KRW", "MY": "MYR", "NZ": "NZD", "PH": "PHP",
    "QA": "QAR", "SA": "SAR", "SG": "SGD", "TH": "THB", "TW": "TWD", "VN": "VND",
    # Africa
    "EG": "EGP", "MA": "MAD", "NG": "NGN", "ZA": "ZAR",
}


class CurrencyConversionService:
    async def resolve_currency_for_destination(self, destination: str | None) -> str:
        """
        Resolves the ISO 4217 currency code for a mission destination using Nominatim
        (address.country_code) and the ISO 3166-1 alpha-2 country mapping.
        """
        if not destination or len(destination.strip()) < 3:
            return "EUR"

        try:
            locations = await search_locations(destination)
            if locations:
                country_code = str(locations[0].get("address", {}).get("country_code", "")).upper()
                if country_code in COUNTRY_CODE_TO_CURRENCY:
                    return COUNTRY_CODE_TO_CURRENCY[country_code]
        except Exception as e:
            logger.warning("Nominatim lookup failed for destination '%s': %s", destination, e)

        return "EUR"

    async def convert_to_eur(self, amount: Decimal, currency: str, date: str | None = None) -> CurrencyConversionDTO | None:
        if not currency:
            currency = "EUR"
        curr_code = currency.strip().upper()

        if curr_code == "EUR":
            return CurrencyConversionDTO(
                original_currency="EUR",
                original_amount=amount,
                converted_amount=amount,
                rate=Decimal("1.0"),
                date=date or "latest",
                provider="None (already EUR)",
            )

        # 1. Try Frankfurter API
        frankfurter_url = f"https://api.frankfurter.dev/v1/latest?base={curr_code}&symbols=EUR"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(frankfurter_url)
                if resp.status_code == 200:
                    data = resp.json()
                    rate = Decimal(str(data["rates"]["EUR"]))
                    rate_date = data.get("date", "latest")
                    converted = round(amount * rate, 2)
                    return CurrencyConversionDTO(
                        original_currency=curr_code,
                        original_amount=amount,
                        converted_amount=converted,
                        rate=rate,
                        date=rate_date,
                        provider="Frankfurter API",
                    )
        except Exception as e:
            logger.warning("Frankfurter API query failed for %s: %s", curr_code, e)

        # 2. Peg fallback (e.g. AED pegged to USD at 3.6725)
        if curr_code == "AED":
            try:
                usd_url = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR"
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(usd_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        usd_to_eur = Decimal(str(data["rates"]["EUR"]))
                        rate = round(usd_to_eur / AED_USD_PEG, 6)
                        rate_date = data.get("date", "latest")
                        converted = round(amount * rate, 2)
                        return CurrencyConversionDTO(
                            original_currency="AED",
                            original_amount=amount,
                            converted_amount=converted,
                            rate=rate,
                            date=rate_date,
                            provider="Frankfurter API (via USD peg 3.6725)",
                        )
            except Exception as e:
                logger.warning("AED peg conversion failed: %s", e)

        # 3. Fallback to Open Exchange Rates API (open.er-api.com)
        try:
            er_url = f"https://open.er-api.com/v6/latest/{curr_code}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(er_url)
                if resp.status_code == 200:
                    data = resp.json()
                    rate_val = data.get("rates", {}).get("EUR")
                    if rate_val:
                        rate = Decimal(str(rate_val))
                        rate_date = data.get("time_last_update_utc", "latest")
                        converted = round(amount * rate, 2)
                        return CurrencyConversionDTO(
                            original_currency=curr_code,
                            original_amount=amount,
                            converted_amount=converted,
                            rate=rate,
                            date=rate_date,
                            provider="Open Exchange Rates API",
                        )
        except Exception as e:
            logger.warning("Fallback currency exchange API failed for %s: %s", curr_code, e)

        return None
