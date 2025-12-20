from datetime import datetime, timezone
import os
from typing import Dict
from collections import defaultdict
import uuid
import base64

from dotenv import load_dotenv
from fastapi.security import api_key
from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from beanie import PydanticObjectId
from bson import ObjectId

from app.dto.base import ReponseWrapper, Participants
from app.dto.bills import (
    BillCreateIn, BillOut, BillItemOut, UserShareOut, BillUpdateIn,
    BillBalancesOut, BalanceItemOut, ListBillItemOut
)
from app.models.bills import Bills, BillItem, UserShare, BillSplitType, ItemSplitType
from app.models.events import Events
from app.utils.auth import get_current_user

load_dotenv()

router = APIRouter(prefix="/bills", tags=["Bills"])

def _parse_object_id(id_str: str) -> PydanticObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier")
    return PydanticObjectId(id_str)


def _generate_item_id() -> str:
    """Generate unique item ID"""
    return f"item_{uuid.uuid4().hex[:8]}"

def _calculate_subtotal(items: list) -> float:
    """Calculate subtotal from items (quantity * unit_price)"""
    return sum(item.get("quantity", 1) * item.get("unit_price", 0) for item in items)

def _calculate_total_amount(subtotal: float, tax: float) -> float:
    """Calculate total amount after tax"""
    return subtotal * (1 + tax / 100)


def _round_share(amount: float) -> float:
    """Round share to 2 decimal places"""
    return round(amount, 2)

def _bill_to_out(bill: Bills) -> BillOut:
    """Convert Bills model to BillOut DTO"""
    items_out = [
        BillItemOut(
            id=item.id,
            name=item.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            split_type=item.split_type,
            split_between=item.split_between
        )
        for item in bill.items
    ]
    
    shares_out = [
        UserShareOut(user_name=share.user_name, share=share.share)
        for share in bill.per_user_shares
    ]
    
    return BillOut(
        id=str(bill.id),
        owner_id=str(bill.owner_id),
        event_id=str(bill.event_id),
        title=bill.title,
        note=bill.note,
        bill_split_type=bill.bill_split_type,
        items=items_out,
        subtotal=bill.subtotal,
        tax=bill.tax,
        total_amount=bill.total_amount,
        paid_by=bill.paid_by,
        per_user_shares=shares_out
    )


async def _validate_event(event_id: str) -> Events:
    """Validate event exists and return it"""
    event = await Events.get(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def _process_by_item(payload: BillCreateIn) -> tuple[float, float, list[BillItem], list[UserShare]]:
    """Process by_item split type"""
    subtotal = _calculate_subtotal(payload.items)

    total_amount = _calculate_total_amount(subtotal, payload.tax)

    # key: stable participant identifier (user_id or name)
    user_shares: Dict[str, float] = defaultdict(float)
    participants_map: Dict[str, Participants] = {}
    tax_multiplier = 1 + payload.tax / 100
    
    bill_items = []
    for item in payload.items:
        if "split_between" not in item or not item["split_between"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item '{item.get('name', 'unknown')}' must have at least one user in split_between"
            )
        if "split_type" not in item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item '{item.get('name', 'unknown')}' must have split_type"
            )
        quantity = item.get("quantity", 1)
        unit_price = item.get("unit_price", 0)
        total_price = quantity * unit_price

        # Chuẩn hoá split_between về list[Participants]
        raw_split_between = item["split_between"]
        participants_list: list[Participants] = []
        for p in raw_split_between:
            if isinstance(p, Participants):
                participants_list.append(p)
            elif isinstance(p, dict):
                participants_list.append(Participants(**p))
            else:
                participants_list.append(Participants(name=str(p)))

        share_per_person = total_price / len(participants_list)
        for participant in participants_list:
            key = str(participant.user_id) if participant.user_id is not None else participant.name
            participants_map[key] = participant
            user_shares[key] += share_per_person

        bill_items.append(BillItem(
            id=_generate_item_id(),
            name=item["name"],
            quantity=quantity,
            unit_price=unit_price,
            total_price=_round_share(total_price),
            split_type=ItemSplitType(item["split_type"]),
            split_between=participants_list
        ))

    per_user_shares = [
        UserShare(
            user_name=participants_map[key],
            share=_round_share(share * tax_multiplier),
        )
        for key, share in user_shares.items()
    ]
    return subtotal, _round_share(total_amount), bill_items, per_user_shares


