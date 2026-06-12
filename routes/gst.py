# routes/gst.py
# FastAPI routes for GST — captcha fetch, verify/scrape, filing CRUD, WhatsApp reminders.
# No Playwright logic here — all scraping is in gst_scraper.py.

from fastapi import APIRouter, HTTPException, Depends
from httpcore import request
from httpcore import request
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


# ── Helper functions ──────────────────────────────────────────────────────────

def _save_scraped_data_to_client(client: Client, scraped: dict, db: Session) -> None:
    """Writes all scraped fields from the GST portal onto the Client ORM object."""

    # Basic info
    client.registration_date     = scraped.get("registration_date")
    client.constitution          = scraped.get("constitution")
    client.taxpayer_type         = scraped.get("taxpayer_type")
    client.principal_place       = scraped.get("principal_place")
    client.business_activity     = scraped.get("business_activity")
    client.gstin_status          = scraped.get("status")

    # Filing statuses
    filings = scraped.get("filings") or {}
    all_periods = {
        "current": filings.get("current") or {},
        "previous": filings.get("previous") or {},
    }

    for fy_type, fy_data in all_periods.items():
        if not isinstance(fy_data, dict):
            continue
        for return_type, months_data in fy_data.items():
            if not isinstance(months_data, dict):
                continue
            for month_key, filing_data in months_data.items():
                if not isinstance(filing_data, dict):
                    continue
                financial_year = filing_data.get("fy")
                month_name = filing_data.get("period")
                if not financial_year or not month_name:
                    continue
                
                existing = db.query(GstFiling).filter(
                    GstFiling.client_id == client.id,
                    GstFiling.financial_year == financial_year,
                    GstFiling.month == month_name,
                    GstFiling.return_type == return_type,
                ).first()

                if existing:
                    existing.filing_status = filing_data.get("status") or "Pending"
                    existing.filing_date = filing_data.get("date")
                    existing.last_check = datetime.now()
                else:
                    print("INSERTING GST FILINGS")
                    print(
                        "INSERT:",
                        financial_year,
                        month_name,
                        return_type
                    )
                    db.add(
                        GstFiling(
                            client_id=client.id,
                            financial_year=financial_year,
                            month=month_name,
                            return_type=return_type,
                            filing_status=filing_data.get("status") or "Pending",
                            filing_date=filing_data.get("date"),
                            last_check=datetime.now(),
                        )
                    )
    
    summary = {}
    for fy_type, fy_data in all_periods.items():
        if not isinstance(fy_data, dict):
            continue
        for return_type, months_data in fy_data.items():
            if not isinstance(months_data, dict):
                continue
            latest_month = None
            for key, val in months_data.items():
                if isinstance(val, dict):
                    latest_month = val
                    break
            if latest_month:
                summary[return_type] = {
                    "status": latest_month.get("status"),
                    "date": latest_month.get("date"),
                    "period": latest_month.get("period"),
                    "financial_year": latest_month.get("fy"),
                }
    client.gst_summary = summary
    client.last_filing_check = datetime.now()


