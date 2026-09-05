import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.database import Base, engine
from app.routers import auth, modules, monitor, programs, sessions, topics
from app.services import auth as auth_service

app = FastAPI(
    title="Personal Learning Agent",
    description=(
        "Local single-user backend: researches any topic multi-source, teaches it through "
        "rotating active-learning methods, and quietly tracks which methods work for you."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path.startswith("/api/auth/"):
        return await call_next(request)
    token = request.cookies.get(auth_service.COOKIE_NAME)
    if not auth_service.is_valid_session_token(token):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return await call_next(request)


@app.exception_handler(anthropic.AuthenticationError)
def handle_anthropic_auth_error(request: Request, exc: anthropic.AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={"detail": "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in .env."},
    )


@app.exception_handler(anthropic.APIError)
def handle_anthropic_api_error(request: Request, exc: anthropic.APIError):
    return JSONResponse(status_code=502, content={"detail": f"Anthropic API error: {exc.message}"})


app.include_router(auth.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(modules.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")
app.include_router(programs.router, prefix="/api")


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}
