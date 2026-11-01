import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anyio
from app.db.mission import Mission
from app.db.mission_document import MissionDocument
from app.db.models import User

UPLOAD_DIR=Path("uploads/missions")

async def _get_mission_and_check_permission(mission_id: uuid.UUID, user: User, session: AsyncSession, action: str="read")->Mission:
    result=await session.execute(select(Mission).where(Mission.id==mission_id))
    mission=result.scalar_one_or_none()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found.",
        )
    is_requester=mission.requester_id==user.id
    is_fund_manager=getattr(mission, "fund_manager_id", None)==user.id
    is_superuser=getattr(user, "is_superuser", False)
    if action=="write":
        allowed=is_requester or is_superuser
    else:
        allowed=is_requester or is_fund_manager or is_superuser
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission.",
        )
    return mission

async def save_mission_document(mission_id: uuid.UUID, file: UploadFile, user: User, session: AsyncSession)->MissionDocument:
    await _get_mission_and_check_permission(mission_id, user, session, action="write")
    safe_original_filename=Path(file.filename).name if file.filename else "document.pdf"
    if file.content_type!="application/pdf" or not safe_original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDFs accepted."
        )
    mission_folder=UPLOAD_DIR/str(mission_id)
    mission_folder.mkdir(parents=True, exist_ok=True)
    stored_filename=f"{uuid.uuid4()}_{safe_original_filename}"
    file_path=mission_folder/stored_filename
    content=await file.read()
    async with await anyio.open_file(file_path, "wb") as f:
        await f.write(content)
    document=MissionDocument(mission_id=mission_id, filename=safe_original_filename, file_path=str(file_path))
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document

async def get_mission_documents(mission_id: uuid.UUID, user: User, session: AsyncSession)->list[MissionDocument]:
    await _get_mission_and_check_permission(mission_id, user, session, action="read")
    result=await session.execute(select(MissionDocument).where(MissionDocument.mission_id==mission_id))
    return list(result.scalars().all())