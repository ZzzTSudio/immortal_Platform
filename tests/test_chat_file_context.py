import pytest

from app.chat_file_context import (
    ChatFileValidationError,
    build_chat_file_context,
)


class FakeUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        if size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_chat_file_context_decodes_gbk_text():
    upload = FakeUpload("说明.txt", "中文内容".encode("gbk"))

    context = await build_chat_file_context([upload])

    assert "[FILE 1: 说明.txt]" in context
    assert "中文内容" in context


@pytest.mark.asyncio
async def test_chat_file_context_skips_empty_content():
    upload = FakeUpload("empty.md", b"   \n\n")

    context = await build_chat_file_context([upload])

    assert context == ""


@pytest.mark.asyncio
async def test_chat_file_context_rejects_too_many_files():
    uploads = [FakeUpload(f"{i}.txt", b"x") for i in range(4)]

    with pytest.raises(ChatFileValidationError):
        await build_chat_file_context(uploads)


@pytest.mark.asyncio
async def test_chat_file_context_rejects_large_file():
    upload = FakeUpload("big.txt", b"x" * (5 * 1024 * 1024 + 1))

    with pytest.raises(ChatFileValidationError):
        await build_chat_file_context([upload])


@pytest.mark.asyncio
async def test_chat_file_context_rejects_unsupported_extension():
    upload = FakeUpload("bad.exe", b"x")

    with pytest.raises(ChatFileValidationError):
        await build_chat_file_context([upload])


@pytest.mark.asyncio
async def test_chat_file_context_truncates_in_file_order():
    first = FakeUpload("a.txt", ("甲 " * 200).encode("utf-8"))
    second = FakeUpload("b.txt", ("乙 " * 200).encode("utf-8"))

    context = await build_chat_file_context([first, second], max_tokens=20)

    assert context.startswith("[FILE 1: a.txt]")
    assert "[FILE 2: b.txt]" not in context
    assert "…(截断)" in context
