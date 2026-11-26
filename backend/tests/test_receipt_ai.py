import io
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, UploadFile

from PIL import Image

from app.schemas.receipt_ai import BoundingBoxDTO, ReceiptDetectionResponseDTO
from app.core.enums import ExpenseCategory, ExpenseSubtype
from app.schemas.currency import CurrencyConversionDTO
from app.services.currency_service import CurrencyConversionService
from app.services.receipt_ai_service import ReceiptAIService


def _make_upload_file(
    content: bytes = b"fake-jpeg-bytes",
    filename: str = "receipt.jpg",
    content_type: str = "image/jpeg",
) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


@pytest.mark.asyncio
async def test_receipt_ai_rejects_unsupported_file_types():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    with pytest.raises(HTTPException) as exc:
        await service.extract_receipt(
            _make_upload_file(filename="archive.zip", content_type="application/zip")
        )
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_receipt_ai_rejects_empty_file():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    with pytest.raises(HTTPException) as exc:
        await service.extract_receipt(_make_upload_file(content=b""))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_receipt_ai_accepts_pdf_and_bypasses_ocr():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    pdf_sample_text = "Trenitalia Biglietto Frecciarossa Roma - Milano 65.00 EUR 2026-11-20T08:30"
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "category": "TRANSPORT",
                "subtype": "TRAIN",
                "amount": 65.00,
                "currency": "EUR",
                "date_incurred": "2026-11-20T08:30",
                "merchant": "Trenitalia",
                "description": "Frecciarossa Roma - Milano",
            })
        }
    }

    with (
        patch("app.services.receipt_ai_service.extract_pdf_content", return_value=(pdf_sample_text, None)),
        patch.object(service, "_sync_ocr") as mock_ocr,
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)),
    ):
        result = await service.extract_receipt(
            _make_upload_file(content=b"%PDF-1.4...", filename="ticket.pdf", content_type="application/pdf")
        )

    # Verify OCR was completely bypassed
    mock_ocr.assert_not_called()
    assert result.ocr_engine == "pdf_text"
    assert result.category == ExpenseCategory.TRANSPORT
    assert result.subtype == ExpenseSubtype.TRAIN
    assert result.amount == Decimal("65.00")
    assert result.currency == "EUR"
    assert result.merchant == "Trenitalia"


@pytest.mark.asyncio
async def test_receipt_ai_sends_vision_image_to_ollama():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "category": "MEALS",
                "subtype": "MEALS_EXPENSE",
                "amount": 15.50,
                "currency": "EUR",
                "merchant": "Bar Centrale",
            })
        }
    }

    captured_payload = None

    async def mock_post(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = kwargs.get("json")
        return mock_resp

    with (
        patch.object(service, "_sync_ocr", return_value=("Bar Centrale 15.50 EUR", ["Bar Centrale 15.50 EUR"], 0.95)),
        patch("app.services.receipt_ai_service._prepare_vision_base64", return_value="base64fakeimage"),
        patch("httpx.AsyncClient.post", new=mock_post),
    ):
        result = await service.extract_receipt(_make_upload_file())

    assert result.amount == Decimal("15.50")
    assert captured_payload is not None
    user_msg = captured_payload["messages"][1]
    assert "images" in user_msg
    assert user_msg["images"] == ["base64fakeimage"]


@pytest.mark.asyncio
async def test_receipt_ai_extracts_and_converts_foreign_currency():
    currency_service = CurrencyConversionService()
    currency_service.convert_to_eur = AsyncMock(
        return_value=CurrencyConversionDTO(
            original_currency="RUB",
            original_amount=Decimal("420.00"),
            converted_amount=Decimal("4.62"),
            rate=Decimal("0.011"),
        )
    )
    service = ReceiptAIService(currency_service=currency_service)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "category": "MEALS",
                "subtype": "MEALS_EXPENSE",
                "amount": 420.00,
                "currency": "RUB",
                "issued_date": "2019-07-29",
                "starts_at": "2019-07-29T18:30",
                "ends_at": "2019-07-29T19:00",
                "itinerary_from": "Ignored",
                "itinerary_to": "Ignored",
                "merchant": "Blinok",
                "description": "Dinner at Blinok",
            })
        }
    }

    with (
        patch.object(service, "_sync_ocr", return_value=("ИТОГ 420.00 РУБ", ["ИТОГ 420.00 РУБ"], 0.95)),
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)),
    ):
        result = await service.extract_receipt(
            _make_upload_file(),
            hint_currency="RUB",
            hint_country="Ulan-Ude, Russia",
        )

    assert result.category == ExpenseCategory.MEALS
    assert result.subtype == ExpenseSubtype.MEALS_EXPENSE
    assert result.amount == Decimal("420.00")
    assert result.currency == "RUB"
    assert result.converted_amount_eur == Decimal("4.62")
    assert result.exchange_rate == Decimal("0.011")
    currency_service.convert_to_eur.assert_awaited_once_with(
        amount=Decimal("420.00"),
        currency="RUB",
        issued_date="2019-07-29",
    )
    assert result.merchant == "Blinok"
    assert result.starts_at == "2019-07-29T18:30"
    # MEALS must strip disallowed ends_at and itinerary fields
    assert result.ends_at is None
    assert result.itinerary_from is None
    assert result.itinerary_to is None


