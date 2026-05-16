from __future__ import annotations

import pytest
import yaml

from app.api.errors import ApiError
from app.core.config import Settings
from app.services.webhook_ingestion import WebhookIngestionService


def _build_service(*, hook_payload_max_bytes: int = 1024) -> WebhookIngestionService:
    settings = Settings(
        _env_file=None,
        hook_payload_max_bytes=hook_payload_max_bytes,
    )
    return WebhookIngestionService(session=None, session_factory=None, settings=settings)


def test_normalize_content_type_lowercases_and_strips_parameters() -> None:
    service = _build_service()

    normalized = service.normalize_content_type("Application/JSON; charset=utf-8")

    assert normalized == "application/json"


def test_normalize_content_type_rejects_invalid_media_type() -> None:
    service = _build_service()

    with pytest.raises(ApiError) as excinfo:
        service.normalize_content_type("not-a-media-type")

    assert excinfo.value.status_code == 415
    assert excinfo.value.error_code == "unsupported_media_type"


def test_validate_payload_size_rejects_oversized_payload() -> None:
    service = _build_service(hook_payload_max_bytes=4)

    with pytest.raises(ApiError) as excinfo:
        service.validate_payload_size(b"12345")

    assert excinfo.value.status_code == 413
    assert excinfo.value.error_code == "payload_too_large"


def test_render_payload_yaml_falls_back_for_malformed_json() -> None:
    service = _build_service()

    rendered = service.render_payload_yaml(b'{"foo": }', "application/json")

    assert yaml.safe_load(rendered) == {"text": '{"foo": }'}
