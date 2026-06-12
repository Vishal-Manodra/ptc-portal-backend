    # auth.py
    # This file handles everything related to identity:
    #   - Hashing passwords before saving to DB (so we never store plain text)
    #   - Verifying passwords at login
    #   - Creating JWT tokens after successful login
    #   - Reading and validating JWT tokens on every protected request
    #   - A "get_current_user" dependency that any route can use to
    #     know WHO is making the request and WHAT role they have

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
from database import get_db
from models import User

load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))
# ── PASSWORD HASHING ──────────────────────────────────────────────────────────
# CryptContext tells passlib to use bcrypt for hashing.
# bcrypt is slow by design — makes brute-force attacks impractical.
# "deprecated=auto" means if a weaker hash is found it gets upgraded automatically.
import bcrypt
def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
# ── JWT TOKEN ─────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT token containing the user's info.
    "data" is a dict like:
        {"sub": "3", "role": "admin", "name": "CA Mehta"}
    "sub" = subject = user ID (standard JWT field name)
    The token looks like three base64 strings joined by dots:
        header.payload.signature
    Anyone can decode header and payload, but the signature
    proves it came from us and hasn't been tampered with.
    """
    to_encode = data.copy()
    # Set expiry time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # "exp" is a standard JWT claim — jose checks this automatically
    to_encode.update({"exp": expire})
    # Sign the token with our SECRET_KEY using HS256
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.
    Raises an error if:
    - the token is malformed
    - the signature doesn't match (tampered)
    - the token has expired
    Returns the payload dict if valid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
# ── OAUTH2 SCHEME ─────────────────────────────────────────────────────────────
# This tells FastAPI: "tokens come from the Authorization header as Bearer tokens"
# It also makes the /docs page show a login button for testing
# tokenUrl="/auth/login" = the endpoint where tokens are issued
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
oauth2_scheme = HTTPBearer()
# ── CURRENT USER DEPENDENCY─────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials  # extracts the token from "Bearer <token>"
    payload = decode_token(token)
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user ID",
        )
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user
# ── ROLE GUARD FACTORIES ───────────────────────────────────────────────────────
# These are helper functions that create role-checking dependencies.
# Usage in a route:  current_user = Depends(require_roles("admin", "employee"))
# If the user's role isn't in the allowed list → 403 Forbidden

def require_roles(*allowed_roles: str):
    """
    Returns a FastAPI dependency that checks the current user's role.
    Example:
        @router.get("/clients")
        def list_clients(user = Depends(require_roles("admin", "employee"))):
            ...
        # clients cannot access this route — they get 403
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker
# Pre-built role guards — import and use these directly in routes
# Instead of writing Depends(require_roles("admin")) every time

def admin_only(current_user: User = Depends(get_current_user)) -> User:
    """Only CA admin can access this route."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action",
        )
    return current_user

def admin_or_employee(current_user: User = Depends(get_current_user)) -> User:
    """Admin and employees can access — clients cannot."""
    if current_user.role not in ("admin","manager","employee"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot access this resource",
        )
    return current_user

def any_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    """Any logged-in user (admin, employee, or client) can access."""
    return current_user 