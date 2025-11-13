from datetime import date, datetime, timezone
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel


class Bills(Document):
    owner_id: PydanticObjectId = Field(..., description="User who created the bill")
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    total_amount: float = Field(..., ge=0)
    due_date: Optional[date] = Field(default=None)
    participants: List[PydanticObjectId] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "bills"
        indexes = [
            "owner_id",
            IndexModel([("participants", 1)]),
            IndexModel([("due_date", 1)]),
        ]

    class Config:
        json_schema_extra = {
            "example": {
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