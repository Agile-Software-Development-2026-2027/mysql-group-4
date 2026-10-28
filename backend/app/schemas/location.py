from pydantic import BaseModel
from typing import Optional, Dict, Any

#schema Pydantic per la location. Per la spiegazione dettagliata dei campi vai in backend\app\services\geocoding.py
class LocationResponse(BaseModel):
    display_name: str
    lat: str
    lon: str
    type: Optional[str]=None
    address: Optional[Dict[str, Any]]=None