async def _process_equally(payload: BillCreateIn, event: Events) -> tuple[float, float, list[BillItem], list[UserShare]]:
    """Process equally split type"""
    if not event.participants or len(event.participants) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has no participants to split the bill"
        )

    subtotal = _calculate_subtotal(payload.items)

    total_amount = _calculate_total_amount(subtotal, payload.tax)

    share_per_person = total_amount / len(event.participants)
    per_user_shares = [
        UserShare(
            user_name=participant
            if isinstance(participant, Participants)
            else Participants(name=str(participant)),
            share=_round_share(share_per_person),
        )
        for participant in event.participants
    ]

    bill_items = [
        BillItem(
            id=_generate_item_id(),
            name=item["name"],
            quantity=item.get("quantity", 1),
            unit_price=item.get("unit_price", 0),
            total_price=_round_share(item.get("quantity", 1) * item.get("unit_price", 0)),
            split_type=None,
            split_between=None
        )
        for item in payload.items
    ]
    
    return subtotal, _round_share(total_amount), bill_items, per_user_shares


def _process_manual(payload: BillCreateIn) -> tuple[float, float, list[BillItem], list[UserShare]]:
    """Process manual split type"""
    if not payload.manual_shares:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="manual_shares is required for manual split type"
        )

    subtotal = _calculate_subtotal(payload.items)

    total_amount = _calculate_total_amount(subtotal, payload.tax)

    manual_shares_sum = sum(share.amount for share in payload.manual_shares)
    if abs(manual_shares_sum - total_amount) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sum of manual shares ({manual_shares_sum}) must equal total amount ({_round_share(total_amount)})"
        )

    per_user_shares = [
        UserShare(
            user_name=share.user_name,
            share=_round_share(share.amount),
        )
        for share in payload.manual_shares
    ]

    bill_items = [
        BillItem(
            id=_generate_item_id(),
            name=item["name"],
            quantity=item.get("quantity", 1),
            unit_price=item.get("unit_price", 0),
            total_price=_round_share(item.get("quantity", 1) * item.get("unit_price", 0)),
            split_type=None,
            split_between=None
        )
        for item in payload.items
    ]
    
    return subtotal, _round_share(total_amount), bill_items, per_user_shares

def _encode_bytes_to_base64(file_bytes):
    return base64.b64encode(file_bytes).decode('utf-8')

@router.post(
    "/",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_201_CREATED,
    description="Create a new bill with 3 split types: by_item, equally, manual",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "split_by_item": {
                            "summary": "Split by item",
                            "description": "Each item is split between specific users (Participants objects)",
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
                        "split_equally": {
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
                        "split_manually": {
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
                    }
                }
            }
        }
    }
)
async def create_bill(payload: BillCreateIn, current_user: str = Depends(get_current_user)):
    try:
        event = await _validate_event(payload.event_id)
        owner_id = _parse_object_id(current_user)

        # Map paid_by (string from client) to Participants from event, keeping user_id
        paid_by_participant: Participants | None = None
        if event.participants:
            for p in event.participants:
                # Match by user_id (as string) or by name
                if (
                    (p.user_id is not None and str(p.user_id) == payload.paid_by)
                    or p.name == payload.paid_by
                ):
                    paid_by_participant = p
                    break
        if paid_by_participant is None:
            # Fallback: create guest participant if not found in event
            paid_by_participant = Participants(name=payload.paid_by, is_guest=True)

        if payload.bill_split_type == BillSplitType.BY_ITEM:
            subtotal, total_amount, bill_items, per_user_shares = _process_by_item(payload)
        elif payload.bill_split_type == BillSplitType.EQUALLY:
            subtotal, total_amount, bill_items, per_user_shares = await _process_equally(payload, event)
        elif payload.bill_split_type == BillSplitType.MANUAL:
            subtotal, total_amount, bill_items, per_user_shares = _process_manual(payload)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bill_split_type: {payload.bill_split_type}"
            )

        new_bill = Bills(
            owner_id=owner_id,
            event_id=_parse_object_id(payload.event_id),
            title=payload.title,
            note=payload.note,
            bill_split_type=payload.bill_split_type,
            items=bill_items,
            subtotal=subtotal,
            tax=payload.tax,
            total_amount=total_amount,
            paid_by=paid_by_participant,
            per_user_shares=per_user_shares
        )
        await new_bill.insert()

        return ReponseWrapper(message="Bill created successfully", data=_bill_to_out(new_bill))
    except HTTPException:
        raise
    except Exception as e:
        raise e

