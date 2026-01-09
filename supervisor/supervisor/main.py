"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from supervisor.config import get_settings
from supervisor.api import auth, rdmp, projects, samples, storage
from supervisor.database import Base, engine

settings = get_settings()

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
app.include_router(rdmp.router, prefix="/api/rdmp", tags=["rdmp"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(samples.router, prefix="/api", tags=["samples"])
app.include_router(storage.router, prefix="/api", tags=["storage"])


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
