# models.py
# Each class here = one table in PostgreSQL.
# The attributes = columns in that table.
# SQLAlchemy handles all the SQL CREATE TABLE statements for us.

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Date, ForeignKey, JSON, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    # role controls what this user can see and do
    role = Column(String(20), nullable=False)   # 'admin', 'employee', 'client'
    phone = Column(String(15))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships — these let us do user.assigned_clients in Python
    # instead of writing JOIN queries manually
    assigned_clients = relationship("Client", foreign_keys="Client.assigned_employee_id", back_populates="assigned_employee")
    uploaded_documents = relationship("Document", back_populates="uploader")
    assigned_tasks = relationship("Task", back_populates="assignee")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String(200), nullable=False)
    pan = Column(String(10))
    gstin = Column(String(15))
    contact_person = Column(String(100))
    phone = Column(String(15))
    email = Column(String(150))
    status = Column(String(20), default="active")
    assigned_employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fees = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, server_default=func.now())

    # Contact
    contact_name = Column(String(100))
    mobile = Column(String(15))
    address = Column(Text)

    # GST
    gst_username = Column(String(100))
    gst_password = Column(String(100))
    eway_bill_id = Column(String(100))
    einvoice_id = Column(String(100))

    # Direct Tax
    tan = Column(String(10))
    it_login_id = Column(String(100))
    it_password = Column(String(100))
    tds_login_id = Column(String(100))
    tds_password = Column(String(100))

    # IEC
    iec_code = Column(String(20))
    iec_password = Column(String(100))
    lut_number = Column(String(50))

    # Registrations
    udyam_number = Column(String(50))
    gumasta = Column(String(50))
    food_license = Column(String(50))
    trademark = Column(String(100))
    roc_id = Column(String(100))
    roc_password = Column(String(100))

    # PTRC
    ptrc_number = Column(String(50))
    ptrc_id = Column(String(100))
    ptrc_password = Column(String(100))

    # PTEC
    ptec_number = Column(String(50))

    # New onboarding fields
    aadhaar_number = Column(String(20))
    eway_password = Column(String(100))
    einvoice_password = Column(String(100))

    traces_id = Column(String(100))
    traces_password = Column(String(100))

    # Certificates
    udyam_id = Column(String(100))
    udyam_password = Column(String(100))

    gumasta_id = Column(String(100))
    gumasta_password = Column(String(100))

    food_license_id = Column(String(100))
    food_license_password = Column(String(100))

    trademark_id = Column(String(100))
    trademark_password = Column(String(100))

    # GST fetched data
    registration_date = Column(String(20))
    constitution = Column(String(100))
    taxpayer_type = Column(String(100))
    principal_place = Column(Text)

    business_activity = Column(Text)
    filing_type = Column(String(20))
    gstin_status = Column(String(50))

    # Latest GST filing summary cache
    gst_summary = Column(JSON, nullable=True)
    last_filing_check = Column(DateTime)

    # Relationships
    assigned_employee = relationship("User", foreign_keys=[assigned_employee_id], back_populates="assigned_clients")
    client_user = relationship("User", foreign_keys=[user_id])
    services = relationship("ClientService", back_populates="client", cascade="all, delete")
    documents = relationship("Document", back_populates="client", cascade="all, delete")
    tasks = relationship("Task", back_populates="client", cascade="all, delete")
    directors = relationship("Director", back_populates="client", cascade="all, delete-orphan")

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)        # e.g. 'GST Filing'
    description = Column(Text)

    client_services = relationship("ClientService", back_populates="service")


class ClientService(Base):
    # This table links a client to a service they've engaged for.
    # e.g. "Sharma Enterprises" + "GST Filing" + status="in_progress"
    __tablename__ = "client_services"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    status = Column(String(30), default="pending")   # pending/in_progress/completed/on_hold
    progress = Column(Integer, default=0)             # 0 to 100
    due_date = Column(Date, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="services")
    service = relationship("Service", back_populates="client_services")
    documents = relationship("Document", back_populates="client_service")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    client_service_id = Column(Integer, ForeignKey("client_services.id"), nullable=True)
    file_name = Column(String(200), nullable=False)
    file_url = Column(Text, nullable=False)           # URL where file is stored
    file_type = Column(String(50))                    # e.g. 'pdf', 'xlsx'
    file_size_kb = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    # if True, client can see this doc on their portal and via WhatsApp
    visible_to_client = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="documents")
    client_service = relationship("ClientService", back_populates="documents")
    uploader = relationship("User", back_populates="uploaded_documents")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="pending")    # pending/done/overdue
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks")


class WhatsappMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    client_phone = Column(String(15))
    direction = Column(String(10))                    # 'inbound' or 'outbound'
    message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    pan = Column(String(10))
    email = Column(String(150))
    mobile = Column(String(15))
    din = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="directors")


class GstFiling(Base):
    __tablename__ = "gst_filings"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    financial_year = Column(String(20), nullable=False)
    month = Column(String(20), nullable=False)
    return_type = Column(String(50), nullable=False)
    filing_status = Column(String(20), default="Pending")  # "Filed", "Pending"
    filing_date = Column(String(20), nullable=True)
    extend_date = Column(String(20), nullable=True)
    last_check = Column(DateTime, server_default=func.now(), onupdate=func.now())

    client = relationship("Client")
