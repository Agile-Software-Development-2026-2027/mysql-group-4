import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session
from app.db.models import User
from app.security import current_active_user
from app.schemas.document import MissionDocumentResponse
from app.services.document_service import save_mission_document, get_mission_documents

router=APIRouter(prefix="/missions/{mission_id}/documents", tags=["documents"])

@router.post("", response_model=MissionDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(mission_id: uuid.UUID, file: UploadFile=File(...), session: AsyncSession=Depends(get_async_session), user: User=Depends(current_active_user)):
    return await save_mission_document(mission_id, file, user, session)

@router.get("", response_model=List[MissionDocumentResponse], status_code=status.HTTP_200_OK)
async def list_documents(mission_id: uuid.UUID, session: AsyncSession=Depends(get_async_session), user: User=Depends(current_active_user)):
    return await get_mission_documents(mission_id, user, session)