def month_matches(db_month: str, query_month: str) -> bool:
    if not db_month or not query_month:
        return False
    if query_month == "All":
        return True
        
    db_m = db_month.lower()
    q_m = query_month.lower()
    
    # 1. Direct or substring match
    if q_m in db_m:
        return True
    
    # 2. 3-letter abbreviation match
    abbreviations = {
        "january": "jan", "february": "feb", "march": "mar",
        "april": "apr", "may": "may", "june": "jun",
        "july": "jul", "august": "aug", "september": "sep",
        "october": "oct", "november": "nov", "december": "dec"
    }
    q_abbr = abbreviations.get(q_m, q_m[:3])
    if q_abbr in db_m:
        return True
        
    # 3. Quarter mappings
    quarters = {
        "april": ["q1", "apr-jun", "april-june"],
        "may": ["q1", "apr-jun", "april-june"],
        "june": ["q1", "apr-jun", "april-june"],
        "july": ["q2", "jul-sep", "july-september"],
        "august": ["q2", "jul-sep", "july-september"],
        "september": ["q2", "jul-sep", "july-september"],
        "october": ["q3", "oct-dec", "october-december"],
        "november": ["q3", "oct-dec", "october-december"],
        "december": ["q3", "oct-dec", "october-december"],
        "january": ["q4", "jan-mar", "january-march"],
        "february": ["q4", "jan-mar", "january-march"],
        "march": ["q4", "jan-mar", "january-march"]
    }
    
    for term in quarters.get(q_m, []):
        if term in db_m:
            return True
            
    return False


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
    current_user: User = Depends(admin_or_employee),
):
    print("=" * 80)
    print("VERIFY ROUTE HIT")
    print("REQUEST =", request)
    print("CLIENT ID =",request.client_id)
    print("=" * 80)
    """
    Step 2: Submit the captcha, scrape the result page.
    If client_id is provided, scraped data is saved to that client record.
    """
    try:
        scraped = await submit_captcha_and_scrape(
            request.session_id, request.captcha_text
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Scrape failed: {e}")

    # Persist to DB if client_id was supplied
    if request.client_id:
        client = db.query(Client).filter(Client.id == request.client_id).first()
        if client:
            if current_user.role == "employee" and client.assigned_employee_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not your assigned client.")
            _save_scraped_data_to_client(client, scraped, db)
            db.commit()
        else:
            scraped["_warning"] = f"client_id {request.client_id} not found; data not saved."
    print("CLIENT ID RECEIVED:", request.client_id)
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

    # Determine return types to query
    if return_type == "All" or not return_type:
        returns_to_query = [
            "gstr1_iff", "gstr3b", "cmp08", "gstr4",
            "gstr4_annual", "gstr9_annual", "gstr9c", "gstr1a"
        ]
    else:
        returns_to_query = [return_type]

    # Fetch all database filings for this FY and return types
    filings = db.query(GstFiling).filter(
        GstFiling.financial_year == financial_year,
        GstFiling.return_type.in_(returns_to_query),
    ).all()

    results = []
    for client in clients:
        # Get filings for this specific client
        client_filings = [f for f in filings if f.client_id == client.id]
        
        # Filter by month match
        matching_filings = []
        for rec in client_filings:
            if month == "All" or not month or month_matches(rec.month, month):
                matching_filings.append(rec)
                
        if not matching_filings:
            status = "Pending"
            
            if filing_status and filing_status != "All" and status.lower() != filing_status.lower():
                continue
                
            display_return_type = return_type if (return_type and return_type != "All") else "—"
            display_month = month if (month and month != "All") else "—"
            
            if display_month != "—":
                return_period = f"{display_month} {financial_year.split(' - ')[0]}"
            else:
                return_period = "—"

            results.append({
                "id": f"pending-{client.id}-{return_type}-{month}",
                "client_id": client.id,
                "business_name": client.business_name,
                "file_no": f"PTC-{client.id:03d}",
                "gstin": client.gstin,
                "state": "",
                "taxpayer_type": client.taxpayer_type or "Regular",
                "filing_frequency": client.filing_type or "Monthly",
                "return_period": return_period,
                "period": display_return_type,
                "return_type": display_return_type,
                "financial_year": financial_year,
                "month": display_month,
                "extend_date": "—",
                "filing_status": status,
                "filing_date": "—",
                "mobile": client.mobile or client.phone or "—",
                "last_check": "—",
            })
        else:
            for rec in matching_filings:
                status      = rec.filing_status or "Pending"
                filing_date = rec.filing_date
                extend_date = rec.extend_date
                last_check  = (
                    rec.last_check.strftime("%d-%m-%Y %H:%M:%S")
                    if rec.last_check else None
                )

                if filing_status and filing_status != "All" and status.lower() != filing_status.lower():
                    continue

                results.append({
                    "id": rec.id,
                    "client_id": client.id,
                    "business_name": client.business_name,
                    "file_no": f"PTC-{client.id:03d}",
                    "gstin": client.gstin,
                    "state": "",
                    "taxpayer_type": client.taxpayer_type or "Regular",
                    "filing_frequency": client.filing_type or "Monthly",
                    "return_period": f"{rec.month} {financial_year.split(' - ')[0]}",
                    "period": rec.return_type,
                    "return_type": rec.return_type,
                    "financial_year": financial_year,
                    "month": rec.month,
                    "extend_date": extend_date or "—",
                    "filing_status": status,
                    "filing_date": filing_date or "—",
                    "mobile": client.mobile or client.phone or "—",
                    "last_check": last_check or "—",
                })

    month_order = {
    "April": 1,
    "May": 2,
    "June": 3,
    "July": 4,
    "August": 5,
    "September": 6,
    "October": 7,
    "November": 8,
    "December": 9,
    "January": 10,
    "February": 11,
    "March": 12,
}

    results.sort(
    key=lambda x: (
        x["financial_year"],
        month_order.get(x["month"], 0),
    ),
    reverse=True,
)

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
