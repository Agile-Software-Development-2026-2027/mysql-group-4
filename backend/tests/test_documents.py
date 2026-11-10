import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient
from main import app
from app.security import current_active_user
from app.db.models import User
from app.db.mission import Mission
from app.db.mission_document import MissionDocument

@pytest.fixture(autouse=True)
def mock_auth_and_minio():
    mock_user=User(id=uuid.uuid4(), email="test@example.com", is_active=True, is_superuser=True)
    app.dependency_overrides[current_active_user]=lambda: mock_user
    mock_response=MagicMock()
    mock_response.read.return_value=b"%PDF-1.4 Mock PDF Content"
    mock_response.close.return_value=None
    mock_response.release_conn.return_value=None
    with patch("app.services.document_service.minio_client") as mock_minio:
        mock_minio.bucket_exists.return_value=True
        mock_minio.put_object.return_value=None
        mock_minio.get_object.return_value=mock_response
        yield mock_minio
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_upload_pdf_document_success(client: AsyncClient, db_session):
    mission_id=uuid.uuid4()
    user_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=user_id, 
        subject="Test Mission", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.0, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=user_id
    )
    db_session.add(mission)
    await db_session.commit()
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
async def test_upload_non_pdf_fails(client: AsyncClient, db_session):
    mission_id=uuid.uuid4()
    user_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=user_id, 
        subject="Test Mission", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.0, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=user_id
    )
    db_session.add(mission)
    await db_session.commit()
    txt_content=b"Invalid file."
    files={"file": ("document.txt", io.BytesIO(txt_content), "text/plain")}
    response=await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    assert response.status_code==400
    assert response.json()["detail"]=="Only PDFs accepted."

@pytest.mark.asyncio
async def test_list_mission_documents(client: AsyncClient, db_session):
    mission_id=uuid.uuid4()
    user_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=user_id, 
        subject="Test Mission", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.0, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=user_id
    )
    db_session.add(mission)
    await db_session.commit()
    pdf_content=b"%PDF-1.4 Fake PDF Content"
    files={"file": ("document.pdf", io.BytesIO(pdf_content), "application/pdf")}
    await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    response=await client.get(f"/api/v1/missions/{mission_id}/documents")
    assert response.status_code==200
    data=response.json()
    assert len(data)>=1
    assert data[0]["filename"]=="document.pdf"

#1 happy path (200 OK - Download PDF)
@pytest.mark.asyncio
async def test_download_document_success(client: AsyncClient, db_session):
    mission_id=uuid.uuid4()
    doc_id=uuid.uuid4()
    user_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=user_id, 
        subject="Test Mission", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.0, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=user_id
    )
    doc=MissionDocument(id=doc_id, mission_id=mission_id, filename="receipt.pdf", file_path="test/path.pdf", created_by=user_id)
    db_session.add_all([mission, doc])
    await db_session.commit()
    response=await client.get(f"/api/v1/missions/{mission_id}/documents/{doc_id}")
    assert response.status_code==200
    assert response.headers["content-type"]=="application/pdf"
    assert b"%PDF-1.4 Mock PDF Content" in response.content

#2 field validation (422 unprocessable entity)
@pytest.mark.asyncio
async def test_upload_document_missing_file_validation_error(client: AsyncClient):
    mission_id=uuid.uuid4()
    response=await client.post(f"/api/v1/missions/{mission_id}/documents", data={})
    assert response.status_code==422

#3 security/authorization (403 forbidden)
@pytest.mark.asyncio
async def test_upload_document_forbidden(client: AsyncClient, db_session):
    normal_user=User(id=uuid.uuid4(), email="user@example.com", is_active=True, is_superuser=False)
    app.dependency_overrides[current_active_user]=lambda: normal_user
    mission_id=uuid.uuid4()
    other_user_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=other_user_id, 
        subject="Someone else's mission", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.00, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=uuid.uuid4()
    )
    db_session.add(mission)
    await db_session.commit()
    files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    response=await client.post(f"/api/v1/missions/{mission_id}/documents", files=files)
    assert response.status_code==403
    assert response.json()["detail"]=="No permission."

#4 business logic/not found (404 not found)
@pytest.mark.asyncio
async def test_download_document_not_found(client: AsyncClient, db_session):
    mission_id=uuid.uuid4()
    non_existent_doc_id=uuid.uuid4()
    mission=Mission(
        id=mission_id, 
        requester_id=uuid.uuid4(), 
        subject="Test", 
        mission_type="RESEARCH", 
        destination="Test Destination", 
        estimated_cost=100.00, 
        starts_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), 
        ends_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), 
        fund_manager_id=uuid.uuid4()
    )
    db_session.add(mission)
    await db_session.commit()
    response=await client.get(f"/api/v1/missions/{mission_id}/documents/{non_existent_doc_id}")
    assert response.status_code==404
    assert response.json()["detail"]=="Document not found."