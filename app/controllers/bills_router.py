from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId
from bson import ObjectId

from app.dto.base import ReponseWrapper
from app.dto.bills import BillIn, BillOut, BillUpdate
from app.models.bills import Bills
from app.utils.auth import get_current_user


router = APIRouter(prefix="/bills", tags=["Bills"])


def _parse_object_id(id_str: str) -> PydanticObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier")
    return PydanticObjectId(id_str)


def _ensure_bill_access(bill: Bills, current_user_id: PydanticObjectId) -> None:
    if bill.owner_id != current_user_id and current_user_id not in bill.participants:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this bill")


@router.get(
    "/",
    response_model=ReponseWrapper[List[BillOut]],
    status_code=status.HTTP_200_OK,
    description="Get list of bills for current user",
)
async def list_bills(current_user: str = Depends(get_current_user)):
    user_id = _parse_object_id(current_user)
    bills = await Bills.find(
        {
            "$or": [
                {"owner_id": user_id},
                {"participants": user_id},
            ]
        }
    ).to_list()
    return ReponseWrapper(message="Bills retrieved successfully", data=bills)


@router.get(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Get bill by ID",
)
async def get_bill(bill_id: str, current_user: str = Depends(get_current_user)):
    user_id = _parse_object_id(current_user)
    bill = await Bills.get(bill_id)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    _ensure_bill_access(bill, user_id)
    return ReponseWrapper(message="Bill retrieved successfully", data=bill)


@router.post(
    "/",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_201_CREATED,
    description="Create a new bill",
)
async def create_bill(payload: BillIn, current_user: str = Depends(get_current_user)):
    owner_id = _parse_object_id(current_user)
    new_bill = Bills(owner_id=owner_id, **payload.model_dump())
    await new_bill.insert()
    return ReponseWrapper(message="Bill created successfully", data=new_bill)


@router.put(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Update bill by ID",
)
async def update_bill(bill_id: str, payload: BillUpdate, current_user: str = Depends(get_current_user)):
    owner_id = _parse_object_id(current_user)
    bill = await Bills.get(bill_id)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    if bill.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can update this bill")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await bill.set(update_data)

    return ReponseWrapper(message="Bill updated successfully", data=bill)


@router.delete(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Delete bill by ID",
)
async def delete_bill(bill_id: str, current_user: str = Depends(get_current_user)):
    owner_id = _parse_object_id(current_user)
    bill = await Bills.get(bill_id)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    if bill.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete this bill")

    await bill.delete()
    return ReponseWrapper(message="Bill deleted successfully", data=bill)