@pytest.mark.asyncio
async def test_receipt_ai_skips_foreign_currency_conversion_without_issued_date():
    currency_service = CurrencyConversionService()
    currency_service.convert_to_eur = AsyncMock()
    service = ReceiptAIService(currency_service=currency_service)

    with (
        patch.object(
            service,
            "_sync_ocr",
            return_value=("TOTAL 12.50 USD", ["TOTAL 12.50 USD"], 0.95),
        ),
        patch.object(
            service,
            "_query_ollama",
            new=AsyncMock(return_value={"amount": 12.50, "currency": "USD"}),
        ),
    ):
        result = await service.extract_receipt(_make_upload_file())

    currency_service.convert_to_eur.assert_not_awaited()
    assert result.converted_amount_eur is None
    assert any("without a receipt issue date" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_receipt_ai_handles_markdown_fenced_json():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    fenced_content = "```json\n" + json.dumps({
        "category": "TRANSPORT",
        "subtype": "PUBLIC_TRANSPORT",
        "amount": 2.60,
        "currency": "EUR",
        "merchant": "Klagenfurt Mobil",
    }) + "\n```"

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"message": {"content": fenced_content}}

    with (
        patch.object(service, "_sync_ocr", return_value=("Klagenfurt Mobil 2.60 EUR", ["Klagenfurt Mobil 2.60 EUR"], 0.98)),
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)),
    ):
        result = await service.extract_receipt(_make_upload_file())

    assert result.category == ExpenseCategory.TRANSPORT
    assert result.amount == Decimal("2.60")
    assert result.merchant == "Klagenfurt Mobil"


@pytest.mark.asyncio
async def test_receipt_ai_graceful_on_ollama_timeout():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    with (
        patch.object(service, "_sync_ocr", return_value=("RAW TICKET 10.00 EUR", ["RAW TICKET 10.00 EUR"], 0.90)),
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ReadTimeout("timeout"))),
    ):
        result = await service.extract_receipt(_make_upload_file())

    assert result.raw_text == "RAW TICKET 10.00 EUR"
    assert any("timed out" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_receipt_ai_accommodation_keeps_dates_strips_itinerary():
    currency_service = CurrencyConversionService()
    service = ReceiptAIService(currency_service=currency_service)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "category": "ACCOMMODATION",
                "subtype": "ACCOMMODATION_EXPENSE",
                "amount": 320.00,
                "currency": "EUR",
                "starts_at": "2026-11-10T14:00",
                "ends_at": "2026-11-13T11:00",
                "itinerary_from": "Milan",
                "itinerary_to": "Rome",
                "merchant": "Hotel Roma",
            })
        }
    }

    with (
        patch.object(service, "_sync_ocr", return_value=("HOTEL ROMA 320.00 EUR", ["HOTEL ROMA 320.00 EUR"], 0.95)),
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)),
    ):
        result = await service.extract_receipt(_make_upload_file())

    assert result.category == ExpenseCategory.ACCOMMODATION
    assert result.starts_at == "2026-11-10T14:00"
    assert result.ends_at == "2026-11-13T11:00"
    assert result.itinerary_from is None
    assert result.itinerary_to is None

@pytest.mark.asyncio
async def test_detect_receipt_boxes_image_and_pdf():
    service = ReceiptAIService(currency_service=CurrencyConversionService())
    service.detector = MagicMock()
    service.detector.detect = AsyncMock(
        return_value=ReceiptDetectionResponseDTO(
            image_width=400,
            image_height=300,
            boxes=[BoundingBoxDTO(x=15, y=20, width=150, height=220, page=0)],
        )
    )

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color=(255, 255, 255)).save(buf, format="JPEG")
    img_res = await service.detect_receipt_boxes(_make_upload_file(content=buf.getvalue()))
    assert img_res.image_width == 400
    assert len(img_res.boxes) == 1
    assert img_res.pages == []


    with patch("app.services.receipt_ai_service.render_pdf_pages", return_value=[b"p0", b"p1"]):
        pdf_res = await service.detect_receipt_boxes(
            _make_upload_file(content=b"%PDF-1.4", filename="doc.pdf", content_type="application/pdf")
        )
    assert len(pdf_res.pages) == 2
    assert [b.page for b in pdf_res.boxes] == [0, 1]


@pytest.mark.asyncio
async def test_detect_receipt_boxes_validation_errors():
    service = ReceiptAIService(currency_service=CurrencyConversionService())

    with pytest.raises(HTTPException) as exc_415:
        await service.detect_receipt_boxes(
            _make_upload_file(filename="notes.txt", content_type="text/plain")
        )
    assert exc_415.value.status_code == 415

    with pytest.raises(HTTPException) as exc_400:
        await service.detect_receipt_boxes(_make_upload_file(content=b""))
    assert exc_400.value.status_code == 400

    with pytest.raises(HTTPException) as exc_413:
        await service.detect_receipt_boxes(_make_upload_file(content=b"x" * (10 * 1024 * 1024 + 1)))
    assert exc_413.value.status_code == 413


def test_crop_receipt_dimensions_and_clamping():
    service = ReceiptAIService(currency_service=CurrencyConversionService())
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), color=(100, 150, 200)).save(buf, format="JPEG")
    raw_img = buf.getvalue()


    cropped_bytes = service.crop_receipt(
        raw_img, BoundingBoxDTO(x=20, y=30, width=80, height=60, page=0)
    )
    with Image.open(io.BytesIO(cropped_bytes)) as cropped:
        assert cropped.size == (80, 60)


    clamped_bytes = service.crop_receipt(
        raw_img, BoundingBoxDTO(x=150, y=100, width=100, height=100, page=0)
    )
    with Image.open(io.BytesIO(clamped_bytes)) as clamped:
        assert clamped.size == (50, 50)