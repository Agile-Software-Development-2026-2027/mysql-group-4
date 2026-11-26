from __future__ import annotations

import base64
import io
import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import anyio
import httpx
from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.core.config import settings
from app.core.enums import ExpenseCategory, ExpenseSubtype
from app.schemas.receipt_ai import ReceiptAutocompleteDTO
from app.services.currency_service import CurrencyConversionService

logger = logging.getLogger(__name__)

MAX_EXTRACT_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_IMAGE_DIMENSION = 1600
VISION_MAX_IMAGE_DIMENSION = 1024

VALID_CATEGORIES: set[str] = {"TRANSPORT", "ACCOMMODATION", "MEALS", "OTHER"}

SUBTYPES_BY_CATEGORY: dict[str, set[str]] = {
    "TRANSPORT": {
        "TRAIN",
        "PLANE",
        "SHIP",
        "PUBLIC_TRANSPORT",
        "TAXI_RENTAL",
        "OWN_VEHICLE",
    },
    "ACCOMMODATION": {
        "ACCOMMODATION_EXPENSE",
        "OTHER_ACCOMMODATION_EXPENSE",
    },
    "MEALS": {
        "MEALS_EXPENSE",
        "OTHER_MEALS_EXPENSE",
    },
    "OTHER": set(),
}

CURRENCY_ALIASES: dict[str, str] = {
    "€": "EUR",
    "EURO": "EUR",
    "$": "USD",
    "US$": "USD",
    "£": "GBP",
    "¥": "CNY",
    "RMB": "CNY",
    "元": "CNY",
    "NT$": "TWD",
    "NTD": "TWD",
    "₽": "RUB",
    "РУБ": "RUB",
    "CHF": "CHF",
    "SGD": "SGD",
    "CAD": "CAD",
    "AED": "AED",
}

SYSTEM_PROMPT = """You extract structured expense data from travel receipts (text and/or image).
Return ONLY valid JSON with these exact keys:
{
  "category": "TRANSPORT" | "ACCOMMODATION" | "MEALS" | "OTHER" | null,
  "subtype": "TRAIN" | "PLANE" | "SHIP" | "PUBLIC_TRANSPORT" | "TAXI_RENTAL" | "OWN_VEHICLE" | "ACCOMMODATION_EXPENSE" | "OTHER_ACCOMMODATION_EXPENSE" | "MEALS_EXPENSE" | "OTHER_MEALS_EXPENSE" | null,
  "amount": number | null,
  "currency": "3-letter ISO code like EUR, USD, CNY, TWD, RUB, GBP, CHF, SGD, CAD, AED" | null,
  "starts_at": "YYYY-MM-DDTHH:MM" | null,
  "ends_at": "YYYY-MM-DDTHH:MM" | null,
  "issued_date": "YYYY-MM-DD" | null,
  "merchant": string | null,
  "description": "short concise expense summary in English (max 80 chars)" | null,
  "itinerary_from": string | null,
  "itinerary_to": string | null
}
Rules:
- Use the FINAL TOTAL paid amount (not subtotal or tax).
- issued_date is the date printed on the receipt/invoice, formatted as YYYY-MM-DD; return null if it is not shown. Do not substitute a travel or service date for it.
- TRANSPORT (flights, trains, buses, taxis): extract departure city/station in itinerary_from, arrival city/station in itinerary_to, departure datetime in starts_at, and arrival datetime in ends_at (null if not shown).
- ACCOMMODATION (hotels, lodging): extract check-in datetime in starts_at and check-out datetime in ends_at; itinerary_from and itinerary_to MUST be null.
- MEALS: subtype must be MEALS_EXPENSE or OTHER_MEALS_EXPENSE; extract receipt datetime in starts_at; ends_at, itinerary_from, and itinerary_to MUST be null.
- OTHER: subtype, ends_at, itinerary_from, and itinerary_to MUST be null; extract receipt datetime in starts_at.
- If time is missing on a date, default to T12:00.
- Return null for fields that cannot be inferred."""


def preprocess_receipt_image(
    raw_bytes: bytes,
    *,
    max_dimension: int = DEFAULT_MAX_IMAGE_DIMENSION,
) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size
        longest = max(width, height)
        if longest > max_dimension:
            scale = max_dimension / float(longest)
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=92)
        return out.getvalue()


def _prepare_vision_base64(raw_bytes: bytes) -> str | None:
    try:
        compressed = preprocess_receipt_image(raw_bytes, max_dimension=VISION_MAX_IMAGE_DIMENSION)
        return base64.b64encode(compressed).decode("utf-8")
    except Exception as exc:
        logger.warning("Could not encode image for vision: %s", exc)
        return None


def extract_pdf_content(raw_bytes: bytes) -> tuple[str, bytes | None]:
    """Extract embedded text or embedded image from a PDF document."""
    try:
        import pypdf  # type: ignore[import-not-found]
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages_text: list[str] = []
        first_image_bytes: bytes | None = None
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())
            if first_image_bytes is None and page.images:
                try:
                    first_image_bytes = page.images[0].data
                except Exception:
                    pass
        return "\n".join(pages_text).strip(), first_image_bytes
    except Exception as exc:
        logger.warning("pypdf extraction failed: %s", exc)
        return "", None


