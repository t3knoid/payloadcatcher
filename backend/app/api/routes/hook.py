from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.schemas.common import SafeErrorResponse
from app.api.schemas.webhook import WebhookAcceptedResponse
from app.services.webhook_ingestion import WebhookIngestionService, get_webhook_ingestion_service

router = APIRouter(tags=["hook"])


@router.post(
    "/hook/{clsid}",
    response_model=WebhookAcceptedResponse,
    summary="Accept webhook payload",
    description="Accept a provider-agnostic webhook payload, acknowledge quickly, and defer persistence work.",
    responses={
        400: {"model": SafeErrorResponse, "description": "Malformed request or invalid clsid."},
        404: {"model": SafeErrorResponse, "description": "Inbox does not exist or has expired."},
        413: {"model": SafeErrorResponse, "description": "Payload exceeds configured size limit."},
        415: {"model": SafeErrorResponse, "description": "Content-Type header is invalid."},
        500: {"model": SafeErrorResponse, "description": "Safe internal error envelope."},
    },
)
async def ingest_webhook(
    clsid: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: Annotated[WebhookIngestionService, Depends(get_webhook_ingestion_service)],
) -> WebhookAcceptedResponse:
    payload_raw = await request.body()
    prepared = service.prepare_ingestion(clsid, request, payload_raw)
    background_tasks.add_task(service.persist_ingestion, prepared)
    return WebhookAcceptedResponse(status="accepted", request_id=prepared.request_id)