import io
import uuid
from pathlib import Path
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anyio

from app.core.config import settings
from app.db.mission import Mission
from app.db.mission_document import MissionDocument
from app.db.models import User

# Inizializzazione Client MinIO
minio_client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)


def _ensure_bucket_exists():
    """Verifica l'esistenza del bucket MinIO e lo crea se non esiste."""
    try:
        if not minio_client.bucket_exists(settings.MINIO_BUCKET_NAME):
            minio_client.make_bucket(settings.MINIO_BUCKET_NAME)
    except Exception as e:
        print(f"[MinIO] Errore verifica/creazione bucket: {e}")


# Inizializziamo il bucket all'importazione del modulo
_ensure_bucket_exists()


async def _get_mission_and_check_permission(mission_id: uuid.UUID, user: User, session: AsyncSession, action: str = "read") -> Mission:
    result = await session.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found.",
        )
    is_requester = mission.requester_id == user.id
    is_fund_manager = getattr(mission, "fund_manager_id", None) == user.id
    is_superuser = getattr(user, "is_superuser", False)
    if action == "write":
        allowed = is_requester or is_superuser
    else:
        allowed = is_requester or is_fund_manager or is_superuser
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission.",
        )
    return mission


async def save_mission_document(mission_id: uuid.UUID, file: UploadFile, user: User, session: AsyncSession) -> MissionDocument:
    await _get_mission_and_check_permission(mission_id, user, session, action="write")
    safe_original_filename = Path(file.filename).name if file.filename else "document.pdf"
    
    if file.content_type != "application/pdf" or not safe_original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDFs accepted."
        )

    # Chiave oggetto univoca dentro il bucket MinIO (es. missions/<mission_id>/<uuid>_nomefile.pdf)
    object_name = f"missions/{mission_id}/{uuid.uuid4()}_{safe_original_filename}"
    
    content = await file.read()
    file_stream = io.BytesIO(content)

    try:
        # Caricamento del file su MinIO (in un thread dedicato per non bloccare l'event loop async)
        await anyio.to_thread.run_sync(
            lambda: minio_client.put_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=object_name,
                data=file_stream,
                length=len(content),
                content_type="application/pdf"
            )
        )
    except S3Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il salvataggio su MinIO: {str(e)}"
        )

    # Salvataggio nel database (salviamo la chiave dell'oggetto MinIO nel campo file_path)
    document = MissionDocument(
        mission_id=mission_id, 
        filename=safe_original_filename, 
        file_path=object_name, 
        created_by=user.id
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def get_mission_documents(mission_id: uuid.UUID, user: User, session: AsyncSession) -> list[MissionDocument]:
    await _get_mission_and_check_permission(mission_id, user, session, action="read")
    result = await session.execute(select(MissionDocument).where(MissionDocument.mission_id == mission_id))
    return list(result.scalars().all())


async def download_mission_document(document_id: uuid.UUID, user: User, session: AsyncSession) -> tuple[bytes, str]:
    """
    Funzione helper per scaricare un documento da MinIO restituendo i byte e il nome originale.
    """
    result = await session.execute(select(MissionDocument).where(MissionDocument.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    await _get_mission_and_check_permission(document.mission_id, user, session, action="read")

    try:
        response = await anyio.to_thread.run_sync(
            lambda: minio_client.get_object(settings.MINIO_BUCKET_NAME, document.file_path)
        )
        content = response.read()
        response.close()
        response.release_conn()
        return content, document.filename
    except S3Error as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Impossibile recuperare il file da MinIO: {str(e)}"
        )