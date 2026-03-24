import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from grantflow.config import HOST, PORT, BASE_DIR
from grantflow.database import init_db
from grantflow.pipeline.logging import configure_structlog


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog(env=os.getenv("GRANTFLOW_ENV", "development"))
    init_db()
    yield


app = FastAPI(
    title="GrantFlow",
    description="Unified Government Grants API",
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
from grantflow.web.routes import router as web_router

app.include_router(api_router)
app.include_router(web_router)


def main():
    import uvicorn
    uvicorn.run("grantflow.app:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
