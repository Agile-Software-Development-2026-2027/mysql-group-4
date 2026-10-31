import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.mission_document import MissionDocument

UPLOAD_DIR=Path("uploads/missions")

async def save_mission_document(mission_id: uuid.UUID, file: UploadFile, session: AsyncSession)->MissionDocument:
    if file.content_type!="application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDFs accepted."
        )

    mission_folder=UPLOAD_DIR/str(mission_id)
    mission_folder.mkdir(parents=True, exist_ok=True)
    safe_filename=f"{uuid.uuid4()}_{file.filename}"
    file_path=mission_folder/safe_filename
    content=await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    document=MissionDocument(mission_id=mission_id, filename=file.filename, file_path=str(file_path))
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document

async def get_mission_documents(mission_id: uuid.UUID, session: AsyncSession)->list[MissionDocument]:
    result=await session.execute(select(MissionDocument).where(MissionDocument.mission_id==mission_id))
    return list(result.scalars().all())