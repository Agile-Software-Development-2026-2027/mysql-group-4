import io
import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_pdf_document_success(client: AsyncClient):
    mission_id=uuid.uuid4()
    pdf_content=b"%PDF-1.4 Fake PDF Content"
    files={"file": ("document.pdf", io.BytesIO(pdf_content), "application/pdf")}
    response=await client.post(f"/api/v1/missions/{mission_id}/documents",files=files)
    assert response.status_code==201
    data=response.json()
    assert data["filename"]=="document.pdf"
    assert data["mission_id"]==str(mission_id)
    assert "id" in data

@pytest.mark.asyncio
async def test_upload_non_pdf_fails(client: AsyncClient):
    mission_id=uuid.uuid4()
    txt_content=b"Unvaild file."
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