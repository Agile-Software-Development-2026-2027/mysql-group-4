from fastapi import APIRouter, Query, HTTPException, status
from typing import List
from app.schemas.location import LocationResponse
from app.services.geocoding import search_locations

router=APIRouter(prefix="/locations", tags=["locations"])

@router.get("/autocomplete", response_model=List[LocationResponse], status_code=status.HTTP_200_OK)

async def autocomplete_location(q: str=Query(..., min_length=3, description="description_text")):
    try:
        results=await search_locations(q)
        return results
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="detail_text")