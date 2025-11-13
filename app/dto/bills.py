from datetime import date
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field


class BillIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, examples=["Weekend trip"])
    description: Optional[str] = Field(default=None, max_length=1024, examples=["Shared Airbnb and groceries"])
    total_amount: float = Field(..., ge=0, examples=[240.75])
    due_date: Optional[date] = Field(default=None, examples=["2024-12-01"])
    participants: List[PydanticObjectId] = Field(default_factory=list, examples=[["60f5f8a3b9c3f0a1b2c3d4e5"]])


class BillUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255, examples=["Updated trip name"])
    description: Optional[str] = Field(default=None, max_length=1024, examples=["Updated description"])
    total_amount: Optional[float] = Field(default=None, ge=0, examples=[260.0])
    due_date: Optional[date] = Field(default=None, examples=["2024-12-15"])
    participants: Optional[List[PydanticObjectId]] = Field(default=None, examples=[["60f5f8a3b9c3f0a1b2c3d4e5"]])


class BillOut(BaseModel):
    id: PydanticObjectId
    owner_id: PydanticObjectId
    title: str
    description: Optional[str]
    total_amount: float
    due_date: Optional[date]
    participants: List[PydanticObjectId]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "60f5f8a3b9c3f0a1b2c3d4e0",
                "owner_id": "60f5f8a3b9c3f0a1b2c3d4e5",
                "title": "Weekend trip",
                "description": "Shared Airbnb and groceries",
                "total_amount": 240.75,
                "due_date": "2024-12-01",
                "participants": [
                    "60f5f8a3b9c3f0a1b2c3d4e5",
                    "60f5f8a3b9c3f0a1b2c3d4e6",
                ],
            }
        }

