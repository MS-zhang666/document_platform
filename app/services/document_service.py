from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    UploadFile,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.config import (
    Settings,
    get_settings,
)
from app.database import get_db
from app.models import Document
from app.storage import save_upload


class DocumentNotFoundError(Exception):
    pass


class DocumentResultNotReady(Exception):
    pass


class DocumentService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
    ) -> None:

        self.db = db

        self.settings = settings

    async def upload(
        self,
        file: UploadFile,
    ) -> Document:

        document_id = uuid4().hex

        stored = await save_upload(
            file,
            document_id,
            self.settings,
        )  # 保存上传文件到磁盘，并返回 `StoredUpload` 对象

        document = Document(
            id=document_id,
            original_filename=(stored.original_filename),
            stored_filename=(stored.path.name),
            file_type=(stored.extension.removeprefix(".")),
            content_type=(stored.content_type),
            size_bytes=(stored.size_bytes),
            storage_path=str(stored.path),
            parse_status="uploaded",
        )

        try:
            self.db.add(document)

            await self.db.commit()

            await self.db.refresh(document)

            return document

        except Exception:
            await self.db.rollback()

            stored.path.unlink(missing_ok=True)  # 避免垃圾文件残留

            raise

    async def get(
        self,
        document_id: str,
    ) -> Document:  # 查询记录

        document = await self.db.get(
            Document,
            document_id,
        )  # await async_session.get(Model, pk) 固定用法

        if document is None:
            raise DocumentNotFoundError(document_id)

        return document

    async def get_result(
        self,
        document_id: str,
    ) -> tuple[
        Document,
        Path,
    ]:  # 获取文档解析输出结果

        document = await self.get(document_id)

        if document.parse_status != "completed" or not document.result_path:
            raise DocumentResultNotReady(document_id)

        path = Path(document.result_path)

        if not path.exists():
            raise DocumentResultNotReady(document_id)

        return document, path


async def get_document_service(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> DocumentService:

    return DocumentService(
        db=db,
        settings=settings,
    )
