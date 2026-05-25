<<<<<<< HEAD
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import Client, GstFiling, User, WhatsappMessage
from auth import admin_or_employee
from routes.whatsapp import send_whatsapp_message
from typing import List, Optional
from datetime import datetime

from gst_scraper import (
    start_gst_search,
    submit_captcha_and_scrape
)

router = APIRouter(tags=["GST"])


class GstCaptchaRequest(BaseModel):
    gstin: str


class VerifyCaptchaRequest(BaseModel):
    session_id: str
    captcha_text: str


class GstFilingUpdatePayload(BaseModel):
    client_id: int
    financial_year: str
    month: str
    return_type: str
    filing_status: str
    filing_date: Optional[str] = None
    extend_date: Optional[str] = None


class GstRemindPayload(BaseModel):
    client_ids: List[int]
    message_template: str


@router.post("/gst/get-captcha")
async def get_captcha(
    request: GstCaptchaRequest
):
    try:

        result = await start_gst_search(
            request.gstin
        )

        return {
            "success": True,

            "session_id":
                result["session_id"],

            "captcha_image":
                result["captcha_image"],

            "captcha_path":
                result.get(
                    "captcha_path"
                )
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/gst/verify")
async def verify_captcha(
    request: VerifyCaptchaRequest
):
    try:

        scraped_data = await submit_captcha_and_scrape(
            request.session_id,
            request.captcha_text
        )

        return {
            "success": True,
            "data": scraped_data
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Verification failed: {str(e)}"
        )


@router.get("/gst/filings", response_model=List[dict])
def get_gst_filings(
    financial_year: str,
    month: str,
    return_type: str,
    filing_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee)
):
    # Fetch all clients with a GSTIN
    query = db.query(Client).filter(Client.gstin != None)
    if current_user.role == "employee":
        query = query.filter(Client.assigned_employee_id == current_user.id)
    clients = query.all()

    # Fetch database filings
    filings = db.query(GstFiling).filter(
        GstFiling.financial_year == financial_year,
        GstFiling.month == month,
        GstFiling.return_type == return_type
    ).all()

    filing_map = {f.client_id: f for f in filings}

    results = []
    for client in clients:
        filing_record = filing_map.get(client.id)
        
        status = filing_record.filing_status if filing_record else "Pending"
        filing_date = filing_record.filing_date if filing_record else None
        extend_date = filing_record.extend_date if filing_record else None
        last_check = filing_record.last_check.strftime("%d-%m-%Y %H:%M:%S") if (filing_record and filing_record.last_check) else None

        # Filter by filing status if requested
        if filing_status and filing_status != "All" and status.lower() != filing_status.lower():
            continue

        # Extract State from GSTIN (first 2 digits)
        state_code = client.gstin[:2] if client.gstin and len(client.gstin) >= 2 else ""
        state_map = {
            "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
            "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
            "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
            "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
            "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
            "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
            "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
            "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
            "38": "Ladakh"
        }
        state_name = state_map.get(state_code, "Unknown")

        results.append({
            "client_id": client.id,
            "business_name": client.business_name,
            "file_no": f"PTC-{client.id:03d}",
            "gstin": client.gstin,
            "state": state_name,
            "taxpayer_type": client.taxpayer_type or "Regular",
            "filing_frequency": client.filing_type or "Monthly",
            "return_period": f"{month} {financial_year.split(' - ')[0]}",
            "period": return_type,
            "extend_date": extend_date or "—",
            "filing_status": status,
            "filing_date": filing_date or "—",
            "mobile": client.mobile or client.phone or "—",
            "last_check": last_check or "—"
        })

    return results


@router.post("/gst/filings/update")
def update_gst_filing(
    payload: GstFilingUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee)
):
    if current_user.role == "employee":
        client = db.query(Client).filter(Client.id == payload.client_id).first()
        if not client or client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

    record = db.query(GstFiling).filter(
        GstFiling.client_id == payload.client_id,
        GstFiling.financial_year == payload.financial_year,
        GstFiling.month == payload.month,
        GstFiling.return_type == payload.return_type
    ).first()
    
    if record:
        record.filing_status = payload.filing_status
        record.filing_date = payload.filing_date
        record.extend_date = payload.extend_date
        record.last_check = datetime.now()
    else:
        record = GstFiling(
            client_id=payload.client_id,
            financial_year=payload.financial_year,
            month=payload.month,
            return_type=payload.return_type,
            filing_status=payload.filing_status,
            filing_date=payload.filing_date,
            extend_date=payload.extend_date,
            last_check=datetime.now()
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return {"success": True, "data": {
        "id": record.id,
        "client_id": record.client_id,
        "filing_status": record.filing_status,
        "filing_date": record.filing_date,
        "extend_date": record.extend_date,
        "last_check": record.last_check.strftime("%d-%m-%Y %H:%M:%S")
    }}


@router.post("/gst/filings/remind")
async def send_gst_reminders(
    payload: GstRemindPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee)
):
    success_count = 0
    failed_clients = []

    for cid in payload.client_ids:
        client = db.query(Client).filter(Client.id == cid).first()
        if not client:
            failed_clients.append(f"Client {cid} not found")
            continue

        if current_user.role == "employee" and client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

        phone = client.mobile or client.phone
        if not phone:
            failed_clients.append(f"{client.business_name} (no phone number)")
            continue

        # Clean recipient's phone number
        to_phone = "".join(filter(str.isdigit, phone))
        if not to_phone.startswith("91") and len(to_phone) == 10:
            to_phone = f"91{to_phone}"

        # Personalize template
        message = payload.message_template.replace("{business_name}", client.business_name)

        try:
            await send_whatsapp_message(to_phone=to_phone, message=message)
            
            # Log message in DB
            db.add(WhatsappMessage(
                client_phone=to_phone,
                direction="outbound",
                message=message
            ))
            success_count += 1
        except Exception as e:
            failed_clients.append(f"{client.business_name} (send error: {str(e)})")

    db.commit()
    return {
        "success": True,
        "success_count": success_count,
        "failed_clients": failed_clients
    }
