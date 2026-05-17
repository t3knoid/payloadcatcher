from typing import Any, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import ApiError, api_error_handler, http_exception_handler, validation_exception_handler
from app.api.routes.bootstrap import router as bootstrap_router
from app.api.routes.health import router as health_router
from app.api.routes.hook import router as hook_router
from app.api.routes.inbox import router as inbox_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.cors import NetworkAwareCORSMiddleware
from app.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"displayRequestDuration": True},
    )
    app.add_exception_handler(ApiError, cast(Any, api_error_handler))
    app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))

    app.add_middleware(
        NetworkAwareCORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_origin_networks=settings.cors_allow_origin_networks,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(bootstrap_router)
    app.include_router(hook_router)
    app.include_router(inbox_router)
    app.include_router(health_router)

    return app


app = create_app()
