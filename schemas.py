from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# ── AUTH ──────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    credential: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    user_id: int


# ── USER ──────────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str
    phone: Optional[str] = None

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    phone: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── SERVICE ───────────────────────────────────────────────
class ServiceOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ── CLIENT SERVICE ────────────────────────────────────────
class ClientServiceOut(BaseModel):
    id: int
    service: ServiceOut
    status: str
    progress: int
    due_date: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class ClientServiceUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[int] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


# ── DOCUMENT ──────────────────────────────────────────────
class DocumentOut(BaseModel):
    id: int
    file_name: str
    file_url: str
    file_type: Optional[str] = None
    file_size_kb: Optional[int] = None
    visible_to_client: bool
    created_at: datetime
    uploader: Optional[UserOut] = None
    client_service_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── TASK ──────────────────────────────────────────────────
class ClientMinOut(BaseModel):
    id: int
    business_name: str

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    client_id: int
    title: str
    due_date: Optional[date] = None
    assigned_to: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    title: str
    due_date: Optional[date] = None
    status: str
    assignee: Optional[UserOut] = None
    client_id: int
    client: Optional[ClientMinOut] = None

    class Config:
        from_attributes = True


# ── DIRECTOR ────────────────────────────────────────────────
class DirectorCreate(BaseModel):
    name: str
    pan: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    din: Optional[str] = None

class DirectorOut(BaseModel):
    id: int
    name: str
    pan: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    din: Optional[str] = None

    class Config:
        from_attributes = True


# ── CLIENT ────────────────────────────────────────────────
class ClientCreate(BaseModel):
    business_name: str
    contact_person: Optional[str] = None
    contact_name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    aadhaar_number: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    gst_username: Optional[str] = None
    gst_password: Optional[str] = None
    eway_bill_id: Optional[str] = None
    eway_password: Optional[str] = None
    einvoice_id: Optional[str] = None
    einvoice_password: Optional[str] = None
    gstin_status: Optional[str] = None
    registration_date: Optional[str] = None
    constitution: Optional[str] = None
    taxpayer_type: Optional[str] = None
    principal_place: Optional[str] = None
    business_activity: Optional[str] = None
    filing_type: Optional[str] = None
    pan: Optional[str] = None
    tan: Optional[str] = None
    it_login_id: Optional[str] = None
    it_password: Optional[str] = None
    tds_login_id: Optional[str] = None
    tds_password: Optional[str] = None
    traces_id: Optional[str] = None
    traces_password: Optional[str] = None
    iec_code: Optional[str] = None
    iec_password: Optional[str] = None
    lut_number: Optional[str] = None
    udyam_number: Optional[str] = None
    udyam_id: Optional[str] = None
    udyam_password: Optional[str] = None
    gumasta: Optional[str] = None
    gumasta_id: Optional[str] = None
    gumasta_password: Optional[str] = None
    food_license: Optional[str] = None
    food_license_id: Optional[str] = None
    food_license_password: Optional[str] = None
    trademark: Optional[str] = None
    trademark_id: Optional[str] = None
    trademark_password: Optional[str] = None
    roc_id: Optional[str] = None
    roc_password: Optional[str] = None
    ptrc_number: Optional[str] = None
    ptrc_id: Optional[str] = None
    ptrc_password: Optional[str] = None
    ptec_number: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    # GST Filing Return Statuses
    gstr1_iff_status: Optional[str] = None
    gstr3b_status: Optional[str] = None
    gstr4_status: Optional[str] = None
    cmp08_status: Optional[str] = None
    gstr4_annual_status: Optional[str] = None
    gstr9_annual_status: Optional[str] = None
    gstr9c_status: Optional[str] = None
    gstr1a_status: Optional[str] = None
    # Previous Year GST Filing Return Statuses
    gstr1_iff_status_prev: Optional[str] = None
    gstr3b_status_prev: Optional[str] = None
    gstr4_status_prev: Optional[str] = None
    cmp08_status_prev: Optional[str] = None
    gstr4_annual_status_prev: Optional[str] = None
    gstr9_annual_status_prev: Optional[str] = None
    gstr9c_status_prev: Optional[str] = None
    gstr1a_status_prev: Optional[str] = None
    last_filing_check: Optional[datetime] = None
    directors: Optional[List[DirectorCreate]] = []