_ocr_engine_instance: Any = None


def get_ocr_engine():
    global _ocr_engine_instance
    if _ocr_engine_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
            _ocr_engine_instance = RapidOCR()
        except ImportError:
            logger.warning("rapidocr_onnxruntime not installed; OCR will be disabled.")
            _ocr_engine_instance = None
    return _ocr_engine_instance


def _normalize_currency(raw: Any, hint_currency: str | None) -> str | None:
    del hint_currency
    if isinstance(raw, str):
        cleaned = raw.strip().upper()
        if cleaned in CURRENCY_ALIASES:
            return CURRENCY_ALIASES[cleaned]
        if re.fullmatch(r"[A-Z]{3}", cleaned):
            return cleaned
    return None


def _normalize_amount(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip().replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(",", "")
    text = re.sub(r"[^\d.]", "", text)
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value.quantize(Decimal("0.01")) if value > 0 else None


def _normalize_date(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            has_time = "T" in fmt or " " in fmt
            dt = datetime.strptime(text[:16] if has_time else text[:10], fmt)
            return dt.strftime("%Y-%m-%dT%H:%M") if has_time else dt.strftime("%Y-%m-%dT12:00")
        except ValueError:
            continue
    return None


def _normalize_category_and_subtype(
    raw_cat: Any, raw_sub: Any
) -> tuple[ExpenseCategory | None, ExpenseSubtype | None]:
    cat_str = str(raw_cat).strip().upper() if isinstance(raw_cat, str) else None
    if cat_str not in VALID_CATEGORIES:
        return None, None
    sub_str = str(raw_sub).strip().upper() if isinstance(raw_sub, str) else None
    allowed_subs = SUBTYPES_BY_CATEGORY[cat_str]
    if sub_str not in allowed_subs:
        sub_str = None
    try:
        cat_enum = ExpenseCategory(cat_str)
    except ValueError:
        cat_enum = None
    try:
        sub_enum = ExpenseSubtype(sub_str) if sub_str else None
    except ValueError:
        sub_enum = None
    return cat_enum, sub_enum


class ReceiptAIService:
    """Integrated Receipt OCR (RapidOCR) + PDF parser + Multimodal LLM extraction service."""

    def __init__(self, currency_service: CurrencyConversionService) -> None:
        self.currency_service = currency_service

    def _sync_ocr(self, image_bytes: bytes) -> tuple[str, list[str], float | None]:
        engine = get_ocr_engine()
        if engine is None:
            return "", [], None
        processed = preprocess_receipt_image(image_bytes)
        result, _ = engine(processed)
        if not result:
            return "", [], None
        lines = [r[1] for r in result]
        scores = [r[2] for r in result if len(r) > 2 and isinstance(r[2], (int, float))]
        avg_score = float(sum(scores) / len(scores)) if scores else None
        return "\n".join(lines), lines, avg_score

    async def _query_ollama(
        self,
        raw_text: str,
        *,
        hint_currency: str | None,
        hint_country: str | None,
        image_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        hints = []
        if hint_country:
            hints.append(f"Mission country: {hint_country}")
        if hint_currency:
            hints.append(f"Expected local currency: {hint_currency}")
        hint_block = "\n".join(hints)

        text_section = f"\n\nDOCUMENT / OCR TEXT:\n{raw_text[:4000]}" if raw_text.strip() else ""
        user_prompt = f"{hint_block}{text_section}".strip()
        if not user_prompt:
            user_prompt = "Extract travel expense details from this receipt image."

        user_message: dict[str, Any] = {"role": "user", "content": user_prompt}
        if settings.OLLAMA_VISION_ENABLED and image_bytes:
            b64_img = _prepare_vision_base64(image_bytes)
            if b64_img:
                user_message["images"] = [b64_img]

        payload = {
            "model": settings.OLLAMA_MODEL,
            "stream": False,
            "think": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                user_message,
            ],
        }

        async with httpx.AsyncClient(timeout=settings.RECEIPT_AI_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{settings.OLLAMA_URL.rstrip('/')}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        if "```" in content:
            content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content.strip())
        parsed = json.loads(content) if content else {}
        return parsed if isinstance(parsed, dict) else {}

    async def extract_receipt(
        self,
        file: UploadFile,
        *,
        hint_currency: str | None = None,
        hint_country: str | None = None,
    ) -> ReceiptAutocompleteDTO:
        content_type = (file.content_type or "").lower()
        filename = (file.filename or "").lower()

        is_pdf = content_type == "application/pdf" or filename.endswith(".pdf")
        is_image = content_type.startswith("image/") or any(
            filename.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")
        )

        if not is_pdf and not is_image:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Receipt AI extraction supports image files (JPEG, PNG, WEBP) and PDF documents.",
            )

        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded receipt file is empty.",
            )
        if len(raw_bytes) > MAX_EXTRACT_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Receipt file exceeds 10 MB limit.",
            )

        warnings: list[str] = []
        raw_text = ""
        confidence: float | None = None
        engine_name = "rapidocr"
        image_for_vision: bytes | None = None

        if is_pdf:
            pdf_text, embedded_image = await anyio.to_thread.run_sync(extract_pdf_content, raw_bytes)
            if len(pdf_text) >= 20:
                # Native digital PDF: direct text extraction bypasses OCR completely!
                raw_text = pdf_text
                confidence = 1.0
                engine_name = "pdf_text"
                image_for_vision = embedded_image
            elif embedded_image:
                # Scanned PDF with embedded receipt image: run OCR on the image
                raw_text, _, confidence = await anyio.to_thread.run_sync(self._sync_ocr, embedded_image)
                engine_name = "rapidocr"
                image_for_vision = embedded_image
            else:
                raw_text = pdf_text
                engine_name = "pdf_text"
                warnings.append("PDF contains very little text and no embedded image.")
        else:
            image_for_vision = raw_bytes
            raw_text, _, confidence = await anyio.to_thread.run_sync(self._sync_ocr, raw_bytes)
            engine_name = "rapidocr"

        if not raw_text.strip() and not image_for_vision:
            warnings.append("No text or image detected on the receipt file.")
            return ReceiptAutocompleteDTO(
                raw_text="",
                confidence=confidence,
                ocr_engine=engine_name,
                llm_model=settings.OLLAMA_MODEL,
                warnings=warnings,
            )

        extracted: dict[str, Any] = {}
        try:
            extracted = await self._query_ollama(
                raw_text=raw_text,
                hint_currency=hint_currency,
                hint_country=hint_country,
                image_bytes=image_for_vision,
            )
        except httpx.TimeoutException:
            logger.warning("Ollama timed out during receipt extraction.")
            warnings.append("LLM service timed out; returning raw OCR/PDF text.")
        except Exception as exc:
            logger.warning("Ollama extraction failed: %s", exc)
            warnings.append(f"LLM extraction unavailable ({type(exc).__name__}); returning raw text.")

        category, subtype = _normalize_category_and_subtype(
            extracted.get("category"), extracted.get("subtype")
        )
        amount = _normalize_amount(extracted.get("amount"))
        currency = _normalize_currency(extracted.get("currency"), hint_currency)
        starts_at = _normalize_date(extracted.get("starts_at") or extracted.get("date_incurred"))
        ends_at = _normalize_date(extracted.get("ends_at"))
        normalized_issued_date = _normalize_date(extracted.get("issued_date"))
        issued_date = normalized_issued_date[:10] if normalized_issued_date else None
        merchant = extracted.get("merchant")
        description = extracted.get("description")
        itin_from = extracted.get("itinerary_from")
        itin_to = extracted.get("itinerary_to")

        norm_from = itin_from.strip()[:120] if isinstance(itin_from, str) and itin_from.strip() else None
        norm_to = itin_to.strip()[:120] if isinstance(itin_to, str) and itin_to.strip() else None

        # Enforce RefundItemBase category field rules so the form never gets disallowed fields
        if category in (ExpenseCategory.MEALS, ExpenseCategory.OTHER):
            norm_from = None
            norm_to = None
            ends_at = None
        elif category == ExpenseCategory.ACCOMMODATION:
            norm_from = None
            norm_to = None

        if starts_at and ends_at and ends_at < starts_at:
            ends_at = None

        converted_amount_eur: Decimal | None = None
        exchange_rate: Decimal | None = None

        if amount is not None and currency:
            if currency == "EUR":
                converted_amount_eur = amount
                exchange_rate = Decimal("1.0")
            elif issued_date:
                conversion = await self.currency_service.convert_to_eur(
                    amount=amount,
                    currency=currency,
                    issued_date=issued_date,
                )
                if conversion is not None:
                    converted_amount_eur = conversion.converted_amount
                    exchange_rate = conversion.rate
                else:
                    warnings.append(f"Could not convert {currency} to EUR automatically.")
            else:
                warnings.append(
                    f"Could not convert {currency} to EUR automatically without a receipt issue date."
                )

        return ReceiptAutocompleteDTO(
            category=category,
            subtype=subtype,
            amount=amount,
            currency=currency,
            converted_amount_eur=converted_amount_eur,
            exchange_rate=exchange_rate,
            starts_at=starts_at,
            ends_at=ends_at,
            issued_date=issued_date,
            merchant=merchant.strip()[:120] if isinstance(merchant, str) and merchant.strip() else None,
            description=description.strip()[:255] if isinstance(description, str) and description.strip() else None,
            itinerary_from=norm_from,
            itinerary_to=norm_to,
            raw_text=raw_text,
            confidence=confidence,
            ocr_engine=engine_name,
            llm_model=settings.OLLAMA_MODEL,
            warnings=warnings,
        )
