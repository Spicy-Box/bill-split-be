from datetime import date, datetime, timezone
from typing import List, Optional
from enum import IntEnum

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel

class CurrencyEnum(IntEnum):
    VND = 1
    USD = 2
    JPY = 3

class Events(Document):
    name: str = Field(..., description="Name of the event")
    currency: CurrencyEnum = Field(..., description="Currency type for the event")
    participants: list[str] = Field(..., description="List of participant name")
    total_amount: float = Field(..., ge=0, description="Total amount of money for the event")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "events"