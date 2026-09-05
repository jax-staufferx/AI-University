from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AuthStatus, LoginRequest, RegisterRequest
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _set_session_cookie(response: Response, username: str) -> None:
    response.set_cookie(
        auth_service.COOKIE_NAME,
        auth_service.make_session_token(username),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


@router.post("/register", response_model=AuthStatus)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords don't match")
    if auth_service.get_account_by_username(db, username) is not None:
        raise HTTPException(status_code=409, detail="That username is already taken")

    auth_service.create_account(db, username, payload.password)
    _set_session_cookie(response, username)
    return AuthStatus(authenticated=True, username=username)


@router.post("/login", response_model=AuthStatus)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    account = auth_service.authenticate(db, payload.username.strip(), payload.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    _set_session_cookie(response, account.username)
    return AuthStatus(authenticated=True, username=account.username)


@router.get("/status", response_model=AuthStatus)
def status(request: Request):
    token = request.cookies.get(auth_service.COOKIE_NAME)
    username = auth_service.verify_session_token(token)
    return AuthStatus(authenticated=username is not None, username=username)


@router.post("/logout", response_model=AuthStatus)
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME)
    return AuthStatus(authenticated=False)
