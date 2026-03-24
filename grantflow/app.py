import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from grantflow.config import HOST, PORT, BASE_DIR
from grantflow.database import init_db
from grantflow.pipeline.logging import configure_structlog, bind_source_logger
from grantflow.ingest.run_all import run_all_ingestion
from grantflow.ingest.run_state import run_state_ingestion

logger_app = bind_source_logger("app")

# Module-level scheduler so tests and external code can inspect registered jobs
scheduler = AsyncIOScheduler()

# Rate limiter — keyed on X-API-Key header (falls back to IP for public routes)
limiter = Limiter(
    key_func=lambda request: request.headers.get("x-api-key", get_remote_address(request))
)


async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return consistent {error_code, message} shape with Retry-After header."""
    retry_after = getattr(exc, "retry_after", None)
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Retry-After header shows seconds until reset.",
            }
        },
        headers=headers,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog(env=os.getenv("GRANTFLOW_ENV", "development"))
    init_db()

    scheduler.add_job(
        lambda: asyncio.get_event_loop().run_in_executor(None, run_all_ingestion),
        CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="daily_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,  # tolerate up to 1h delay (e.g. server restart at 02:00)
    )
    scheduler.add_job(
        lambda: asyncio.get_event_loop().run_in_executor(None, run_state_ingestion),
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC"),
        id="weekly_state_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger_app.info("APScheduler started — daily ingestion at 02:00 UTC")
    logger_app.info("APScheduler started — weekly state ingestion at Sunday 03:00 UTC")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="GrantFlow",
    description="Unified Government Grants API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "opportunities",
            "description": "Search and retrieve grant opportunities from Grants.gov, SAM.gov, and state portals.",
        },
    ],
    lifespan=lifespan,
)

# Attach limiter and rate-limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Analytics middleware — registers after CORS, captures all API requests non-blocking
from grantflow.analytics.middleware import setup_analytics_middleware
setup_analytics_middleware(app)

# Static files
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
from grantflow.api.routes import router as api_router
from grantflow.api.keys import router as keys_router
from grantflow.web.routes import router as web_router

app.include_router(api_router)
app.include_router(keys_router)
app.include_router(web_router)


def main():
    import uvicorn
    uvicorn.run("grantflow.app:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
