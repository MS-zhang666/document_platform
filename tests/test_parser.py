import pytest

from app.parser import (
    parse_document_file,
)


@pytest.mark.asyncio
async def test_parse_text(
    tmp_path,
):

    path = tmp_path / "hello.txt"

    path.write_text(
        "Hello Async Agent",
        encoding="utf-8",
    )

    progress_values = []

    async def progress(
        value,
        message,
    ):

        progress_values.append(value)

    result = await parse_document_file(
        path,
        "txt",
        progress,
    )

    assert result.text == "Hello Async Agent"

    assert result.char_count == len("Hello Async Agent")

    assert progress_values
