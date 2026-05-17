from fastapi import APIRouter

router = APIRouter(tags=["operations"])


@router.get(
    "/healthz",
    summary="Health check",
    description="Return a lightweight process health signal for local development and container orchestration.",
)
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
