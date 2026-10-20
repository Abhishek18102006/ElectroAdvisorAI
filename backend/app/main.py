import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api import api_router
from app.data.init_db import init_db

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("electroadvisor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler: initializes SQLite database and seeds records on startup."""
    logger.info("Initializing ElectroAdvisor Backend...")
    try:
        init_db()
        logger.info("Database verified and seeded successfully.")
    except Exception as e:
        logger.error(f"Error during startup database init: {e}")
    yield
    logger.info("Shutting down ElectroAdvisor Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Production-grade AI Electronics Sales Assistant Backend. "
        "Understands natural language customer needs, tracks requirements state, "
        "filters products strictly by hard constraints, ranks using soft preferences, "
        "and recommends the top 2 grounded products with detailed trade-off analysis."
    ),
    lifespan=lifespan,
)

# CORS middleware for React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", summary="API Root", tags=["System"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_PREFIX}/health",
        "api_endpoints": {
            "products": f"{settings.API_V1_PREFIX}/products",
            "conversations": f"{settings.API_V1_PREFIX}/conversations",
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please verify your request.", "error": str(exc)},
    )
