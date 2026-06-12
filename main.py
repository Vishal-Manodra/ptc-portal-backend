# main.py
import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

print("PYTHON:", sys.executable)
print("VERSION:", sys.version)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import os

from database import engine, Base
from routes.auth_routes import router as auth_router
from routes.clients import router as clients_router
from routes.documents import router as documents_router
from routes.tasks import router as tasks_router
from routes.whatsapp import router as whatsapp_router
from routes.services import router as services_router
from routes.gst import router as gst_router
from routes.workflows import router as workflow_router


# ── Lifespan — runs on startup and shutdown ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables (skips existing ones — always safe)
    Base.metadata.create_all(bind=engine)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PTC Portal API",
    description="CA Practice Management Platform",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Swagger: replace OAuth2 flow with plain Bearer token ─────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="PTC Portal API",
        version="1.0.0",
        description="CA Practice Management Platform",
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    schema["security"] = [{"HTTPBearer": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi


# ── CORS ──────────────────────────────────────────────────────────────────────
# Pull allowed origins from .env in production:
#   ALLOWED_ORIGINS=https://your-app.vercel.app,https://staging.your-app.vercel.app
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_extra_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        *_extra_origins,          # ← production Vercel URL goes in .env
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(documents_router)
app.include_router(tasks_router)
app.include_router(whatsapp_router)
app.include_router(services_router)
app.include_router(gst_router)
app.include_router(workflow_router)

# ── Utility endpoints ─────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "PTC Portal API is running"}


