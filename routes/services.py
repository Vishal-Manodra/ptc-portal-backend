from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Service
from auth import any_authenticated_user

router = APIRouter(prefix="/services", tags=["Services"])

@router.get("")
def list_services(db: Session = Depends(get_db), current_user=Depends(any_authenticated_user)):
    return db.query(Service).all()