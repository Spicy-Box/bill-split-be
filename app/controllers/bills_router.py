from datetime import datetime, timezone
import os
from typing import Dict
from collections import defaultdict
import uuid
import base64
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi.security import api_key
from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import StreamingResponse
from beanie import PydanticObjectId
from bson import ObjectId

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.dto.base import ReponseWrapper, Participants
from app.dto.bills import (
    BillCreateIn, BillOut, BillItemOut, UserShareOut, BillUpdateIn,
    BillBalancesOut, BalanceItemOut, ListBillItemOut
)
from app.models.bills import Bills, BillItem, UserShare, BillSplitType, ItemSplitType
from app.models.events import Events, CurrencyEnum
from app.utils.auth import get_current_user

load_dotenv()

router = APIRouter(prefix="/bills", tags=["Bills"])

PDF_FONT_NAME = "DivvyUnicode"
_FONT_REGISTERED = False


def _candidate_font_paths() -> list[Path]:
    """Possible font files that support extended Latin/Vietnamese characters."""
    base_dir = Path(__file__).resolve().parent.parent
    print(base_dir)
    return [
        base_dir / "assets" / "fonts" / "DejaVuSans.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]


def _ensure_unicode_font() -> str:
    """Register a Unicode-capable font with ReportLab once and reuse it."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED and PDF_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return PDF_FONT_NAME

    for path in _candidate_font_paths():
        if path.exists():
            pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, str(path)))
            _FONT_REGISTERED = True
            return PDF_FONT_NAME

    return "Helvetica"


def _participant_key(participant: Participants) -> str:
    if participant.user_id is not None:
        return str(participant.user_id)
    return participant.name


def _participant_display(participant: Participants) -> str:
    suffix = " (Guest)" if participant.is_guest else ""
    return f"{participant.name}{suffix}"


def _get_currency_meta(currency: CurrencyEnum) -> dict:
    mapping = {
        CurrencyEnum.VND: {"code": "VND", "symbol": "₫", "precision": 0},
        CurrencyEnum.USD: {"code": "USD", "symbol": "$", "precision": 2},
        CurrencyEnum.JPY: {"code": "JPY", "symbol": "¥", "precision": 0},
    }
    return mapping.get(currency, {"code": "VND", "symbol": "₫", "precision": 0})


def _format_currency(amount: float, currency: CurrencyEnum) -> str:
    meta = _get_currency_meta(currency)
    precision = meta["precision"]
    if precision == 0:
        formatted = f"{amount:,.0f}"
    else:
        formatted = f"{amount:,.{precision}f}"
    return f"{formatted} {meta['symbol']}"


def _get_split_type_label(split_type: BillSplitType) -> str:
    labels = {
        BillSplitType.BY_ITEM: "Split by Items",
        BillSplitType.EQUALLY: "Split Equally",
        BillSplitType.MANUAL: "Manual Input",
    }
    return labels.get(split_type, split_type.value)


def _calculate_tax_amount(bill: Bills) -> float:
    return round(bill.subtotal * (bill.tax / 100), 2)


def _is_same_participant(a: Participants, b: Participants) -> bool:
    if a.user_id is not None and b.user_id is not None:
        return a.user_id == b.user_id
    if a.user_id is None and b.user_id is None:
        return a.name == b.name
    return False


def _calculate_balances_for_bill(bill: Bills) -> BillBalancesOut:
    creditor = bill.paid_by
    balances: list[BalanceItemOut] = []
    for share in bill.per_user_shares:
        debtor = share.user_name
        if _is_same_participant(debtor, creditor):
            continue
        balances.append(
            BalanceItemOut(
                debtor=debtor,
                creditor=creditor,
                amount_owed=_round_share(share.share),
            )
        )

    return BillBalancesOut(
        bill_id=str(bill.id),
        total_amount=bill.total_amount,
        balances=balances,
    )


def _build_item_detail_map(bill: Bills) -> Dict[str, list[str]]:
    details: Dict[str, list[str]] = defaultdict(list)
    for item in bill.items:
        if not item.split_between:
            continue
        participant_count = len(item.split_between)
        for participant in item.split_between:
            key = _participant_key(participant)
            label = f"{item.name} (1/{participant_count} share)"
            details[key].append(label)
    return details


def _detail_for_share(bill: Bills, share: UserShare, item_detail_map: Dict[str, list[str]]) -> str:
    if bill.bill_split_type == BillSplitType.BY_ITEM:
        key = _participant_key(share.user_name)
        entries = item_detail_map.get(key)
        if entries:
            return ", ".join(entries)
        return "Shared specific items"
    if bill.bill_split_type == BillSplitType.EQUALLY:
        return "Split evenly across participants"
    return "Manual allocation"


def _build_bill_pdf(bill: Bills, event: Events, balances: BillBalancesOut) -> BytesIO:
    buffer = BytesIO()
    font_name = _ensure_unicode_font()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Divvy Bill {bill.title}",
        author="Divvy",
    )

    base_style = ParagraphStyle(
        name="DivvyBase",
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2C3E50"),
    )
    app_style = ParagraphStyle(
        name="DivvyApp", parent=base_style, fontSize=9, textColor=colors.HexColor("#95A5A6"))
    heading_style = ParagraphStyle(
        name="DivvyHeading", parent=base_style, fontSize=18, spaceAfter=4, spaceBefore=4, fontName=font_name)
    sub_heading_style = ParagraphStyle(
        name="DivvySubHeading", parent=base_style, fontSize=11, textColor=colors.HexColor("#7F8C8D"), spaceAfter=12)
    section_style = ParagraphStyle(
        name="DivvySection", parent=base_style, fontSize=14, spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#2C3E50"))

    currency = event.currency if event else CurrencyEnum.VND
    currency_meta = _get_currency_meta(currency)
    tax_amount = _calculate_tax_amount(bill)
    generated_at = datetime.now(timezone.utc).astimezone()

    formatted_date = generated_at.strftime("%d %b %Y • %I:%M %p")

    elements = []

    elements.append(Paragraph("Divvy", app_style))
    elements.append(Paragraph("Bill Receipt", heading_style))
    elements.append(Paragraph(f"Ref ID: #{str(bill.id)[-8:].upper()}", sub_heading_style))

    info_rows = [
        ["Bill Title", bill.title],
        ["Event", getattr(event, "name", "-")],
        ["Date", formatted_date],
        ["Currency", f"{currency_meta['code']} ({currency_meta['symbol']})"],
        ["Split Method", _get_split_type_label(bill.bill_split_type)],
    ]
    if bill.note:
        info_rows.append(["Note", bill.note])

    info_table = Table(info_rows, hAlign="LEFT", colWidths=[40 * mm, 100 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#7F8C8D")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#2C3E50")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("padding", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Receipt Details", section_style))
    
    items_data = [["Item Name", "Qty", "Price", "Total"]]
    for item in bill.items:
        items_data.append([
            item.name,
            f"x{item.quantity}",
            _format_currency(item.unit_price, currency),
            _format_currency(item.total_price, currency),
        ])

    items_table = Table(items_data, hAlign="LEFT", colWidths=[85 * mm, 20 * mm, 35 * mm, 40 * mm])
    items_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ECF0F1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9F9")]),
    ]))
    elements.append(items_table)


    summary_data = [
        ["Subtotal", _format_currency(bill.subtotal, currency)],
    ]
    if tax_amount > 0:
        tax_percent = int(bill.tax) if bill.tax.is_integer() else bill.tax
        summary_data.append([f"Tax ({tax_percent}%)", _format_currency(tax_amount, currency)])
    summary_data.append(["TOTAL", _format_currency(bill.total_amount, currency)])

    summary_table = Table(summary_data, hAlign="RIGHT", colWidths=[40 * mm, 40 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, -2), colors.HexColor("#7F8C8D")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (1, -1), (1, -1), colors.HexColor("#C0392B")),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("FONTNAME", (0, -1), (-1, -1), font_name),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(Spacer(1, 4))
    elements.append(summary_table)

    elements.append(Spacer(1, 10))

    payer_name = _participant_display(bill.paid_by)
    paid_by_data = [[f"PAID BY", payer_name]]
    paid_by_table = Table(paid_by_data, hAlign="LEFT", colWidths=[30 * mm, 150 * mm])
    paid_by_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF9E7")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F1C40F")),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#F39C12")),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#2C3E50")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("PADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
    ]))
    elements.append(paid_by_table)

    elements.append(Paragraph("Participant Shares", section_style))
    elements.append(Paragraph("Tax included", sub_heading_style))
    detail_map = _build_item_detail_map(bill)
    breakdown_rows = [["Member", "Share Amount", "Allocation Details"]]
    
    if bill.per_user_shares:
        for share in bill.per_user_shares:
            breakdown_rows.append([
                _participant_display(share.user_name),
                _format_currency(share.share, currency),
                _detail_for_share(bill, share, detail_map),
            ])
    else:
        breakdown_rows.append(["-", "-", "No participants"])

    breakdown_table = Table(breakdown_rows, hAlign="LEFT", colWidths=[50 * mm, 35 * mm, 95 * mm])
    breakdown_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16A085")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAFAF1")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DBDB")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(breakdown_table)

    elements.append(Paragraph("Who owes whom?", section_style))

    if balances.balances:
        settlement_data = [["Debtor (From)", "", "Creditor (To)", "Amount"]]
        for balance in balances.balances:
            settlement_data.append([
                _participant_display(balance.debtor),
                "→",
                _participant_display(balance.creditor),
                _format_currency(balance.amount_owed, currency)
            ])
        
        settlement_table = Table(settlement_data, hAlign="LEFT", colWidths=[55 * mm, 15 * mm, 55 * mm, 55 * mm])
        settlement_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), font_name),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#7F8C8D")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#BDC3C7")),

            ("FONTNAME", (0, 1), (-1, -1), font_name),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 8),

            ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#C0392B")),
            ("FONTSIZE", (3, 1), (3, -1), 11),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FDEDEC")]),
        ]))
        elements.append(settlement_table)
    else:
        elements.append(Table(
            [[Paragraph("✅ Everyone is settled up for this bill.", base_style)]],
            colWidths=[180*mm],
            style=[
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EAFAF1")),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("PADDING", (0,0), (-1,-1), 12),
                ("BOX", (0,0), (-1,-1), 1, colors.HexColor("#2ECC71"))
            ]
        ))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Exported by Divvy App on {formatted_date}", app_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def _parse_object_id(id_str: str) -> PydanticObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier")
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
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
            key = str(
                participant.user_id) if participant.user_id is not None else participant.name
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
            total_price=_round_share(
                item.get("quantity", 1) * item.get("unit_price", 0)),
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
            total_price=_round_share(
                item.get("quantity", 1) * item.get("unit_price", 0)),
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
                                            {"name": "Minh", "user_id": None,
                                                "is_guest": True},
                                            {"name": "Hùng", "user_id": None,
                                                "is_guest": True},
                                            {"name": "Lan", "user_id": None,
                                                "is_guest": True},
                                            {"name": "Mai", "user_id": None,
                                                "is_guest": True}
                                        ]
                                    },
                                    {
                                        "name": "Cánh gà chiên",
                                        "quantity": 2,
                                        "unit_price": 120000,
                                        "split_type": "custom",
                                        "split_between": [
                                            {"name": "Minh", "user_id": None,
                                                "is_guest": True},
                                            {"name": "Hùng", "user_id": None,
                                                "is_guest": True}
                                        ]
                                    },
                                    {
                                        "name": "Mì bò",
                                        "quantity": 3,
                                        "unit_price": 100000,
                                        "split_type": "custom",
                                        "split_between": [
                                            {"name": "Lan", "user_id": None,
                                                "is_guest": True}
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
            paid_by_participant = Participants(
                name=payload.paid_by, is_guest=True)

        if payload.bill_split_type == BillSplitType.BY_ITEM:
            subtotal, total_amount, bill_items, per_user_shares = _process_by_item(
                payload)
        elif payload.bill_split_type == BillSplitType.EQUALLY:
            subtotal, total_amount, bill_items, per_user_shares = await _process_equally(payload, event)
        elif payload.bill_split_type == BillSplitType.MANUAL:
            subtotal, total_amount, bill_items, per_user_shares = _process_manual(
                payload)
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

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        if str(bill.owner_id) != current_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the owner can update this bill")

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        if str(bill.owner_id) != current_user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the owner can delete this bill")

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        result = _calculate_balances_for_bill(bill)

        return ReponseWrapper(message="Bill balances retrieved successfully", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise e


@router.get(
    "/{bill_id}/export-pdf",
    status_code=status.HTTP_200_OK,
    description="Export bill as a professionally formatted PDF invoice",
    response_class=StreamingResponse,
)
async def export_bill_pdf(bill_id: str, current_user: str = Depends(get_current_user)):
    try:
        bill = await Bills.get(bill_id)
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

        event = await Events.get(bill.event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Event not found for bill")

        balances = _calculate_balances_for_bill(bill)
        pdf_stream = _build_bill_pdf(bill, event, balances)

        filename = f"Divvy_Bill_{bill.id}.pdf"
        headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
        return StreamingResponse(pdf_stream, media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        raise e
