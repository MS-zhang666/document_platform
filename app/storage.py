from dataclasses import dataclass
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.config import Settings


# 自定义异常类
class UnsupportedFileType(Exception):
    pass


class FileTooLarge(Exception):
    pass


class InvalidFileContent(Exception):
    pass


# 快速定义保存数据的类
@dataclass
class StoredUpload:
    original_filename: str

    path: Path

    size_bytes: int

    extension: str

    content_type: str


def ensure_storage_dirs(
    settings: Settings,
) -> None:

    settings.uploads_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    settings.results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


async def save_upload(
    upload: UploadFile,
    document_id: str,
    settings: Settings,
) -> StoredUpload:
    """
    将上传文件分块保存到磁盘。

    不使用：
        content = await file.read()

    一次全部读进内存。
    """

    filename = Path(upload.filename or "upload").name  # 前端上传的文件名，也可能没有

    extension = Path(filename).suffix.lower()

    if extension not in {
        ".pdf",
        ".txt",
    }:
        raise UnsupportedFileType("Only PDF and TXT are supported")

    ensure_storage_dirs(settings)

    destination = settings.uploads_dir / f"{document_id}{extension}"  # 磁盘文件名

    size = 0
    # 读取文件
    try:
        async with aiofiles.open(
            destination,
            "wb",
        ) as output:
            while True:
                chunk = await upload.read(1024 * 1024)  # 每次读1MB

                if not chunk:
                    break

                size += len(chunk)

                if size > settings.max_upload_bytes:
                    raise FileTooLarge("Uploaded file is too large")

                await output.write(chunk)

        if size == 0:
            raise InvalidFileContent("Empty file")

        # PDF简单Magic Number检查
        if extension == ".pdf":
            async with aiofiles.open(
                destination,
                "rb",
            ) as saved:
                header = await saved.read(5)
            # 读取文件内容**最开头 5 个字节**。
            # 标准合法 PDF 文件，开头固定就是这 5 个字节：`%PDF-`
            if header != b"%PDF-":
                raise InvalidFileContent("Invalid PDF file")

        return StoredUpload(
            original_filename=filename,
            path=destination,
            size_bytes=size,
            extension=extension,
            content_type=(upload.content_type or "application/octet-stream"),
        )

    except Exception:
        destination.unlink(missing_ok=True)  # 删除文件，避免残留

        raise

    finally:
        await upload.close()


# Arq worker 解析完成后调用：把提取出来的文本，写入 `results_dir/{document_id}.txt`，utf-8 编码
async def write_result_text(
    document_id: str,
    text: str,
    settings: Settings,
) -> Path:
    """
    将解析结果写入共享存储。
    """

    ensure_storage_dirs(settings)

    path = settings.results_dir / f"{document_id}.txt"

    async with aiofiles.open(
        path,
        "w",
        encoding="utf-8",
    ) as file:
        await file.write(text)

    return path
