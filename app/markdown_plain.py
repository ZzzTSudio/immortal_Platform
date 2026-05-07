"""Strip common Markdown / markup from model output for chat-style plain text."""

from __future__ import annotations

import re


def strip_markdown_like_to_plain(s: str) -> str:
    """
    Best-effort conversion of LLM Markdown to plain text (no new deps).
    Safe to call multiple times on already-plain strings.
    """
    if not s:
        return s
    text = s

    # Fenced code blocks: keep inner text, drop fences
    text = re.sub(r"```[^\n]*\n([\s\S]*?)```", r"\1", text)
    text = re.sub(r"```([\s\S]*?)```", r"\1", text)

    # HTML tags (models sometimes emit <br>, <strong>, etc.)
    text = re.sub(r"<[^>]+>", "", text)

    # Markdown tables: separator rows; pipe-heavy lines -> spaces between cells
    text = re.sub(r"(?m)^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?)+\s*\|?\s*$", "", text)

    def _pipe_row(m: re.Match[str]) -> str:
        line = m.group(0)
        if line.count("|") >= 2:
            return re.sub(r"\|+", " ", line)
        return line

    text = re.sub(r"(?m)^[^\n]*\|[^\n]*$", _pipe_row, text)

    # Images ![alt](url) -> alt
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Bare URLs in angle brackets
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)

    # Headers at line start
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)

    # Blockquotes
    text = re.sub(r"(?m)^>\s?", "", text)

    # Horizontal rules
    text = re.sub(r"(?m)^\s*([-*_])(?:\s*\1){2,}\s*$", "", text)

    # Ordered / unordered list markers at line start
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)

    # Strikethrough
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # Inline code (single backticks, non-greedy)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Bold / italic: repeat to handle simple nesting
    for _ in range(4):
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)", r"\1", text)
        text = re.sub(r"(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)", r"\1", text)

    # Remaining stray emphasis markers (single chars left by odd counts)
    text = text.replace("**", "").replace("__", "")

    # Collapse excessive blank lines from removed blocks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def assistant_plain_for_display(raw: str) -> str:
    """Strip Markdown-like markup, then apply bracket emoticon substitution (assistant only)."""
    from app.bracket_emoticons import substitute_bracket_emoticons

    return substitute_bracket_emoticons(strip_markdown_like_to_plain(raw))
