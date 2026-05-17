"""Auth endpoints — signup, login, current user.

Email/password auth for the MVP. JWT bearer tokens are minted on signup and
login; the current-user dependency below is the reusable hook future routes
should depend on once multi-user data isolation lands.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.database import get_session
from app.models.daily_rhythm import DailyRhythm
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    UserOut,
)
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.services.daily_rhythm import (
    DEFAULT_AWAKE_END,
    DEFAULT_AWAKE_START,
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# `auto_error=False` so missing headers surface as our own 401, not 403.
_bearer_scheme = HTTPBearer(auto_error=False)


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
    )


def _auth_response(user: User) -> AuthResponse:
    token = create_access_token(subject=str(user.id))
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=_user_out(user),
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Resolve the user from an Authorization: Bearer <token> header.

    Raises 401 on missing, malformed, expired, or unknown tokens.
    """
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        raise invalid

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise invalid

    user = session.get(User, user_id)
    if user is None:
        raise invalid
    return user


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(body: SignupRequest, session: Session = Depends(get_session)) -> AuthResponse:
    """Create a new user, seed their Daily Rhythm defaults, and issue a token.

    Does not create default calendars, categories, events, or summaries —
    auth MVP keeps account creation deliberately minimal.
    """
    email = normalize_email(body.email)

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    user = User(
        name=body.name,
        email=email,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Seed Daily Rhythm with system defaults for the new user so their first
    # GET /daily-rhythm returns their own row, not the legacy single-user row.
    session.add(
        DailyRhythm(
            user_id=user.id,
            awake_start_time=DEFAULT_AWAKE_START,
            awake_end_time=DEFAULT_AWAKE_END,
            suggestions_start_time=DEFAULT_SUGGESTIONS_START,
            suggestions_end_time=DEFAULT_SUGGESTIONS_END,
        )
    )
    session.commit()

    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> AuthResponse:
    """Verify credentials and return a fresh access token."""
    email = normalize_email(body.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(current_user)
