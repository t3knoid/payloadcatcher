import contextvars
import logging

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(getattr(handler, "_payloadcatcher_default", False) for handler in root_logger.handlers):
        default_handler = logging.StreamHandler()
        default_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )
        default_handler.addFilter(RequestIdFilter())
        default_handler._payloadcatcher_default = True  # type: ignore[attr-defined]
        root_logger.addHandler(default_handler)

    _configured = True
