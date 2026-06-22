from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import admin_or_employee
from database import get_db
from models import DocumentRegister
from schemas import (
    DocumentRegisterCreate,
    DocumentRegisterOut,
    DocumentRegisterReturn,
)

router = APIRouter(
    prefix="/document-register",
    tags=["Document Register"],
)


@router.post(
    "/",
    response_model=DocumentRegisterOut,
)
def register_in(
    data: DocumentRegisterCreate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_or_employee),
):
    entry = DocumentRegister(
        client_id=data.client_id,
        document_name=data.document_name,
        document_details=data.document_details,
        collected_by=data.collected_by,
        remarks=data.remarks,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


@router.patch(
    "/{entry_id}/return",
    response_model=DocumentRegisterOut,
)
def register_out(
    entry_id: int,
    data: DocumentRegisterReturn,
    db: Session = Depends(get_db),
    current_user=Depends(admin_or_employee),
):
    entry = (
        db.query(DocumentRegister)
        .filter(DocumentRegister.id == entry_id)
        .first()
    )

    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Entry not found",
        )

    entry.returned_to = data.returned_to
    entry.returned_by = data.returned_by
    entry.returned_at = datetime.utcnow()

    if data.remarks:
        entry.remarks = data.remarks

    db.commit()
    db.refresh(entry)

    return entry


@router.get(
    "/client/{client_id}",
    response_model=list[DocumentRegisterOut],
)
def get_entries(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_or_employee),
):
    return (
        db.query(DocumentRegister)
        .filter(DocumentRegister.client_id == client_id)
        .order_by(DocumentRegister.collected_at.desc())
        .all()
    )
