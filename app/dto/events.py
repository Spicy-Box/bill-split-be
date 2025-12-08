from datetime import date, datetime
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from app.models.events import CurrencyEnum

class EventIn(BaseModel):
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    participants: List[str] = Field(..., description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])

class EventOut(BaseModel):
    id: PydanticObjectId = Field(..., description="Event ID", examples=["60f5f8a3b9c3f0a1b2c3d4e0"])
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    participants: List[str] = Field(..., description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])
    total_amount: float = Field(..., description="Total amount of money for the event", examples=[150.0])
    created_at: datetime = Field(..., description="Event creation time", examples=["2024-10-01T12:00:00Z"])