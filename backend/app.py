"""
A2UI Backend API

Security:
- Configurable CORS origins (env: A2UI_CORS_ORIGINS)
- Optional API key auth (env: A2UI_API_KEY) — disabled when unset
- Rate limiting via slowapi
- Input validation via Pydantic
- Security headers on all responses
- Request body size limits (1 MB)
"""

import logging
import os
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn

from content_styles import get_available_styles
from llm_providers import llm_service

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────

ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv(
        "A2UI_CORS_ORIGINS",
        "http://localhost:4200,http://localhost:5174,http://localhost:5173,http://localhost:3000",
    ).split(",")
]

API_KEY = os.getenv("A2UI_API_KEY")          # set to require auth; unset = open
MAX_BODY_BYTES = 1_000_000                    # 1 MB
DEBUG = os.getenv("A2UI_DEBUG", "false").lower() == "true"


# ── App Setup ──────────────────────────────────────────────────

app = FastAPI(
    title="A2UI API",
    docs_url="/api/docs" if DEBUG else None,   # hide docs in prod
    redoc_url=None,
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Combined security middleware: body-size check, auth, and response headers."""

    # ── Request body size limit ────────────────────────────────
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return JSONResponse(
            content={"error": "Request body too large"},
            status_code=413,
        )

    # ── Optional API-key auth ──────────────────────────────────
    if (
        API_KEY
        and request.url.path.startswith("/api/")
        and request.method != "OPTIONS"        # let CORS preflight through
    ):
        provided = request.headers.get("X-API-Key")
        if provided != API_KEY:
            return JSONResponse(
                content={"error": "Unauthorized"},
                status_code=401,
            )

    response = await call_next(request)

    # ── Security response headers ──────────────────────────────
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    return response


# ── Request Models ─────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., max_length=10_000)


class UserLocation(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    provider: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=100)
    history: List[HistoryMessage] = Field(default_factory=list)
    enableWebSearch: bool = False
    userLocation: Optional[UserLocation] = None
    contentStyle: str = Field(
        default="auto",
        max_length=30,
        description="Content style: 'auto' (default), 'analytical', 'content', 'comparison', 'howto', or 'quick'",
    )
    performanceMode: str = Field(
        default="auto",
        max_length=30,
        description="Performance mode: 'auto' (default), 'comprehensive', or 'optimized'",
    )

    @field_validator("history")
    @classmethod
    def limit_history(cls, v):
        if len(v) > 50:
            raise ValueError("History exceeds maximum of 50 messages")
        return v


# ── Routes ─────────────────────────────────────────────────────

@app.get("/api")
@limiter.limit("60/minute")
def home(request: Request):
    return JSONResponse(content={"message": "Welcome to the A2UI Python Backend!"})


@app.get("/api/providers")
@limiter.limit("60/minute")
def get_providers(request: Request):
    """
    Get available LLM providers and their models.

    Returns providers that have valid API keys configured.
    """
    providers = llm_service.get_available_providers()
    return JSONResponse(content={"providers": providers})


@app.get("/api/styles")
@limiter.limit("60/minute")
def get_styles(request: Request):
    """Return available content styles for the frontend."""
    return JSONResponse(content={"styles": get_available_styles()})


# A2UI Chat endpoint — returns structured A2UI responses
@app.post("/api/chat")
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Chat endpoint that returns A2UI protocol responses.

    Request body (validated via Pydantic):
    - message: The user's message (1–10 000 chars)
    - provider: Optional LLM provider ID (openai, anthropic, gemini)
    - model: Optional model ID for the provider
    - history: Optional list of previous messages [{role, content}] (max 50)
    - enableWebSearch: Optional boolean to enable web search tool
    - contentStyle: Content style ('auto', 'analytical', 'content', etc.)

    Returns:
    - text: Optional plain text response
    - a2ui: Optional A2UI protocol JSON for rich UI rendering
    """
    if not body.message.strip():
        return JSONResponse(
            content={"error": "Message is required"},
            status_code=400,
        )

    # If provider is specified, use LLM service
    if body.provider and body.model:
        try:
            history_dicts = [h.model_dump() for h in body.history]
            location_dict = body.userLocation.model_dump() if body.userLocation else None
            response = await llm_service.generate(
                body.message,
                body.provider,
                body.model,
                history=history_dicts,
                user_location=location_dict,
                content_style=body.contentStyle,
                performance_mode=body.performanceMode,
            )
            return JSONResponse(content=response)
        except ValueError as e:
            # Known errors (invalid provider, etc.)
            return JSONResponse(
                content={"error": str(e)},
                status_code=400,
            )
        except Exception as e:
            logger.exception("LLM error")
            return JSONResponse(
                content={
                    "text": "Something went wrong generating a response. Please try again.",
                    "_error": str(e),
                },
                status_code=500,
            )

    # No provider selected — tell the client to pick one
    return JSONResponse(
        content={"error": "No LLM provider selected. Choose a provider and model from the dropdown."},
        status_code=400,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=DEBUG,
    )
