"""Main FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from supervisor.config import get_settings
from supervisor.api import auth, rdmp, projects, samples, storage, supervisors, operational, rdmp_management, remediation, ingest_template, lab_activity, lab_status
from supervisor.discovery import api as discovery_api
from supervisor.database import Base, engine

_log = logging.getLogger(__name__)

settings = get_settings()

# Guard: reject default dev secret key in production
_DEV_SECRET = "dev-secret-key-change-in-production"
if settings.secret_key == _DEV_SECRET:
    if settings.supervisor_env == "production":
        raise RuntimeError(
            "Refusing to start: secret_key is the dev default. "
            "Set SECRET_KEY in .env or environment."
        )
    _log.warning("Running with default dev secret key. Do not use in production.")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RDM Supervisor",
    description="Metadata-first Research Data Management supervisor service",
    version="1.0.0",
    redirect_slashes=False,  # Prevent 307 redirects that drop Authorization headers
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(supervisors.router, prefix="/api/supervisors", tags=["supervisors"])
app.include_router(rdmp.router, prefix="/api/rdmp", tags=["rdmp"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(samples.router, prefix="/api", tags=["samples"])
app.include_router(storage.router, prefix="/api", tags=["storage"])
app.include_router(operational.router, prefix="/api/ops", tags=["operational"])
app.include_router(rdmp_management.router, prefix="/api", tags=["rdmp-management"])
app.include_router(discovery_api.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(remediation.router, prefix="/api", tags=["remediation"])
app.include_router(ingest_template.router, prefix="/api", tags=["ingest-template"])
app.include_router(lab_activity.router, prefix="/api", tags=["lab-activity"])
app.include_router(lab_status.router, prefix="/api/supervisors", tags=["lab-status"])


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rdm-supervisor"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "RDM Supervisor",
        "version": "1.0.0",
        "docs": "/docs"
    }
