from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from datetime import datetime, timezone
from bson import ObjectId

from app.models.events import Events
from app.models.users import User
from app.models.bills import Bills
from app.dto.events import EventIn, EventOut, EventsOut, EventDetailOut, EventUpdate
from app.dto.base import ReponseWrapper

from app.utils.auth import get_current_user

router = APIRouter(prefix='/events', tags=["Events"])

@router.post("/", response_model=ReponseWrapper[EventOut], status_code=status.HTTP_201_CREATED)
async def create_event(event_in: EventIn, current_user: str = Depends(get_current_user)):
    try:
        user = await User.get(current_user)
        
        event_in.participants.append(user.first_name)
        event = Events(
            **event_in.model_dump(),
            creator=user.id,    
            total_amount=0.0,
            created_at=datetime.now(timezone.utc)
        )
        await event.insert()

        event_out = EventOut(
            **event.model_dump(),
            totalAmount= event.total_amount,
            createdAt= event.created_at
            )
        return ReponseWrapper(
            message="Event created successfully",
            data=event_out
        )
    except Exception as e:
        raise e
    
@router.get("/", response_model=ReponseWrapper[List[EventsOut]], status_code=status.HTTP_200_OK)
async def find_events(current_user: str = Depends(get_current_user)):
    try:
        list_events = await Events.find_all().to_list()
        result = [EventsOut(
            **e.model_dump(),
            participantsCount= len(e.participants),
            totalAmount= e.total_amount,
            createdAt=e.created_at
            ) for e in list_events]

        return ReponseWrapper(
            message="Get all events successfully",
            data=result
        )
    except Exception as e:
        raise e
    
@router.get("/{event_id}", response_model=ReponseWrapper[EventDetailOut], status_code=status.HTTP_200_OK)
async def find_detail_event(event_id: str ,current_user: str = Depends(get_current_user)):
    try:
        event = await Events.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        result = EventDetailOut(
            **event.model_dump(),
            createdAt=event.created_at,
            totalAmount=event.total_amount
        )
        return ReponseWrapper(message="Find event successfully", data=result)
    except Exception as e:
        raise e
    
@router.patch("/{event_id}", response_model=ReponseWrapper[EventDetailOut], status_code=status.HTTP_200_OK)
async def path_event(event_id: str ,event_in: EventUpdate ,current_user: str = Depends(get_current_user)):
    try:
        event = await Events.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        update_data = event_in.model_dump(exclude_unset=True)
        if update_data:
            await event.set(update_data)

        event_out = EventDetailOut(
            **event.model_dump(),
            totalAmount= event.total_amount,
            createdAt= event.created_at
        )
        return ReponseWrapper(
            message="Event updated successfully",
            data=event_out
        )
    except Exception as e:
        raise e
    
@router.delete("/{event_id}", response_model=ReponseWrapper[dict], status_code=status.HTTP_200_OK)
async def delete_event(event_id: str, current_user: str = Depends(get_current_user)):
    try:
        event = await Events.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        result = await event.delete()
        return ReponseWrapper(
            message="Delete event successfully",
            data={}
        )
    except Exception as e:
        raise e

@router.post("/add-bill/", response_model=ReponseWrapper[EventDetailOut], status_code=status.HTTP_200_OK)
async def add_bill_to_event(event_id: str, bill_id: str, current_user: str = Depends(get_current_user)):
    try:
        event = await Events.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")   
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        checking = await Events.find_one(
            {"bills._id": ObjectId(bill_id)}
        )
        if checking:
            raise HTTPException(status_code=400, detail="Bill already in event")
        
        
        event.bills.append(bill)
        await event.save()
        result = EventDetailOut(
            **event.model_dump(),
            totalAmount= event.total_amount,
            createdAt= event.created_at
        )
        return ReponseWrapper(
            message="Bill added to event successfully",
            data=result
        )
    except Exception as e:
        raise e