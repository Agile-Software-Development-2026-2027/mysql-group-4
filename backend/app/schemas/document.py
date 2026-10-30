from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID

#schema pydantic per formattare json da inviare al frontend quando si richiedono i metadati dei file allegati
class MissionDocumentResponse(BaseModel):
    id: UUID
    mission_id: UUID
    filename: str
    uploaded_at: datetime
    model_config=ConfigDict(from_attributes=True)