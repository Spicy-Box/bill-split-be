from datetime import date, datetime
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from app.models.events import CurrencyEnum
from app.models.bills import Bills

class EventIn(BaseModel):
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    # description: str = Field(..., description="Description of event", examples=["Đi nhậu cuối tuần"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    participants: List[str] = Field(..., description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])

class EventOut(BaseModel):
    id: PydanticObjectId = Field(..., description="Event ID", examples=["60f5f8a3b9c3f0a1b2c3d4e0"])
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    participants: List[str] = Field(..., description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])
    totalAmount: float = Field(..., description="Total amount of money for the event", examples=[150.0])
    createdAt: datetime = Field(..., description="Event creation time", examples=["2024-10-01T12:00:00Z"])

class EventsOut(BaseModel):
    id: PydanticObjectId = Field(..., description="Event ID", examples=["60f5f8a3b9c3f0a1b2c3d4e0"])
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    participantsCount: int = Field(..., description="Amount of participant in the event", examples=[4])
    totalAmount: float = Field(..., description="Total amount of money for the event", examples=[150.0])
    createdAt: datetime = Field(..., description="Event creation time", examples=["2024-10-01T12:00:00Z"])

class EventDetailOut(BaseModel):
    id: PydanticObjectId = Field(..., description="Event ID", examples=["60f5f8a3b9c3f0a1b2c3d4e0"])
    name: str = Field(..., description="Name of the event", examples=["Birthday Party"])
    description: str = Field(..., description="Description of the event", examples=["Đi nhậu cuối tuần"])
    currency: CurrencyEnum = Field(..., description="Currency type for the event", examples=[1])
    createdAt: datetime = Field(..., description="Event creation time", examples=["2024-10-01T12:00:00Z"])
    participants: List[str] = Field(..., description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])
    bills: list[Bills] = Field(default_factory=list, description="Bills in event")
    totalAmount: float = Field(..., description="Total amount of money for the event", examples=[150.0])

class EventUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of the event", examples=["Birthday Party"])
    currency: Optional[CurrencyEnum] = Field(default=None, description="Currency type for the event", examples=[1])
    description: Optional[str] = Field(default=None, description="Description of the event", examples=["Đi nhậu cuối tuần"])
    participants: Optional[list[str]] = Field(default=None, description="List of participant name", examples=[["Alice", "Bob", "Charlie"]])
    totalAmount: Optional[float] = Field(default=None, description="Total amount of money for the event", examples=[150.0])