import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiofiles
from pypdf import PdfReader

ProgressCallback = Callable[
    [int, str],
    Awaitable[None],
]  # 声明类型, 强制使用者必须传 async 函数，防止写出 `await 普通值` 这种运行时错误。


class UnsupportedDocumentError(Exception):
    pass


@dataclass
class ParseResult:
    text: str

    page_count: Optional[int]

    char_count: int


# 解析 TXT
async def parse_text_file(
    path: Path,
    progress: ProgressCallback,
) -> ParseResult:

    await progress(
        20,
        "Reading text file",
    )  # `progress`外部传进来的**异步回调函数**

    async with aiofiles.open(
        path,
        "r",
        encoding="utf-8",
        errors="replace",
    ) as file:
        text = await file.read()

    await progress(
        90,
        "Text extraction finished",
    )  # 剩下 10% 留给外层任务：保存文本到 `results/` 目录、标记任务完成。

    return ParseResult(
        text=text,
        page_count=None,
        char_count=len(text),
    )


# 解析PDF
async def parse_pdf_file(path: Path, progress: ProgressCallback) -> ParseResult:
    await progress(10, "Opening PDF")
    # PdfReader是同步阻塞，丢线程执行
    reader = await asyncio.to_thread(PdfReader, str(path))  # 必须传字符串

    # 拦截加密PDF
    if reader.is_encrypted:
        raise UnsupportedDocumentError("Encrypted PDF is not supported")

    total_pages = len(reader.pages)
    texts: list[str] = []
    if total_pages == 0:
        return ParseResult(text="", page_count=0, char_count=0)

    for index, page in enumerate(reader.pages):
        # page.extract_text同步阻塞，放到线程
        page_text = await asyncio.to_thread(
            page.extract_text
        )  # **pypdf 内置的同步成员方法**，由第三方库提供，不是我们写的。
        texts.append(page_text or "")

        # 计算进度：10%（打开）~90%（全部页面解析完）
        percentage = 10 + int((index + 1) / total_pages * 80)
        await progress(percentage, f"Parsed page {index + 1}/{total_pages}")

    # 页面之间用两个换行分隔
    text = "\n\n".join(texts)
    return ParseResult(text=text, page_count=total_pages, char_count=len(text))


# 统一入口
async def parse_document_file(
    path: Path,
    file_type: str,
    progress: ProgressCallback,
) -> ParseResult:

    if file_type == "txt":
        return await parse_text_file(
            path,
            progress,
        )

    if file_type == "pdf":
        return await parse_pdf_file(
            path,
            progress,
        )

    raise UnsupportedDocumentError(f"Unsupported file type: {file_type}")