=======
# routes/gst.py
# FastAPI routes for GST — captcha fetch, verify/scrape, filing CRUD, WhatsApp reminders.
# No Playwright logic here — all scraping is in gst_scraper.py.

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import Client, GstFiling, User, WhatsappMessage
from auth import admin_or_employee
from routes.whatsapp import send_whatsapp_message
from gst_scraper import start_gst_search, submit_captcha_and_scrape

router = APIRouter(tags=["GST"])


# ── Request / Response schemas ────────────────────────────────────────────────

class GstCaptchaRequest(BaseModel):
    gstin: str


class VerifyCaptchaRequest(BaseModel):
    session_id: str
    captcha_text: str
    client_id: Optional[int] = None  # If provided, scraped data is saved to this client


class GstFilingUpdatePayload(BaseModel):
    client_id: int
    financial_year: str
    month: str
    return_type: str
    filing_status: str
    filing_date: Optional[str] = None
    extend_date: Optional[str] = None


class GstRemindPayload(BaseModel):
    client_ids: List[int]
    message_template: str  # Use {business_name} as placeholder


# ── Filing status column map — keeps the save logic DRY ──────────────────────



def _save_scraped_data_to_client(client: Client, scraped: dict, db) -> None:
    """Writes all scraped fields from the GST portal onto the Client ORM object."""

    # Basic info
    client.registration_date     = scraped.get("registration_date")
    client.constitution          = scraped.get("constitution")
    client.taxpayer_type         = scraped.get("taxpayer_type")
    client.principal_place       = scraped.get("principal_place")
    client.business_activity     = scraped.get("business_activity")
    client.gstin_status          = scraped.get("status")

    # Filing statuses
    filings = scraped.get("filings", {})
    current = filings.get("current", {})
    previous = filings.get("previous", {})
    # ── Save GST filing history ─────────────────────────────

    filings = scraped.get("filings", {})

    all_periods = {
        "current": filings.get("current", {}),
        "previous": filings.get("previous", {}),
    }

    for fy_type, fy_data in all_periods.items():
        for return_type, months_data in fy_data.items():

            for month_key, filing_data in months_data.items():

                financial_year = filing_data.get("fy")
                existing = db.query(GstFiling).filter(
                    GstFiling.client_id == client.id,
                    GstFiling.financial_year == financial_year,
                    GstFiling.month == filing_data.get("period"),
                    GstFiling.return_type == return_type,
                ).first()

                if existing:

                    existing.filing_status = filing_data.get("status")
                    existing.filing_date = filing_data.get("date")
                    existing.last_check = datetime.now()

                else:

                    db.add(
                        GstFiling(
                            client_id=client.id,
                            financial_year=financial_year,
                            month=filing_data.get("period"),
                            return_type=return_type,
                            filing_status=filing_data.get("status"),
                            filing_date=filing_data.get("date"),
                            last_check=datetime.now(),
                        )
                    )
    
    summary = {}

    for fy_type, fy_data in all_periods.items():

        for return_type, months_data in fy_data.items():

            latest_month = next(
                iter(months_data.values()),
                None
            )

            if latest_month:

                summary[return_type] = {
                    "status": latest_month.get("status"),
                    "date": latest_month.get("date"),
                    "period": latest_month.get("period"),
                    "financial_year": latest_month.get("fy"),
                }
    client.gst_summary = summary
    client.last_filing_check = datetime.now()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/gst/get-captcha")
