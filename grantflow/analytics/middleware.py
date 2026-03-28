"""Non-blocking analytics event recording middleware."""
import time
from datetime import datetime, timezone

from fastapi import FastAPI
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import Response


def record_api_event(
    *,
    ts: str,
    path: str,
    method: str,
    api_key_prefix: str | None,
    query_string: str | None,
    status_code: int,
    duration_ms: float,
) -> None:
    """Insert one ApiEvent row. Wrapped in try/except so analytics never crashes the app."""
    try:
        from grantflow.database import SessionLocal
        from grantflow.models import ApiEvent

        event = ApiEvent(
            ts=ts,
            path=path,
            method=method,
            api_key_prefix=api_key_prefix,
            query_string=query_string,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        session = SessionLocal()
        try:
            session.add(event)
            session.commit()
        finally:
            session.close()
    except Exception:
        pass  # analytics must never crash the app


def setup_analytics_middleware(app: FastAPI) -> None:
    """Register the analytics capture middleware via @app.middleware('http')."""

    @app.middleware("http")
    async def analytics_middleware(request: Request, call_next):
        # Skip static file paths
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000.0

        ts = datetime.now(timezone.utc).isoformat()
        raw_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key", "")
        api_key_prefix = raw_key[:8] if raw_key else None
        query_string = str(request.url.query) or None

        # Attach as a background task so it runs after the response is sent
        existing_bg = response.background
        new_task = BackgroundTask(
            record_api_event,
            ts=ts,
            path=request.url.path,
            method=request.method,
            api_key_prefix=api_key_prefix,
            query_string=query_string,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        if existing_bg is None:
            response.background = new_task
        else:
            # Chain: run existing tasks then our new one
            from starlette.background import BackgroundTasks as StarletteBackgroundTasks
            tasks = StarletteBackgroundTasks()
            tasks.add_task(existing_bg)
            tasks.add_task(
                record_api_event,
                ts=ts,
                path=request.url.path,
                method=request.method,
                api_key_prefix=api_key_prefix,
                query_string=query_string,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            response.background = tasks

        return response
