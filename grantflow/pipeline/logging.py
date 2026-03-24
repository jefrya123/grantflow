import logging
import sys
import structlog


def configure_structlog(env: str = "development") -> None:
    """Call once at app startup. env='production' emits JSON; else colored key-value."""
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if env == "production":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # Route stdlib logging into structlog pipeline
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)


def bind_source_logger(source: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger with source bound. Use in every ingest module."""
    return structlog.get_logger().bind(source=source)
