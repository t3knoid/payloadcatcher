from typing import Any, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from app.api.errors import ApiError, api_error_handler, http_exception_handler, validation_exception_handler
from app.api.routes.bootstrap import router as bootstrap_router
from app.api.routes.health import router as health_router
from app.api.routes.hook import router as hook_router
from app.api.routes.inbox import router as inbox_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.cors import NetworkAwareCORSMiddleware
from app.middleware.request_context import RequestContextMiddleware


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
SPA_STATIC_FILES = {
    "favicon.png": FRONTEND_DIST_DIR / "favicon.png",
    "logo.png": FRONTEND_DIST_DIR / "logo.png",
    "logo_with_tag.png": FRONTEND_DIST_DIR / "logo_with_tag.png",
}


def _frontend_file_response(path: Path) -> FileResponse:
    return FileResponse(path)


def _build_frontend_file_handler(file_path: Path):
    async def serve_file() -> FileResponse:
        return _frontend_file_response(file_path)

    return serve_file


def _serve_frontend_index() -> FileResponse:
    if not FRONTEND_INDEX_FILE.is_file():
        raise StarletteHTTPException(status_code=503, headers={"Retry-After": "30"})
    return _frontend_file_response(FRONTEND_INDEX_FILE)


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

    for route_path, file_path in SPA_STATIC_FILES.items():
        if file_path.exists():
            app.add_api_route(f"/{route_path}", _build_frontend_file_handler(file_path), methods=["GET"], include_in_schema=False)

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    async def serve_frontend_asset(asset_path: str) -> FileResponse:
        asset_file = FRONTEND_DIST_DIR / "assets" / asset_path
        if not asset_file.is_file():
            raise StarletteHTTPException(status_code=404)
        return _frontend_file_response(asset_file)

    @app.get("/", include_in_schema=False)
    async def serve_frontend_home() -> FileResponse:
        return _serve_frontend_index()

    @app.get("/privacy", include_in_schema=False)
    async def serve_frontend_privacy() -> FileResponse:
        return _serve_frontend_index()

    @app.get("/inbox/{clsid}", include_in_schema=False)
    async def serve_frontend_inbox(clsid: str) -> FileResponse:
        return _serve_frontend_index()

    return app


app = create_app()
