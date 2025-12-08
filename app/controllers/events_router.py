from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from datetime import datetime, timezone

from app.models.events import Events
from app.dto.events import EventIn, EventOut
from app.dto.base import ReponseWrapper

from app.utils.auth import get_current_user

router = APIRouter(prefix='/events', tags=["Events"])

@router.post("/", response_model=ReponseWrapper[EventOut], status_code=status.HTTP_201_CREATED)
async def create_event(event_in: EventIn, current_user: str = Depends(get_current_user)):
    event = Events(
        **event_in.model_dump(),
        total_amount=0.0,
        created_at=datetime.now(timezone.utc)
    )
    await event.insert()
    event_out = EventOut(**event.model_dump())
    return ReponseWrapper(
        message="Event created successfully",
        data=event_out
    )