from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.schemas import (
    JobCreatedResponse,
    JobStatusResponse,
)
from app.services.job_services import (  # type: ignore
    InvalidJobStateError,
    JobNotFoundError,
    JobService,
    get_job_service,
)

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
)
async def get_job(
    job_id: str,
    service: Annotated[
        JobService,
        Depends(get_job_service),
    ],
):

    try:
        return await service.get_job(job_id)

    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        ) from exc


@router.post(
    "/{job_id}/cancel",
    response_model=JobStatusResponse,
)
async def cancel_job(
    job_id: str,
    service: Annotated[
        JobService,
        Depends(get_job_service),
    ],
):

    try:
        return await service.cancel_job(job_id)

    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        ) from exc

    except InvalidJobStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post(
    "/{job_id}/retry",
    response_model=JobCreatedResponse,
    status_code=202,
)
async def retry_job(
    job_id: str,
    service: Annotated[
        JobService,
        Depends(get_job_service),
    ],
):

    try:
        result = await service.retry_job(job_id)

        return {
            "job_id": (result["job_id"]),
            "document_id": (result["document_id"]),
            "status": (result["status"]),
        }

    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        ) from exc

    except InvalidJobStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
