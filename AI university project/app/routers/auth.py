from fastapi import APIRouter, HTTPException, Request, Response

from app.schemas import AuthStatus, LoginRequest
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@router.post("/login", response_model=AuthStatus)
def login(payload: LoginRequest, response: Response):
    if not auth_service.check_password(payload.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    response.set_cookie(
        auth_service.COOKIE_NAME,
        auth_service.make_session_token(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return AuthStatus(authenticated=True)


@router.get("/status", response_model=AuthStatus)
def status(request: Request):
    token = request.cookies.get(auth_service.COOKIE_NAME)
    return AuthStatus(authenticated=auth_service.is_valid_session_token(token))


@router.post("/logout", response_model=AuthStatus)
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME)
    return AuthStatus(authenticated=False)
