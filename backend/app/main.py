from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import ApiError, api_error_handler
from app.api.routes.bootstrap import router as bootstrap_router
from app.api.routes.health import router as health_router
from app.api.routes.hook import router as hook_router
from app.api.routes.inbox import router as inbox_router
from app.core.config import get_settings
from app.core.logging import configure_logging
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
    app.add_exception_handler(ApiError, api_error_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
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
