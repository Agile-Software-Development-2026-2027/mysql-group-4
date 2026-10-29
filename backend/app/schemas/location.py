from pydantic import BaseModel
from typing import Optional, Dict, Any

#schema Pydantic per la location.
#display name: stringa contenente nome e indirizzo da mostrare a schermo
#lat e lon: latitudine e longitudine
#type (opzionale): la tipologia del luogo (university, city ecc...)
#address: opzionale, un dizionario con i dettagli di via, cap, città, nazione
class LocationResponse(BaseModel):
    display_name: str
    lat: str
    lon: str
    type: Optional[str]=None
    address: Optional[Dict[str, Any]]=None