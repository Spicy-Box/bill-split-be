from typing import List, Optional, Union, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator

from app.dto.base import Participants
from app.models.bills import BillSplitType, ItemSplitType

class ManualShareIn(BaseModel):
    """Manual share input"""
    user_name: str = Field(..., examples=["Minh"])
    amount: float = Field(..., ge=0, examples=[10.0])


class BillCreateIn(BaseModel):
    """Unified input for creating bill - supports all 3 split types"""
    event_id: str = Field(..., examples=["60f5f8a3b9c3f0a1b2c3d4e5"])
    title: str = Field(..., min_length=1, max_length=255, examples=["Nhậu quán A"])
    note: Optional[str] = Field(default=None, max_length=1024, examples=["Kèm thêm 3 món gọi thêm"])
    bill_split_type: BillSplitType = Field(..., examples=["by_item"])
    items: List[dict] = Field(..., min_length=1, description="List of items - structure depends on bill_split_type")
    tax: float = Field(default=0, ge=0, examples=[10])
    paid_by: str = Field(..., examples=["Minh"])
    manual_shares: Optional[List[ManualShareIn]] = Field(default=None, description="Required for manual split type")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "Split by item",
                    "description": "Each item is split between specific users",
                    "value": {
                        "event_id": "69383ff5d1b5eaf8f4a83136",
                        "title": "Nhậu quán A",
                        "note": "Kèm thêm 3 món gọi thêm",
                        "bill_split_type": "by_item",
                        "items": [
                            {
                                "name": "Lẩu cá",
                                "quantity": 1,
                                "unit_price": 300000,
                                "split_type": "everyone",
                                "split_between": [
                                    {"name": "Minh", "user_id": None, "is_guest": True},
                                    {"name": "Hùng", "user_id": None, "is_guest": True},
                                    {"name": "Lan", "user_id": None, "is_guest": True},
                                    {"name": "Mai", "user_id": None, "is_guest": True}
                                ]
                            },
                            {
                                "name": "Cánh gà chiên",
                                "quantity": 2,
                                "unit_price": 120000,
                                "split_type": "custom",
                                "split_between": [
                                    {"name": "Minh", "user_id": None, "is_guest": True},
                                    {"name": "Hùng", "user_id": None, "is_guest": True}
                                ]
                            },
                            {
                                "name": "Mì bò",
                                "quantity": 3,
                                "unit_price": 100000,
                                "split_type": "custom",
                                "split_between": [
                                    {"name": "Lan", "user_id": None, "is_guest": True}
                                ]
                            }
                        ],
                        "tax": 10,
                        "paid_by": "Minh"
                    }
                },
                {
                    "summary": "Split equally",
                    "description": "Bill is split equally among all event participants",
                    "value": {
                        "event_id": "69383ff5d1b5eaf8f4a83136",
                        "title": "Pizza Night",
                        "bill_split_type": "equally",
                        "items": [
                            {
                                "name": "Large Pizza",
                                "quantity": 2,
                                "unit_price": 15.0
                            },
                            {
                                "name": "Special Pizza",
                                "quantity": 3,
                                "unit_price": 30.0
                            }
                        ],
                        "tax": 8,
                        "paid_by": "John"
                    }
                },
                {
                    "summary": "Split manually",
                    "description": "Custom amounts for each user",
                    "value": {
                        "event_id": "69383ff5d1b5eaf8f4a83136",
                        "title": "Coffee Shop",
                        "bill_split_type": "manual",
                        "items": [
                            {
                                "name": "Latte",
                                "quantity": 3,
                                "unit_price": 5.0
                            }
                        ],
                        "tax": 0,
                        "paid_by": "Alice",
                        "manual_shares": [
                            {"user_name": "Alice", "amount": 10.0},
                            {"user_name": "Bob", "amount": 5.0}
                        ]
                    }
                }
            ]
        }



