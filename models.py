# models.py
# Each class here = one table in PostgreSQL.
# The attributes = columns in that table.
# SQLAlchemy handles all the SQL CREATE TABLE statements for us.

from datetime import datetime

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
    workflow_tasks = relationship(
        "WorkflowTask",
        foreign_keys="WorkflowTask.assigned_user_id",
        overlaps="assigned_user"
    )

    activity_logs = relationship(
        "ActivityLog",
        back_populates="user"
    )

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
    assigned_manager_id = Column(
    Integer,
    ForeignKey("users.id"), 
    nullable=True)
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

    workflows = relationship(
    "ClientWorkflow",
    back_populates="client"
    )
    
    #Relationships
    assigned_employee = relationship("User", foreign_keys=[assigned_employee_id], back_populates="assigned_clients")
    assigned_manager = relationship(
    "User",foreign_keys=[assigned_manager_id])
    client_user = relationship("User", foreign_keys=[user_id])
    services = relationship("ClientService", back_populates="client", cascade="all, delete")
    documents = relationship("Document", back_populates="client", cascade="all, delete")
    tasks = relationship("Task", back_populates="client", cascade="all, delete")
    directors = relationship("Director", back_populates="client", cascade="all, delete-orphan")
    document_registers = relationship(
        "DocumentRegister",
        back_populates="client",
        cascade="all, delete-orphan"
    )

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
    uploader = relationship("User",back_populates="uploaded_documents")
    # REGISTER IN
    received_from = Column(String, nullable=True)
    received_by = Column(String, nullable=True)
    received_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    # REGISTER OUT
    returned_to = Column(String, nullable=True)
    returned_by = Column(String, nullable=True)
    returned_at = Column(
        DateTime,
        nullable=True
    )
    remarks = Column(Text, nullable=True)

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

    meta_message_id = Column(String(100), nullable=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    client_phone = Column(String(20))

    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    direction = Column(String(20))
    sender_type = Column(String(20))

    message_type = Column(String(20), default="text")
    message = Column(Text)

    is_read = Column(Boolean, default=False)
    conversation_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client")

    employee = relationship(
        "User",
        foreign_keys=[employee_id]
    )

    manager = relationship(
        "User",
        foreign_keys=[manager_id]
    )


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

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=True
    )

    workflow_id = Column(
        Integer,
        ForeignKey("client_workflows.id"),
        nullable=True
    )

    task_id = Column(
        Integer,
        ForeignKey("workflow_tasks.id"),
        nullable=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    action = Column(
        String(100),
        nullable=False
    )

    description = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    user = relationship(
        "User",
        back_populates="activity_logs"
    )

class WorkflowTaskComment(Base):
    __tablename__ = "workflow_task_comments"

    id = Column(Integer, primary_key=True)

    task_id = Column(
        Integer,
        ForeignKey("workflow_tasks.id")
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    comment = Column(Text)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    user = relationship("User")

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True)

    name = Column(
        String(100),
        nullable=False
    )

    description = Column(Text)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    steps = relationship(
        "WorkflowTemplateStep",
        back_populates="template",
        cascade="all, delete-orphan"
    )

class WorkflowTemplateStep(Base):
    __tablename__ = "workflow_template_steps"

    id = Column(Integer, primary_key=True)

    template_id = Column(
        Integer,
        ForeignKey("workflow_templates.id")
    )

    name = Column(
        String(200),
        nullable=False
    )

    sequence = Column(
        Integer,
        nullable=False
    )

    default_role = Column(
        String(20),
        nullable=False)

    approval_required = Column(
        Boolean,
        default=False)

    estimated_hours = Column(
        Integer,
        default=1)
    
    due_days = Column(
    Integer,
    default=1)

    allow_comments = Column(
        Boolean,
        default=True)

    allow_attachments = Column(
        Boolean,
        default=True)

    is_mandatory = Column(
        Boolean,
        default=True)
    
    template = relationship(
        "WorkflowTemplate",
        back_populates="steps")
    

class ClientWorkflow(Base):
    __tablename__ = "client_workflows"

    id = Column(Integer, primary_key=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"))

    template_id = Column(
        Integer,
        ForeignKey("workflow_templates.id"))

    assigned_manager_id = Column(
    Integer,
    ForeignKey("users.id"),
    nullable=True)

    assigned_employee_id = Column(
    Integer,
    ForeignKey("users.id"),
    nullable=True)

    status = Column(
        String(20),
        default="active"
    )

    progress_percent = Column(
        Integer,
        default=0
    )

    current_step = Column(
        Integer,
        default=1
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    start_date = Column(Date)
    due_date = Column(Date)
    completed_at = Column(DateTime, nullable=True)

    client = relationship(
    "Client",
    back_populates="workflows"
    )
    template = relationship("WorkflowTemplate")

    assigned_manager = relationship(
    "User",
    foreign_keys=[assigned_manager_id])

    assigned_employee = relationship(
    "User",
    foreign_keys=[assigned_employee_id])

    activity_logs = relationship(
    "ActivityLog")
 
class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id = Column(Integer, primary_key=True)

    workflow_id = Column(
        Integer,
        ForeignKey("client_workflows.id")
    )

    template_step_id = Column(
        Integer,
        ForeignKey("workflow_template_steps.id")
    )

    assigned_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    original_assignee_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    transfer_approved = Column(
        Boolean,
        default=False
    )

    status = Column(
        String(20),
        default="pending"
    )

    approved = Column(
        Boolean,
        default=False
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )

    started_at = Column(
        DateTime,
        nullable=True
    )

    due_date = Column(
        Date,
        nullable=True
    )

    rejected_reason = Column(
        Text,
        nullable=True
    )

    priority = Column(
        String(20),
        default="normal"
    )

    transferred_to_id = Column(
    Integer,
    ForeignKey("users.id"),
    nullable=True
    )

    transferred_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    transferred_completed = Column(
        Boolean,
        default=False
    )

    transferred_to = relationship(
    "User",
    foreign_keys=[transferred_to_id]
    )

    transferred_by = relationship(
        "User",
        foreign_keys=[transferred_by_id]
    )

    workflow = relationship("ClientWorkflow")

    assigned_user = relationship(
        "User",
        foreign_keys=[assigned_user_id]
    )

    original_assignee = relationship(
        "User",
        foreign_keys=[original_assignee_id]
    )

    template_step = relationship("WorkflowTemplateStep")

    comments = relationship(
        "WorkflowTaskComment",
        cascade="all, delete-orphan"
    )

    attachments = relationship(
        "WorkflowTaskAttachment",
        cascade="all, delete-orphan"
    )


class WorkflowTaskAttachment(Base):
    __tablename__ = "workflow_task_attachments"

    id = Column(Integer, primary_key=True)

    task_id = Column(
        Integer,
        ForeignKey("workflow_tasks.id")
    )

    uploaded_by = Column(
        Integer,
        ForeignKey("users.id")
    )

    file_name = Column(String(255))

    file_url = Column(Text)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    uploader = relationship("User")

class DocumentRegister(Base):
    __tablename__ = "document_register"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False
    )

    document_name = Column(
        String(255),
        nullable=False
    )

    document_details = Column(Text)

    collected_by = Column(
        String(100),
        nullable=False
    )

    collected_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    returned_to = Column(
        String(100),
        nullable=True
    )

    returned_by = Column(
        String(100),
        nullable=True
    )

    returned_at = Column(DateTime, nullable=True)

    remarks = Column(Text)

    client = relationship("Client", back_populates="document_registers")
