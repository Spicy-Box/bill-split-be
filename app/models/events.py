from datetime import date, datetime, timezone
from typing import List, Optional
from enum import IntEnum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel
from app.models.bills import Bills

class CurrencyEnum(IntEnum):
    VND = 1
    USD = 2
    JPY = 3

class Events(Document):
    name: str = Field(..., description="Name of the event")
    currency: CurrencyEnum = Field(..., description="Currency type for the event")
    creator: PydanticObjectId = Field(..., description="Creator of the events")
    description: str = Field(..., description="Description of event")
    participants: list[str] = Field(..., description="List of participant name")
    total_amount: float = Field(..., ge=0, description="Total amount of money for the event")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bills: list[Bills] = Field(default_factory=list, description="Bills in event")

    class Settings:
        name = "events"