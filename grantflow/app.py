import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from grantflow.config import HOST, PORT, BASE_DIR
from grantflow.database import init_db
from grantflow.pipeline.logging import configure_structlog, bind_source_logger
from grantflow.ingest.run_all import run_all_ingestion

logger_app = bind_source_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog(env=os.getenv("GRANTFLOW_ENV", "development"))
    init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.get_event_loop().run_in_executor(None, run_all_ingestion),
        CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="daily_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,  # tolerate up to 1h delay (e.g. server restart at 02:00)
    )
    scheduler.start()
    logger_app.info("APScheduler started — daily ingestion at 02:00 UTC")
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
