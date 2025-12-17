from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.dto.base import Participants


class BillSplitType(str, Enum):
    BY_ITEM = "by_item"
    EQUALLY = "equally"
    MANUAL = "manual"


class ItemSplitType(str, Enum):
    EVERYONE = "everyone"
    CUSTOM = "custom"


class BillItem(BaseModel):
    """Embedded model for bill items"""
    id: str = Field(..., description="Unique item ID")
    name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    total_price: float = Field(..., ge=0)
    split_type: Optional[ItemSplitType] = Field(default=None, description="Split type for by_item mode")
    # Store full participant info instead of just names
    split_between: Optional[List[Participants]] = Field(
        default=None,
        description="Participants who share this item",
    )


class UserShare(BaseModel):
    """Embedded model for user shares"""
    user_name: Participants = Field(..., description="User name")
    share: float = Field(..., ge=0, description="Amount user needs to pay")


class Bills(Document):
    owner_id: PydanticObjectId = Field(..., description="User ID who created the bill")
    event_id: PydanticObjectId = Field(..., description="Event this bill belongs to")
    title: str = Field(..., min_length=1, max_length=255)
    note: Optional[str] = Field(default=None, max_length=1024)
    bill_split_type: BillSplitType = Field(..., description="Type of bill split")
    items: List[BillItem] = Field(default_factory=list, description="List of bill items")
    subtotal: float = Field(..., ge=0, description="Total before tax")
    tax: float = Field(default=0, ge=0, description="Tax percentage")
    total_amount: float = Field(..., ge=0, description="Total after tax")
    paid_by: str = Field(..., description="User name who paid the bill")
    per_user_shares: List[UserShare] = Field(default_factory=list, description="Amount each user needs to pay")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "bills"
        indexes = [
            "owner_id",
            "event_id",
            IndexModel([("created_at", -1)]),
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "owner_id": "60f5f8a3b9c3f0a1b2c3d4e5",
                "event_id": "60f5f8a3b9c3f0a1b2c3d4e6",
                "title": "Nhậu quán A",
                "note": "Kèm thêm 3 món gọi thêm",
                "bill_split_type": "by_item",
                "items": [
                    {
                        "id": "item_1",
                        "name": "Lẩu cá",
                        "quantity": 1,
                        "unit_price": 300000,
                        "total_price": 300000,
                        "split_type": "everyone",
                        "split_between": ["Minh", "Hùng", "Lan", "Mai"]
                    },
                    {
                        "id": "item_2",
                        "name": "Cánh gà chiên",
                        "quantity": 2,
                        "unit_price": 120000,
                        "total_price": 240000,
                        "split_type": "custom",
                        "split_between": ["Minh", "Hùng"]
                    }
                ],
                "subtotal": 540000,
                "tax": 10,
                "total_amount": 594000,
                "paid_by": "Minh",
                "per_user_shares": [
                    {"user_name": "Minh", "share": 214500},
                    {"user_name": "Hùng", "share": 214500},
                    {"user_name": "Lan", "share": 82500},
                    {"user_name": "Mai", "share": 82500}
                ]
            }
        }
