import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.database import Base, engine
from app.routers import modules, monitor, sessions, topics

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


@app.exception_handler(anthropic.AuthenticationError)
def handle_anthropic_auth_error(request: Request, exc: anthropic.AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={"detail": "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in .env."},
    )


@app.exception_handler(anthropic.APIError)
def handle_anthropic_api_error(request: Request, exc: anthropic.APIError):
    return JSONResponse(status_code=502, content={"detail": f"Anthropic API error: {exc.message}"})


app.include_router(topics.router)
app.include_router(modules.router)
app.include_router(sessions.router)
app.include_router(monitor.router)


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}
