from datetime import datetime

from pydantic import BaseModel


class ServiceError(BaseModel):
    timestamp: datetime
    url: str
    message: str
