from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.schemas.common import SafeErrorResponse
from app.api.schemas.inbox import ProvisionInboxQuery, ProvisionInboxResponse, VisitMetadataUpdateRequest
from app.services.inbox_provisioning import InboxProvisioningService, get_inbox_provisioning_service

router = APIRouter(prefix="/api", tags=["inbox"])


@router.get(
    "/bootstrap",
    response_model=ProvisionInboxResponse,
    summary="Provision inbox callback URL",
    description="Create or reuse the active inbox callback URL for the current browser session.",
    responses={
        429: {"model": SafeErrorResponse, "description": "Too many requests for the current source IP."},
        500: {"model": SafeErrorResponse, "description": "Safe internal error envelope."},
    },
)
def provision_inbox(
    request: Request,
    response: Response,
    query: Annotated[ProvisionInboxQuery, Depends()],
    service: Annotated[InboxProvisioningService, Depends(get_inbox_provisioning_service)],
) -> ProvisionInboxResponse:
    result = service.provision_inbox(request, query)
    service.bind_session_cookie(response, result.clsid)
    return ProvisionInboxResponse(
        clsid=result.clsid,
        callback_url=result.callback_url,
        viewer_url=result.viewer_url,
        expires_at=result.expires_at,
        new_session=result.new_session,
    )


@router.post(
    "/visit-metadata",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update visit metadata",
    description="Persist consented visit metadata that should not be transported in URL parameters.",
    responses={
        422: {"model": SafeErrorResponse, "description": "Validation failed for the visit metadata payload."},
        404: {"model": SafeErrorResponse, "description": "Active inbox or visit metadata not found for session."},
        429: {"model": SafeErrorResponse, "description": "Too many requests for the current source IP."},
        500: {"model": SafeErrorResponse, "description": "Safe internal error envelope."},
    },
)
def update_visit_metadata(
    request: Request,
    payload: VisitMetadataUpdateRequest,
    service: Annotated[InboxProvisioningService, Depends(get_inbox_provisioning_service)],
) -> Response:
    service.update_visit_metadata(request, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)