@router.get(
    "/",
    response_model=ReponseWrapper[list[BillOut]],
    status_code=status.HTTP_200_OK,
    description="Get list of bills for an event"
)
async def list_bills(event_id: str, current_user: str = Depends(get_current_user)):
    try:
        event_oid = _parse_object_id(event_id)
        bills = await Bills.find({"event_id": event_oid}).to_list()
        bills_out = [_bill_to_out(bill) for bill in bills]
        return ReponseWrapper(message="Bills retrieved successfully", data=bills_out)
    except HTTPException:
        raise
    except Exception as e:
        raise e

@router.post("/uploads", response_model=ListBillItemOut, status_code=status.HTTP_200_OK, description="Upload bill image for OCR processing")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))
 
    file_bytes = await file.read()
    base_64_image = _encode_bytes_to_base64(file_bytes)
    response = client.beta.chat.completions.parse(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system", 
                "content": 
                    """
                            Bạn là hệ thống OCR chuyên trích xuất dữ liệu hóa đơn.
                            ========================
                            NGUYÊN TẮC CỐT LÕI
                            ========================
                            - KHÔNG suy luận
                            - KHÔNG phân tích
                            - KHÔNG phỏng đoán
                            - KHÔNG giải thích
                            - KHÔNG tự sửa dữ liệu nếu không có quy tắc bên dưới

                            Chỉ thực hiện:
                            - Đọc chính xác nội dung hiển thị trên hóa đơn
                            - Chuẩn hóa dữ liệu theo quy tắc được mô tả
                            - Trả về dữ liệu đúng định dạng JSON yêu cầu

                            Nếu thông tin không rõ ràng hoặc không xuất hiện:
                            - Trả về null
                            - Tuyệt đối không tự đoán

                            ========================
                            PHÁT HIỆN NGÔN NGỮ & LOCALE
                            ========================
                            - Tự động xác định NGÔN NGỮ và QUỐC GIA của hóa đơn dựa trên:
                            - Ngôn ngữ văn bản (Ví dụ: tiếng Việt, tiếng Anh)
                            - Tên sản phẩm
                            - Đơn vị tiền tệ (VND, USD, $, ₫)
                            - Định dạng giá tiền

                            ========================
                            QUY TẮC XỬ LÝ TIỀN TỆ
                            ========================

                            --- HÓA ĐƠN VIỆT NAM (Tiếng Việt / VND) ---
                            - Đơn vị tiền tệ: VND
                            - VND KHÔNG có phần thập phân
                            - Dấu "." là PHÂN CÁCH HÀNG NGHÌN
                            - Dấu "," (nếu có) cũng là phân cách hàng nghìn
                            - Khi trích xuất giá tiền:
                            - LOẠI BỎ toàn bộ dấu "." và ","
                            - Trả về SỐ NGUYÊN

                            Ví dụ:
                            - "23.674" → 23674
                            - "69.000/KG" → 69000
                            - "123.900" → 123900

                            --- HÓA ĐƠN MỸ / QUỐC TẾ (Tiếng Anh / USD) ---
                            - Đơn vị tiền tệ: USD
                            - Dấu "," là PHÂN CÁCH HÀNG NGHÌN
                            - Dấu "." là DẤU THẬP PHÂN
                            - Giữ nguyên giá trị thập phân nếu có

                            Ví dụ:
                            - "1,234.56" → 1234.56
                            - "5.99" → 5.99

                            ========================
                            QUY TẮC TÍNH TOÁN
                            ========================
                            - Nếu hóa đơn có dạng "X/KG x Y KG":
                            - totalPrice = X * Y
                            - unitPrice = totalPrice
                            - Sau khi tính toán:
                            - Làm tròn theo quy tắc của tiền tệ tương ứng
                            - VND → số nguyên
                            - USD → giữ tối đa 2 chữ số thập phân

                            ========================
                            KIỂM TRA LOGIC CƠ BẢN
                            ========================
                            - Nếu giá tiền quá nhỏ bất thường so với mặt hàng (ví dụ < 1000 VND cho thực phẩm):
                            - Kiểm tra khả năng nhầm dấu phân cách
                            - Áp dụng lại quy tắc tiền tệ theo locale

                            ========================
                            ĐỊNH DẠNG OUTPUT
                            ========================
                            - Chỉ trả về JSON hợp lệ
                            - Không thêm text giải thích
                            - Không thêm metadata
                            - Không thêm nhận xét

                            - JSON phải khớp chính xác với schema được cung cấp
                            - Không trả về danh sách trần nếu schema yêu cầu object bọc ngoài
                        """
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Trích xuất thông tin hóa đơn này."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"},
                    },
                ],
            }
        ],
        response_format=ListBillItemOut,
    )
    
    return response.choices[0].message.parsed
    
    