async def get_captcha(request: GstCaptchaRequest):
    """
    Step 1: Open GST portal, type the GSTIN, screenshot the captcha.
    Returns a session_id (to use in /gst/verify) and the captcha image as base64.
    """
    try:
        result = await start_gst_search(request.gstin)
        return {
            "success": True,
            "session_id": result["session_id"],
            "captcha_image": result["captcha_image"],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/gst/verify")
async def verify_captcha(
    request: VerifyCaptchaRequest,
    db: Session = Depends(get_db),
):
    """
    Step 2: Submit the captcha, scrape the result page.
    If client_id is provided, scraped data is saved to that client record.
    """
    try:
        scraped = await submit_captcha_and_scrape(
            request.session_id, request.captcha_text
        )
    except ValueError as e:
        # Session expired or not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Scrape failed: {e}")

    # Persist to DB if client_id was supplied
    if request.client_id:
        client = db.query(Client).filter(Client.id == request.client_id).first()
        if client:
            _save_scraped_data_to_client(client, scraped,db)
            db.commit()
        else:
            # Non-fatal — still return scraped data, just warn
            scraped["_warning"] = f"client_id {request.client_id} not found; data not saved."

    return {"success": True, "data": scraped}


@router.get("/gst/filings", response_model=List[dict])
def get_gst_filings(
    financial_year: str,
    month: str,
    return_type: str,
    filing_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """Returns filing status rows for all clients, filtered by FY/month/return type."""

    query = db.query(Client).filter(Client.gstin.isnot(None))
    if current_user.role == "employee":
        query = query.filter(Client.assigned_employee_id == current_user.id)
    clients = query.all()

    filings = db.query(GstFiling).filter(
        GstFiling.financial_year == financial_year,
        GstFiling.month == month,
        GstFiling.return_type == return_type,
    ).all()
    filing_map = {f.client_id: f for f in filings}

    results = []
    for client in clients:
        rec = filing_map.get(client.id)
        status      = rec.filing_status if rec else "Pending"
        filing_date = rec.filing_date   if rec else None
        extend_date = rec.extend_date   if rec else None
        last_check  = (
            rec.last_check.strftime("%d-%m-%Y %H:%M:%S")
            if rec and rec.last_check else None
        )

        if filing_status and filing_status != "All" and status.lower() != filing_status.lower():
            continue    
        results.append({
            "client_id":       client.id,
            "business_name":   client.business_name,
            "file_no":         f"PTC-{client.id:03d}",
            "gstin":           client.gstin,
            "state":           "—",
            "taxpayer_type":   client.taxpayer_type or "Regular",
            "filing_frequency":client.filing_type or "Monthly",
            "return_period":   f"{month} {financial_year.split(' - ')[0]}",
            "period":          return_type,
            "extend_date":     extend_date or "—",
            "filing_status":   status,
            "filing_date":     filing_date or "—",
            "mobile":          client.mobile or client.phone or "—",
            "last_check":      last_check or "—",
        })

    return results


@router.post("/gst/filings/update")
def update_gst_filing(
    payload: GstFilingUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """Upsert a single filing status record."""

    if current_user.role == "employee":
        client = db.query(Client).filter(Client.id == payload.client_id).first()
        if not client or client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client.")

    rec = db.query(GstFiling).filter(
        GstFiling.client_id     == payload.client_id,
        GstFiling.financial_year == payload.financial_year,
        GstFiling.month         == payload.month,
        GstFiling.return_type   == payload.return_type,
    ).first()

    if rec:
        rec.filing_status = payload.filing_status
        rec.filing_date   = payload.filing_date
        rec.extend_date   = payload.extend_date
        rec.last_check    = datetime.now()
    else:
        rec = GstFiling(
            client_id      = payload.client_id,
            financial_year = payload.financial_year,
            month          = payload.month,
            return_type    = payload.return_type,
            filing_status  = payload.filing_status,
            filing_date    = payload.filing_date,
            extend_date    = payload.extend_date,
            last_check     = datetime.now(),
        )
        db.add(rec)

    db.commit()
    db.refresh(rec)
    return {
        "success": True,
        "data": {
            "id":            rec.id,
            "client_id":     rec.client_id,
            "filing_status": rec.filing_status,
            "filing_date":   rec.filing_date,
            "extend_date":   rec.extend_date,
            "last_check":    rec.last_check.strftime("%d-%m-%Y %H:%M:%S"),
        },
    }


@router.post("/gst/filings/remind")
async def send_gst_reminders(
    payload: GstRemindPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """Send WhatsApp filing reminders to a list of clients."""

    success_count = 0
    failed_clients: list[str] = []

    for cid in payload.client_ids:
        client = db.query(Client).filter(Client.id == cid).first()
        if not client:
            failed_clients.append(f"Client {cid} not found")
            continue

        if current_user.role == "employee" and client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client.")

        phone = client.mobile or client.phone
        if not phone:
            failed_clients.append(f"{client.business_name} (no phone number)")
            continue

        # Normalise to 91XXXXXXXXXX
        digits = "".join(filter(str.isdigit, phone))
        if not digits.startswith("91") and len(digits) == 10:
            digits = f"91{digits}"

        message = payload.message_template.replace("{business_name}", client.business_name)

        try:
            await send_whatsapp_message(to_phone=digits, message=message)
            db.add(WhatsappMessage(
                client_phone=digits,
                direction="outbound",
                message=message,
            ))
            success_count += 1
        except Exception as e:
            failed_clients.append(f"{client.business_name} (send error: {e})")

    db.commit()
    return {
        "success": True,
        "success_count": success_count,
        "failed_clients": failed_clients,
    }
