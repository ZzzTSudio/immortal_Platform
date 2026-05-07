"""Document cleanup pipeline before chunking."""

from __future__ import annotations

import hashlib
import html
import re
from collections import Counter

from bs4 import BeautifulSoup

try:
    from readability import Document
except ImportError:  # pragma: no cover - optional fallback
    Document = None  # type: ignore[assignment]

_HTML_TAG_RE = re.compile(r"<[a-zA-Z!/][^>]*>")
_TOC_RE = re.compile(r"(目录|table\s+of\s+contents|chapter)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def _normalize_lines(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _simhash(text: str, bits: int = 64) -> int:
    tokens = re.findall(r"\w+|[\u4e00-\u9fff]", text.lower())
    if not tokens:
        return 0
    weights = [0] * bits
    for token in tokens:
        digest = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(bits):
            weights[i] += 1 if digest & (1 << i) else -1
    value = 0
    for i, weight in enumerate(weights):
        if weight > 0:
            value |= 1 << i
    return value


def _simhash_similarity(left: int, right: int, bits: int = 64) -> float:
    distance = (left ^ right).bit_count()
    return 1.0 - distance / bits


def _dedupe_paragraphs(text: str, threshold: float = 0.9) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\n", text) if p.strip()]
    seen_md5: set[str] = set()
    seen_hashes: list[int] = []
    kept: list[str] = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph)
        digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        if digest in seen_md5:
            continue
        fingerprint = _simhash(normalized)
        if any(_simhash_similarity(fingerprint, old) >= threshold for old in seen_hashes):
            continue
        seen_md5.add(digest)
        seen_hashes.append(fingerprint)
        kept.append(paragraph)
    return "\n\n".join(kept)


def _strip_html(text: str) -> str:
    if not _HTML_TAG_RE.search(text):
        return html.unescape(text)
    source = text
    if Document is not None:
        try:
            source = Document(text).summary()
        except Exception:
            source = text
    soup = BeautifulSoup(source, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n")


def _remove_repeated_headers_footers(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    counts = Counter(line for line in lines if len(line) <= 40)
    repeated = {line for line, count in counts.items() if count > 3}
    return "\n".join(line for line in lines if line not in repeated)


def _page_numbers_are_discontinuous(page_text: str) -> bool:
    nums = [int(m.group(1)) for line in page_text.splitlines() if (m := _PAGE_NUMBER_RE.match(line))]
    if len(nums) < 2:
        return True
    return any(b - a != 1 for a, b in zip(nums, nums[1:]))


def remove_toc_cover_pages(pages: list[str]) -> list[str]:
    if not pages:
        return pages
    drop_until = 0
    for idx, page in enumerate(pages[:3]):
        if _TOC_RE.search(page) and _page_numbers_are_discontinuous(page):
            drop_until = idx + 1
    return pages[drop_until:]


def clean_text(text: str) -> str:
    """Run the required cleanup pipeline in order."""
    cleaned = _normalize_lines((text or "").encode("utf-8", errors="ignore").decode("utf-8"))
    cleaned = _dedupe_paragraphs(cleaned, threshold=0.9)
    cleaned = _strip_html(cleaned)
    cleaned = _remove_repeated_headers_footers(cleaned)
    cleaned = _dedupe_paragraphs(cleaned, threshold=0.9)
    return _normalize_lines(cleaned)


def clean_document(text: str, pages: list[str] | None = None) -> str:
    if pages is not None:
        pages = remove_toc_cover_pages(pages)
        text = "\n\n".join(pages)
    return clean_text(text)