class ClientUpdate(BaseModel):
    business_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    aadhaar_number: Optional[str] = None
    gstin: Optional[str] = None
    gst_username: Optional[str] = None
    gst_password: Optional[str] = None
    eway_bill_id: Optional[str] = None
    eway_password: Optional[str] = None
    einvoice_id: Optional[str] = None
    einvoice_password: Optional[str] = None
    gstin_status: Optional[str] = None
    registration_date: Optional[str] = None
    constitution: Optional[str] = None
    taxpayer_type: Optional[str] = None
    principal_place: Optional[str] = None
    business_activity: Optional[str] = None
    filing_type: Optional[str] = None
    pan: Optional[str] = None
    tan: Optional[str] = None
    it_login_id: Optional[str] = None
    it_password: Optional[str] = None
    tds_login_id: Optional[str] = None
    tds_password: Optional[str] = None
    traces_id: Optional[str] = None
    traces_password: Optional[str] = None
    iec_code: Optional[str] = None
    iec_password: Optional[str] = None
    lut_number: Optional[str] = None
    udyam_number: Optional[str] = None
    udyam_id: Optional[str] = None
    udyam_password: Optional[str] = None
    gumasta: Optional[str] = None
    gumasta_id: Optional[str] = None
    gumasta_password: Optional[str] = None
    food_license: Optional[str] = None
    food_license_id: Optional[str] = None
    food_license_password: Optional[str] = None
    trademark: Optional[str] = None
    trademark_id: Optional[str] = None
    trademark_password: Optional[str] = None
    roc_id: Optional[str] = None
    roc_password: Optional[str] = None
    ptrc_number: Optional[str] = None
    ptrc_id: Optional[str] = None
    ptrc_password: Optional[str] = None
    ptec_number: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    fees: Optional[int] = None
    # GST Filing Return Statuses
    gstr1_iff_status: Optional[str] = None
    gstr3b_status: Optional[str] = None
    gstr4_status: Optional[str] = None
    cmp08_status: Optional[str] = None
    gstr4_annual_status: Optional[str] = None
    gstr9_annual_status: Optional[str] = None
    gstr9c_status: Optional[str] = None
    gstr1a_status: Optional[str] = None
    # Previous Year GST Filing Return Statuses
    gstr1_iff_status_prev: Optional[str] = None
    gstr3b_status_prev: Optional[str] = None
    gstr4_status_prev: Optional[str] = None
    cmp08_status_prev: Optional[str] = None
    gstr4_annual_status_prev: Optional[str] = None
    gstr9_annual_status_prev: Optional[str] = None
    gstr9c_status_prev: Optional[str] = None
    gstr1a_status_prev: Optional[str] = None
    last_filing_check: Optional[datetime] = None
    directors: Optional[List[DirectorCreate]] = None


