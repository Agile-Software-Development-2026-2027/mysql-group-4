import httpx
from typing import List, Dict, Any

#URL di Nominatim, servizio di geocoding open source
NOMINATIM_URL="https://nominatim.openstreetmap.org/search"

#prende in input la query (una stringa ad esempio "Università di Padova") e restituisce una lista di dizionari con i dettagli dei luoghi trovati
async def search_locations(query: str)->List[Dict[str, Any]]:
    clean_query=query.strip()
    #ritorna lista vuota se sono state digitate solo 1 o 2 lettere
    if len(clean_query)<3:
        return []
    #definiamo l'header perché Nominatim richiede che ogni client si identifichi con un nome
    headers={"User-Agent": "MySOL-Academic-App/1.0"}
    #parametri della richiesta da inviare a Nominatim
    params={"q": clean_query, "format": "json", "addressdetails": 1, "limit": 5}
    async with httpx.AsyncClient(timeout=5.0) as client:
        response=await client.get(NOMINATIM_URL, params=params, headers=headers)
        response.raise_for_status()
        data=response.json()
    results=[]
    for d in data:
        #display name: stringa contenente nome e indirizzo da mostrare a schermo
        #lat e lon: latitudine e longitudine
        #type (opzionale): la tipologia del luogo (university, city ecc...)
        #address: opzionale, un dizionario con i dettagli di via, cap, città, nazione
        results.append({"display_name": d.get("display_name", ""), "lat": d.get("lat", ""), "lon": d.get("lon", ""), "type": d.get("type", ""), "address": d.get("address", {})})
    return results