class BillItemOut(BaseModel):
    """Item output"""
    id: str
    name: str
    quantity: int
    unit_price: float = Field(..., serialization_alias="unitPrice")
    total_price: float = Field(..., serialization_alias="totalPrice")
    split_type: Optional[ItemSplitType] = Field(default=None, serialization_alias="splitType")
    # Trả ra đầy đủ thông tin người tham gia cho từng item
    split_between: Optional[List[Participants]] = Field(
        default=None,
        serialization_alias="splitBetween",
    )

    class Config:
        populate_by_name = True


class UserShareOut(BaseModel):
    """User share output"""
    user_name: Participants = Field(..., serialization_alias="userName")
    share: float

    class Config:
        populate_by_name = True


class BillOut(BaseModel):
    """Bill output"""
    id: str
    owner_id: str = Field(..., serialization_alias="ownerId")
    event_id: str = Field(..., serialization_alias="eventId")
    title: str
    note: Optional[str] = None
    bill_split_type: BillSplitType = Field(..., serialization_alias="billSplitType")
    items: List[BillItemOut]
    subtotal: float
    tax: float
    total_amount: float = Field(..., serialization_alias="totalAmount")
    paid_by: str = Field(..., serialization_alias="paidBy")
    per_user_shares: List[UserShareOut] = Field(..., serialization_alias="perUserShares")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "60f5f8a3b9c3f0a1b2c3d4e0",
                "ownerId": "60f5f8a3b9c3f0a1b2c3d4e5",
                "eventId": "60f5f8a3b9c3f0a1b2c3d4e6",
                "title": "Nhậu quán A",
                "note": "Kèm thêm 3 món gọi thêm",
                "billSplitType": "by_item",
                "items": [
                    {
                        "id": "item_1",
                        "name": "Lẩu cá",
                        "quantity": 1,
                        "unitPrice": 300000,
                        "totalPrice": 300000,
                        "splitType": "everyone",
                        "splitBetween": ["Minh", "Hùng", "Lan", "Mai"]
                    },
                    {
                        "id": "item_2",
                        "name": "Cánh gà chiên",
                        "quantity": 2,
                        "unitPrice": 120000,
                        "totalPrice": 240000,
                        "splitType": "custom",
                        "splitBetween": ["Minh", "Hùng"]
                    },
                    {
                        "id": "item_3",
                        "name": "Trà đào",
                        "quantity": 3,
                        "unitPrice": 30000,
                        "totalPrice": 90000,
                        "splitType": "custom",
                        "splitBetween": ["Lan"]
                    }
                ],
                "subtotal": 630000,
                "tax": 10,
                "totalAmount": 693000,
                "paidBy": "Minh",
                "perUserShares": [
                    {"userName": "Minh", "share": 214500},
                    {"userName": "Hùng", "share": 214500},
                    {"userName": "Lan", "share": 181500},
                    {"userName": "Mai", "share": 82500}
                ]
            }
        }



class BillUpdateIn(BaseModel):
    """Bill update input"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    note: Optional[str] = Field(default=None, max_length=1024)


class BalanceItemOut(BaseModel):
    """Single balance item - who owes whom"""
    debtor: str = Field(..., description="User name who owes money")
    creditor: str = Field(..., description="User name who is owed money")
    amount_owed: float = Field(..., ge=0, serialization_alias="amountOwed", description="Amount owed")

    class Config:
        populate_by_name = True


class BillBalancesOut(BaseModel):
    """Bill balances output"""
    bill_id: str = Field(..., serialization_alias="billId")
    total_amount: float = Field(..., serialization_alias="totalAmount")
    balances: List[BalanceItemOut]

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "billId": "69393f756bc02287fdddf882",
                "totalAmount": 924000,
                "balances": [
                    {
                        "debtor": "Hùng",
                        "creditor": "Minh",
                        "amountOwed": 214500
                    },
                    {
                        "debtor": "Lan",
                        "creditor": "Minh",
                        "amountOwed": 412500
                    },
                    {
                        "debtor": "Mai",
                        "creditor": "Minh",
                        "amountOwed": 82500
                    }
                ]
            }
        }