class ClientSummary(BaseModel):
    id: int
    business_name: str
    contact_person: Optional[str] = None
    contact_name: Optional[str] = None
    mobile: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    tan: Optional[str] = None
    status: str
    assigned_employee: Optional[UserOut] = None
    services: List[ClientServiceOut] = []
    fees: Optional[int] = None
    taxpayer_type: Optional[str] = None
    filing_type: Optional[str] = None
    gstin_status: Optional[str] = None
    address: Optional[str] = None
    # GST Filing Return Statuses
    gstr1_iff_status: Optional[str] = None
    gstr3b_status: Optional[str] = None
    gstr4_status: Optional[str] = None
    cmp08_status: Optional[str] = None
    gstr4_annual_status: Optional[str] = None
    gstr9_annual_status: Optional[str] = None
    gstr9c_status: Optional[str] = None
    gstr1a_status: Optional[str] = None
    # Previous Year GST Filing Return Statuses
    gstr1_iff_status_prev: Optional[str] = None
    gstr3b_status_prev: Optional[str] = None
    gstr4_status_prev: Optional[str] = None
    cmp08_status_prev: Optional[str] = None
    gstr4_annual_status_prev: Optional[str] = None
    gstr9_annual_status_prev: Optional[str] = None
    gstr9c_status_prev: Optional[str] = None
    gstr1a_status_prev: Optional[str] = None
    last_filing_check: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClientDetail(ClientSummary):
    email: Optional[str] = None
    address: Optional[str] = None
    aadhaar_number: Optional[str] = None
    gst_username: Optional[str] = None
    gst_password: Optional[str] = None
    eway_bill_id: Optional[str] = None
    eway_password: Optional[str] = None
    einvoice_id: Optional[str] = None
    einvoice_password: Optional[str] = None
    gstin_status: Optional[str] = None
    registration_date: Optional[str] = None
    constitution: Optional[str] = None
    taxpayer_type: Optional[str] = None
    principal_place: Optional[str] = None
    business_activity: Optional[str] = None
    filing_type: Optional[str] = None
    it_login_id: Optional[str] = None
    it_password: Optional[str] = None
    tds_login_id: Optional[str] = None
    tds_password: Optional[str] = None
    traces_id: Optional[str] = None
    traces_password: Optional[str] = None
    iec_code: Optional[str] = None
    iec_password: Optional[str] = None
    lut_number: Optional[str] = None
    udyam_number: Optional[str] = None
    udyam_id: Optional[str] = None
    udyam_password: Optional[str] = None
    gumasta: Optional[str] = None
    gumasta_id: Optional[str] = None
    gumasta_password: Optional[str] = None
    food_license: Optional[str] = None
    food_license_id: Optional[str] = None
    food_license_password: Optional[str] = None
    trademark: Optional[str] = None
    trademark_id: Optional[str] = None
    trademark_password: Optional[str] = None
    roc_id: Optional[str] = None
    roc_password: Optional[str] = None
    ptrc_number: Optional[str] = None
    ptrc_id: Optional[str] = None
    ptrc_password: Optional[str] = None
    ptec_number: Optional[str] = None
    # GST Filing Return Statuses
    gstr1_iff_status: Optional[str] = None
    gstr3b_status: Optional[str] = None
    gstr4_status: Optional[str] = None
    cmp08_status: Optional[str] = None
    gstr4_annual_status: Optional[str] = None
    gstr9_annual_status: Optional[str] = None
    gstr9c_status: Optional[str] = None
    gstr1a_status: Optional[str] = None
    # Previous Year GST Filing Return Statuses
    gstr1_iff_status_prev: Optional[str] = None
    gstr3b_status_prev: Optional[str] = None
    gstr4_status_prev: Optional[str] = None
    cmp08_status_prev: Optional[str] = None
    gstr4_annual_status_prev: Optional[str] = None
    gstr9_annual_status_prev: Optional[str] = None
    gstr9c_status_prev: Optional[str] = None
    gstr1a_status_prev: Optional[str] = None
    last_filing_check: Optional[datetime] = None
    documents: List[DocumentOut] = []
    tasks: List[TaskOut] = []
    directors: List[DirectorOut] = []
    created_at: datetime
    fees: Optional[int] = None

class Config:
    from_attributes = True


class GstFilingOut(BaseModel):
    id: Optional[int] = None
    client_id: int
    financial_year: str
    month: str
    return_type: str
    filing_status: str
    filing_date: Optional[str] = None
    extend_date: Optional[str] = None
    last_check: Optional[datetime] = None

    class Config:
        from_attributes = True


class GstFilingUpdate(BaseModel):
    filing_status: str
    filing_date: Optional[str] = None
    extend_date: Optional[str] = None
