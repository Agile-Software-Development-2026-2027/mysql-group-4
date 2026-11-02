import io
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from main import app
from app.security import current_active_user
from app.db.models import User

UPLOAD_DIR=Path("uploads")

@pytest.fixture(autouse=True)
def cleanup_uploads_and_mock_auth():
    mock_user=User(id=uuid.uuid4(), email="test@example.com", is_active=True, is_superuser=True)
    app.dependency_overrides[current_active_user]=lambda: mock_user
    with patch("app.services.document_service._get_mission_and_check_permission", return_value=None):
        yield
    app.dependency_overrides.clear()
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)

@pytest.mark.asyncio
async def test_upload_pdf_document_success(client: AsyncClient):
    mission_id=uuid.uuid4()
    pdf_content=b"%PDF-1.4 Fake PDF Content"
    files={"file": ("document.pdf", io.BytesIO(pdf_content), "application/pdf")}
    response=await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    assert response.status_code==201
    data=response.json()
    assert data["filename"]=="document.pdf"
    assert data["mission_id"]==str(mission_id)
    assert "id" in data
    assert "created_at" in data
    assert "created_by" in data

@pytest.mark.asyncio
async def test_upload_non_pdf_fails(client: AsyncClient):
    mission_id=uuid.uuid4()
    txt_content=b"Invalid file."
    files={"file": ("document.txt", io.BytesIO(txt_content), "text/plain")}
    response=await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    assert response.status_code==400
    assert response.json()["detail"]=="Only PDFs accepted."

@pytest.mark.asyncio
async def test_list_mission_documents(client: AsyncClient):
    mission_id=uuid.uuid4()
    pdf_content=b"%PDF-1.4 Fake PDF Content"
    files={"file": ("document.pdf", io.BytesIO(pdf_content), "application/pdf")}
    await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    response=await client.get(f"/api/v1/missions/{mission_id}/documents")
    assert response.status_code==200
    data=response.json()
    assert len(data)>=1
    assert data[0]["filename"]=="document.pdf"