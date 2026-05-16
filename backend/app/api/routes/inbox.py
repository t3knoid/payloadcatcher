from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.schemas.common import SafeErrorResponse
from app.api.schemas.inbox import InboxViewerQuery, InboxViewerResponse
from app.services.inbox_viewer import InboxViewerService, get_inbox_viewer_service

router = APIRouter(tags=["inbox"])


@router.get(
    "/inbox/{clsid}",
    response_model=InboxViewerResponse,
    summary="List inbox events",
    description="Return a public bearer-style inbox event listing with safe previews, masking, search, and pagination.",
    responses={
        400: {"model": SafeErrorResponse, "description": "Malformed clsid, cursor, or pagination input."},
        404: {"model": SafeErrorResponse, "description": "Inbox does not exist or has expired."},
        429: {"model": SafeErrorResponse, "description": "Too many requests for the current source IP."},
        500: {"model": SafeErrorResponse, "description": "Safe internal error envelope."},
    },
)
def get_inbox_view(
    clsid: str,
    request: Request,
    query: Annotated[InboxViewerQuery, Depends()],
    service: Annotated[InboxViewerService, Depends(get_inbox_viewer_service)],
) -> InboxViewerResponse:
    return service.get_inbox_view(clsid, query, request)