"""Text chunking for knowledge ingestion (plan §10).

Splits cleaned text into ~1000-character chunks with ~150-character overlap,
splitting on paragraph then sentence boundaries.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Chunk:
    content: str
    chunk_index: int
    chunk_metadata: dict


# ── Cleaning ──────────────────────────────────────────────────────────────


def clean_text(text: str) -> str:
    """Normalise whitespace, strip control characters, unify newlines."""
    # Strip control characters (keep newlines, tabs, spaces)
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t", " ") or unicodedata.category(ch)[0] != "C"
    )
    # Collapse runs of whitespace (but preserve paragraph breaks)
    text = re.sub(r"[^\S\n]+", " ", text)
    # Normalise newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Chunking ──────────────────────────────────────────────────────────────


def _split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries (period, !, ?, followed by space or end)."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
    title: str = "",
    filename: str = "",
) -> list[Chunk]:
    """Split *text* into overlapping chunks.

    Strategy:
    1. Split on double-newlines (paragraphs).
    2. Accumulate paragraphs until chunk_size is exceeded.
    3. If a single paragraph exceeds chunk_size, split it by sentences.
    4. Overlap is achieved by carrying the last `overlap` characters forward.
    """
    text = clean_text(text)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0
    carry = ""
    char_offset = 0

    for para in paragraphs:
        para_len = len(para)

        # If a single paragraph is too large, split by sentences
        if para_len > chunk_size:
            # Flush current buffer first
            if current_parts:
                _flush_chunk(
                    chunks, current_parts, carry, char_offset, title, filename
                )
                char_offset += sum(len(p) for p in current_parts) + 2 * len(current_parts)
                last_text = "\n\n".join(current_parts)
                carry = last_text[-overlap:] if len(last_text) > overlap else last_text
                current_parts = []
                current_len = 0

            sentences = _split_sentences(para)
            sub_parts: list[str] = []
            sub_len = 0
            for sent in sentences:
                if sub_len + len(sent) > chunk_size and sub_parts:
                    _flush_chunk(
                        chunks, sub_parts, carry, char_offset, title, filename
                    )
                    char_offset += sum(len(p) for p in sub_parts) + 2 * len(sub_parts)
                    last_text = "\n\n".join(sub_parts)
                    carry = last_text[-overlap:] if len(last_text) > overlap else last_text
                    sub_parts = []
                    sub_len = 0
                sub_parts.append(sent)
                sub_len += len(sent)

            if sub_parts:
                current_parts = sub_parts
                current_len = sub_len
            continue

        if current_len + para_len > chunk_size and current_parts:
            _flush_chunk(
                chunks, current_parts, carry, char_offset, title, filename
            )
            char_offset += sum(len(p) for p in current_parts) + 2 * len(current_parts)
            last_text = "\n\n".join(current_parts)
            carry = last_text[-overlap:] if len(last_text) > overlap else last_text
            current_parts = []
            current_len = 0

        current_parts.append(para)
        current_len += para_len

    # Flush remaining
    if current_parts:
        _flush_chunk(chunks, current_parts, carry, char_offset, title, filename)

    # Re-index sequentially
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    return chunks


def _flush_chunk(
    chunks: list[Chunk],
    parts: list[str],
    carry: str,
    char_offset: int,
    title: str,
    filename: str,
) -> None:
    prefix = carry + "\n\n" if carry else ""
    content = prefix + "\n\n".join(parts)
    chunks.append(
        Chunk(
            content=content,
            chunk_index=len(chunks),
            chunk_metadata={
                "title": title,
                "filename": filename,
                "char_start": max(0, char_offset - len(carry)),
            },
        )
    )