@router.get(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Get bill by ID"
)
async def get_bill(bill_id: str, current_user: str = Depends(get_current_user)):
    try:
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return ReponseWrapper(message="Bill retrieved successfully", data=_bill_to_out(bill))
    except HTTPException:
        raise
    except Exception as e:
        raise e



@router.put(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Update bill by ID (only title and note)"
)
async def update_bill(bill_id: str, payload: BillUpdateIn, current_user: str = Depends(get_current_user)):
    try:
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        if str(bill.owner_id) != current_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can update this bill")
        
        update_data = payload.model_dump(exclude_unset=True)
        if update_data:
            update_data["updated_at"] = datetime.now(timezone.utc)
            await bill.set(update_data)
        
        return ReponseWrapper(message="Bill updated successfully", data=_bill_to_out(bill))
    except HTTPException:
        raise
    except Exception as e:
        raise e


@router.delete(
    "/{bill_id}",
    response_model=ReponseWrapper[BillOut],
    status_code=status.HTTP_200_OK,
    description="Delete bill by ID"
)
async def delete_bill(bill_id: str, current_user: str = Depends(get_current_user)):
    try:
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        if str(bill.owner_id) != current_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete this bill")
        
        await bill.delete()
        return ReponseWrapper(message="Bill deleted successfully", data=_bill_to_out(bill))
    except HTTPException:
        raise
    except Exception as e:
        raise e



@router.get(
    "/{bill_id}/balances",
    response_model=ReponseWrapper[BillBalancesOut],
    status_code=status.HTTP_200_OK,
    description="Get bill balances - who owes whom"
)
async def get_bill_balances(bill_id: str, current_user: str = Depends(get_current_user)):
    """
    Calculate balances for a bill.
    Returns a list of debts showing who owes money to the person who paid (paidBy).
    """
    try:
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        creditor_participant = bill.paid_by

        balances = []
        for share in bill.per_user_shares:
            debtor_participant = share.user_name

            # Bỏ qua nếu debtor chính là creditor (so sánh theo user_id nếu có, fallback name)
            same_person = False
            if (
                debtor_participant.user_id is not None
                and creditor_participant.user_id is not None
                and debtor_participant.user_id == creditor_participant.user_id
            ):
                same_person = True
            elif debtor_participant.user_id is None and creditor_participant.user_id is None:
                same_person = debtor_participant.name == creditor_participant.name

            if same_person:
                continue
            
            balances.append(
                BalanceItemOut(
                    debtor=debtor_participant,
                    creditor=creditor_participant,
                    amount_owed=_round_share(share.share),
                )
            )
        
        result = BillBalancesOut(
            bill_id=str(bill.id),
            total_amount=bill.total_amount,
            balances=balances
        )
        
        return ReponseWrapper(message="Bill balances retrieved successfully", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise e
