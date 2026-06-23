"""企业用工与社保合规智能平台 API 入口。"""
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database import init_db, settings
from app.response import ok
from app.routers import admin, chat, feedback, project_docs


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store"
        return response


class RequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.buckets: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        upload_paths = ("/sources/upload", "/vector-documents/upload", "/chat-with-file")
        limit = settings.max_upload_bytes if request.url.path.endswith(upload_paths) else settings.max_request_bytes
        if content_length and int(content_length) > limit:
            return JSONResponse(status_code=413, content={"detail": "请求体过大"})

        client = request.client.host if request.client else "unknown"
        now = monotonic()
        bucket = self.buckets[client]
        while bucket and now - bucket[0] > settings.rate_limit_window_seconds:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_max_requests:
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
        bucket.append(now)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="企业用工与社保合规智能平台 API",
    description="前后端分离、多租户隔离、LangChain/Dify/RAGFlow 可配置接入的企业合规智能问答平台。",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestGuardMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Code"],
)

app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(project_docs.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": exc.detail, "data": None})


@app.get("/")
async def root():
    return ok(
        {
            "name": settings.app_name,
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/health",
        }
    )


@app.get("/health")
async def health_check():
    return ok({"status": "healthy", "database": settings.db_name})
