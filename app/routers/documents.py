from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import (
    FileResponse,
)

from app.schemas import (
    DocumentResponse,
    JobCreatedResponse,
)
from app.services.document_service import (  # type: ignore
    DocumentNotFoundError,
    DocumentResultNotReady,
    DocumentService,
    get_document_service,
)
from app.services.job_services import (  # type: ignore
    DocumentNotFoundError as JobDocumentNotFoundError,
)
from app.services.job_services import (  # type: ignore
    InvalidJobStateError,
    JobService,
    get_job_service,
)
from app.storage import (
    FileTooLarge,
    InvalidFileContent,
    UnsupportedFileType,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=(status.HTTP_201_CREATED),
)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(...),
    ],
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
):

    try:
        return await service.upload(file)

    except UnsupportedFileType as exc:
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        ) from exc

    except InvalidFileContent as exc:
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        ) from exc

    except FileTooLarge as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: str,
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
):

    try:
        return await service.get(document_id)

    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        ) from exc


@router.post(
    "/{document_id}/parse",
    response_model=JobCreatedResponse,
    status_code=202,
)
async def parse_document(
    document_id: str,
    service: Annotated[
        JobService,
        Depends(get_job_service),
    ],
):

    try:
        result = await service.create_parse_job(document_id)

        return {
            "job_id": (result["job_id"]),
            "document_id": (result["document_id"]),
            "status": (result["status"]),
        }

    except JobDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        ) from exc

    except InvalidJobStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/result",
)
async def get_result(
    document_id: str,
    service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ],
):

    try:
        document, path = await service.get_result(document_id)

    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        ) from exc

    except DocumentResultNotReady as exc:
        raise HTTPException(
            status_code=409,
            detail=("Document result is not ready"),
        ) from exc

    output_name = f"{document.original_filename}.txt"

    return FileResponse(
        path=path,
        media_type=("text/plain; charset=utf-8"),
        filename=output_name,
    )
