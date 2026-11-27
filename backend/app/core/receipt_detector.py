from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import anyio
import cv2
import httpx
import numpy as np

from app.core.config import settings
from app.schemas.receipt_ai import BoundingBoxDTO, ReceiptDetectionResponseDTO

logger = logging.getLogger(__name__)


class BaseReceiptDetector(ABC):
    """Abstract interface for receipt bounding-box detection providers."""

    @abstractmethod
    async def detect(self, image_bytes: bytes) -> ReceiptDetectionResponseDTO:
        raise NotImplementedError


class OpenCVReceiptDetector(BaseReceiptDetector):
    """Local OpenCV fallback detector."""

    def _sync_detect(self, image_bytes: bytes) -> ReceiptDetectionResponseDTO:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode image for receipt detection.")

        img_h, img_w = img.shape[:2]
        img_area = img_h * img_w

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        l_channel = lab[:, :, 0].astype(np.float32)
        s_channel = hsv[:, :, 1].astype(np.float32)

        whiteness = np.clip(l_channel - 1.2 * s_channel, 0, 255).astype(np.uint8)
        whiteness = cv2.GaussianBlur(whiteness, (5, 5), 0)

        _, mask = cv2.threshold(whiteness, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        k_open = max(3, int(min(img_w, img_h) * 0.012) | 1)
        k_close = max(5, int(min(img_w, img_h) * 0.025) | 1)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k_open, k_open), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k_close, k_close), np.uint8))

        def extract_candidates(binary_mask: np.ndarray) -> list[tuple[int, int, int, int]]:
            contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            found: list[tuple[int, int, int, int]] = []
            min_area = img_area * 0.015
            max_area = img_area * 0.95

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if area < min_area or area > max_area:
                    continue
                if w < 30 or h < 30:
                    continue
                aspect = w / float(h)
                if aspect < 0.15 or aspect > 6.5:
                    continue
                found.append((x, y, w, h))
            return found

        candidates = extract_candidates(mask)

        if len(candidates) <= 1:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 120)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((k_close, k_close), np.uint8))
            edge_candidates = extract_candidates(edges)
            if len(edge_candidates) > len(candidates):
                candidates = edge_candidates

        def contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
            ox, oy, ow, oh = outer
            ix, iy, iw, ih = inner
            margin = 10
            return (
                ix >= ox - margin
                and iy >= oy - margin
                and ix + iw <= ox + ow + margin
                and iy + ih <= oy + oh + margin
                and (ow * oh) > (iw * ih) * 1.4
            )

        filtered: list[tuple[int, int, int, int]] = []
        for box in candidates:
            inner_count = sum(1 for other in candidates if other != box and contains(box, other))
            if inner_count >= 2:
                continue
            filtered.append(box)

        filtered.sort(key=lambda b: b[2] * b[3], reverse=True)
        deduped: list[tuple[int, int, int, int]] = []
        for box in filtered:
            x1, y1, w1, h1 = box
            keep = True
            for kept in deduped:
                x2, y2, w2, h2 = kept
                ix1, iy1 = max(x1, x2), max(y1, y2)
                ix2, iy2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = w1 * h1 + w2 * h2 - inter
                if union > 0 and (inter / union) > 0.65:
                    keep = False
                    break
            if keep:
                deduped.append(box)

        if not deduped:
            deduped = [(0, 0, img_w, img_h)]

        row_tolerance = max(20, int(img_h * 0.08))
        deduped.sort(key=lambda b: (b[1] // row_tolerance, b[0]))

        boxes = [
            BoundingBoxDTO(x=int(x), y=int(y), width=int(w), height=int(h), page=0)
            for (x, y, w, h) in deduped
        ]
        return ReceiptDetectionResponseDTO(
            image_width=img_w,
            image_height=img_h,
            boxes=boxes,
        )

    async def detect(self, image_bytes: bytes) -> ReceiptDetectionResponseDTO:
        return await anyio.to_thread.run_sync(self._sync_detect, image_bytes)


class RemoteReceiptDetector(BaseReceiptDetector):
    """Model-agnostic HTTP client for a remote object detection microservice (e.g. GroundingDINO on Colab)."""

    def __init__(self, api_url: str, timeout: float = 60.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    async def detect(self, image_bytes: bytes) -> ReceiptDetectionResponseDTO:
        if not self.api_url:
            raise ValueError("DETECTOR_API_URL is not configured.")

        files = {"file": ("receipt.jpg", image_bytes, "image/jpeg")}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.api_url}/detect", files=files)
            resp.raise_for_status()
            data = resp.json()

        boxes = [
            BoundingBoxDTO(
                x=int(b["x"]),
                y=int(b["y"]),
                width=int(b["width"]),
                height=int(b["height"]),
                page=int(b.get("page", 0)),
            )
            for b in data.get("boxes", [])
        ]
        return ReceiptDetectionResponseDTO(
            image_width=int(data["image_width"]),
            image_height=int(data["image_height"]),
            boxes=boxes,
        )


class FallbackReceiptDetector(BaseReceiptDetector):
    """Wraps a primary detector with an automatic fallback detector."""

    def __init__(self, primary: BaseReceiptDetector, fallback: BaseReceiptDetector) -> None:
        self.primary = primary
        self.fallback = fallback

    async def detect(self, image_bytes: bytes) -> ReceiptDetectionResponseDTO:
        try:
            result = await self.primary.detect(image_bytes)
            if result.boxes:
                return result
            logger.warning("Primary receipt detector returned 0 boxes; falling back to OpenCV.")
        except httpx.TimeoutException:
            logger.warning("Primary receipt detector timed out; falling back to OpenCV.")
        except Exception as exc:
            logger.warning("Primary receipt detector failed (%s); falling back to OpenCV.", exc)

        return await self.fallback.detect(image_bytes)


def get_receipt_detector() -> BaseReceiptDetector:
    """Factory that returns the configured receipt detector provider."""
    provider = settings.RECEIPT_DETECTOR_PROVIDER.strip().lower()
    fallback = OpenCVReceiptDetector()

    if provider == "remote" and settings.DETECTOR_API_URL.strip():
        primary = RemoteReceiptDetector(
            api_url=settings.DETECTOR_API_URL,
            timeout=settings.RECEIPT_AI_TIMEOUT_SECONDS,
        )
        return FallbackReceiptDetector(primary=primary, fallback=fallback)

    return fallback