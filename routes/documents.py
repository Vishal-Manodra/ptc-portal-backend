# routes/documents.py
# Handles file upload, listing, and deletion.
# Files are stored on Cloudflare R2 via storage.py.
# Only the URL is saved in the database — the actual file lives on R2.
#
#   POST   /documents/upload          → upload a file for a client
#   GET    /documents/{client_id}     → list all docs for a client
#   PATCH  /documents/{doc_id}/visibility → toggle client visibility
#   DELETE /documents/{doc_id}        → delete doc from DB and R2

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from database import get_db
from models import Document, Client, User
from schemas import DocumentOut
from auth import admin_or_employee, any_authenticated_user
from storage import upload_file, delete_file

router = APIRouter(prefix="/documents", tags=["Documents"])

# Max file size: 20MB (in bytes)
MAX_FILE_SIZE = 20 * 1024 * 1024

# Allowed file types
ALLOWED_EXTENSIONS = {
    "pdf", "xlsx", "xls", "docx", "doc",
    "jpg", "jpeg", "png", "csv", "txt"
}


# ── UPLOAD DOCUMENT ───────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentOut,)
async def upload_document(
    client_id: int = Form(...),                  # which client this belongs to
    file: UploadFile = File(...),                # the actual file
    client_service_id: Optional[int] = Form(None),  # optional: link to a service
    visible_to_client: bool = Form(True),        # can the client see this?
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Uploads a file to Cloudflare R2 and saves metadata to the database.
    
    Frontend sends a multipart/form-data request (not JSON) because it includes a file.
    Form fields: client_id, client_service_id (optional), visible_to_client
    File field: file
    
    Flow:
    1. Validate file type and size
    2. Upload bytes to R2 via storage.py
    3. Save the returned URL + metadata to documents table
    """
    # Validate client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if current_user.role == "employee" and client.assigned_employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assigned client")

    # Check file extension
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type .{ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file into memory and check size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is 20MB"
        )

    # Upload to Cloudflare R2
    try:
        result = upload_file(file_bytes, filename, client_id)
    except Exception as e:
        import traceback
        traceback.print_exc()  # ← prints full error to terminal
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # Save document record to database
    doc = Document(
        client_id=client_id,
        client_service_id=client_service_id,
        file_name=result["file_name"],
        file_url=result["file_url"],
        file_type=result["file_type"],
        file_size_kb=result["file_size_kb"],
        uploaded_by=current_user.id,
        visible_to_client=visible_to_client,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return db.query(Document).options(
        joinedload(Document.uploader)
    ).filter(Document.id == doc.id).first()


# ── LIST DOCUMENTS FOR A CLIENT ───────────────────────────────────────────────

@router.get("/{client_id}", response_model=List[DocumentOut])
def list_documents(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(any_authenticated_user),
):
    """
    Returns all documents for a client.
    - Admin/Employee: sees all documents including internal ones
    - Client: sees only documents marked visible_to_client=True
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Access control
    if current_user.role == "client" and client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role == "employee" and client.assigned_employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assigned client")

    query = db.query(Document).options(
        joinedload(Document.uploader)
    ).filter(Document.client_id == client_id)

    # Clients only see documents marked as visible
    if current_user.role == "client":
        query = query.filter(Document.visible_to_client == True)

    return query.order_by(Document.created_at.desc()).all()


# ── TOGGLE CLIENT VISIBILITY ──────────────────────────────────────────────────

@router.patch("/{doc_id}/visibility", response_model=DocumentOut)
def toggle_visibility(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Toggles whether a document is visible to the client.
    Useful for internal working papers that the client shouldn't see,
    vs final deliverables (ITR acknowledgement, GST certificate) they should.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role == "employee":
        client = db.query(Client).filter(Client.id == doc.client_id).first()
        if not client or client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

    doc.visible_to_client = not doc.visible_to_client
    db.commit()
    db.refresh(doc)

    return db.query(Document).options(
        joinedload(Document.uploader)
    ).filter(Document.id == doc_id).first()


# ── DELETE DOCUMENT ───────────────────────────────────────────────────────────

@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Deletes a document from both R2 (actual file) and the database (record).
    Order matters: delete from R2 first, then DB.
    If R2 delete fails we still remove the DB record to avoid orphans.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role == "employee":
        client = db.query(Client).filter(Client.id == doc.client_id).first()
        if not client or client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

    # Try to delete from R2 (don't crash if it fails — file may already be gone)
    try:
        delete_file(doc.file_url)
    except Exception:
        pass  # log this in production

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted successfully"}