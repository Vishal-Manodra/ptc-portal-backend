# routes/auth_routes.py
# This file exposes two HTTP endpoints:
#   POST /auth/login   → takes email + password, returns a JWT token
#   POST /auth/register → creates a new user (admin only in production)
#   GET  /auth/me      → returns the current logged-in user's info

import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import (
    GoogleLoginRequest,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    admin_only,
    any_authenticated_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

# APIRouter = a mini-app that groups related routes
# prefix means all routes here start with /auth
router = APIRouter(prefix="/auth", tags=["Authentication"])


def create_token_response(user: User) -> TokenResponse:
    token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
            "name": user.name,
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        name=user.name,
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login endpoint.
    Frontend sends:  { "email": "ca@firm.com", "password": "secret" }
    Returns:         { "access_token": "eyJ...", "role": "admin", "name": "CA Mehta" }

    The frontend stores this token and sends it with every future request
    in the header:  Authorization: Bearer eyJ...
    """
    # Step 1: find the user by email
    user = db.query(User).filter(User.email == request.email).first()

    # Step 2: check password — we use a generic error message intentionally
    # Never say "email not found" or "wrong password" separately —
    # that tells attackers which part is wrong
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Step 3: check account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    # Step 4: create the JWT token
    # "sub" (subject) = user ID as a string — standard JWT convention
    return create_token_response(user)


@router.post("/google", response_model=TokenResponse)
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured",
        )

    try:
        google_user = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            client_id,
        )
    except (GoogleAuthError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        )

    email = google_user.get("email")
    if not email or not google_user.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )

    user = (
        db.query(User)
        .filter(func.lower(User.email) == email.lower())
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No portal account exists for this Google email",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    return create_token_response(user)


@router.post("/register", response_model=UserOut)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),   # only admin can create users
):
    """
    Creates a new user (employee or client login account).
    Only the admin (CA) can call this endpoint.

    Frontend sends:
    {
        "name": "Priya Nair",
        "email": "priya@firm.com",
        "password": "TempPass@123",
        "role": "employee",
        "phone": "9876543210"
    }
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Validate role
    allowed_roles = ("admin", "employee","manager", "client")
    if user_data.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(allowed_roles)}",
        )

    # Create the user — hash the password before saving
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        phone=user_data.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)   # reload from DB to get the generated id and created_at

    return new_user


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(any_authenticated_user)):
    """
    Returns the currently logged-in user's profile.
    The frontend calls this on app load to know who is logged in
    and what role they have (to show the right sidebar, etc.)
    """
    return current_user


@router.get("/employees", response_model=list[UserOut])
def get_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(any_authenticated_user),
):
    """
    Returns a list of all administrative and employee users.
    """
    return db.query(User).filter(User.role.in_(["admin","manager","employee"])).all()
