import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response

from app.core.logging import request_id_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("payloadcatcher.request")

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = request_id_context.set(request_id)
        started = perf_counter()
        response: Response
        try:
            response = await call_next(request)
        except Exception:
            self.logger.exception("Unhandled request failure for %s", request.url.path)
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "Internal Server Error",
                    },
                    "request_id": request_id,
                },
            )
        finally:
            duration_ms = (perf_counter() - started) * 1000
            self.logger.info(
                "%s %s completed in %.2fms",
                request.method,
                request.url.path,
                duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        request_id_context.reset(token)
        return response
