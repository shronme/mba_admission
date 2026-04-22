"""
Tests for FR-5 ingestion changes in
`backend/app/workers/tasks/document_processing.py`.

Covers TC-031..TC-037 from the `rag-full-document-retrieval` QA plan:
  - TC-031: stored `extracted_text` capped at 200_000 chars
  - TC-032: ≤200 chunks per file
  - TC-033: very short document → single chunk, no error
  - TC-034: document shorter than overlap → no infinite loop, sensible list
  - TC-035: ≤600 tokens per chunk (tiktoken-based splitter)
  - TC-036: `_CLASSIFY_MAX_CHARS == 4000` unchanged
  - TC-037: forward-only — already-processed files are not re-chunked unless
    re-run (proxy: asserting that the in-process `_extract_text` is idempotent
    for new inputs; DB-level behavior covered by the existing job contract).

All tests bypass OpenAI by not setting `OPENAI_API_KEY` and supplying
plain-text bytes, which triggers the `_code_extract` path.
"""

from __future__ import annotations

import os

import pytest

# Extraction helpers exercised here do not require DSPY_MODE but we keep the
# env toggle consistent with the rest of the RAG test suite.
os.environ.setdefault("DSPY_MODE", "mock")

from app.workers.tasks.document_processing import (  # noqa: E402
    _CLASSIFY_MAX_CHARS,
    _extract_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(text: str) -> tuple[str | None, list[str] | None]:
    """
    Run `_extract_text` against raw text bytes without LLM. We unset
    `OPENAI_API_KEY` inside the test via monkeypatch so the code-only path
    is used deterministically.
    """
    return _extract_text(
        data=text.encode("utf-8"),
        filename="sample.txt",
        content_type="text/plain",
    )


@pytest.fixture(autouse=True)
def _ensure_no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the code-only extraction path."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ===========================================================================
# TC-031 — stored extracted_text cap at 200_000
# ===========================================================================
class TestExtractedTextCap:
    def test_text_longer_than_cap_is_truncated_at_200k(self) -> None:
        input_text = "A" * 250_000
        extracted, chunks = _extract(input_text)
        assert extracted is not None
        assert len(extracted) == 200_000, (
            f"Expected cap 200_000, got {len(extracted)}"
        )
        assert chunks is not None and len(chunks) > 0

    def test_text_below_cap_kept_as_is(self) -> None:
        input_text = "hello " * 100  # ~600 chars
        extracted, _ = _extract(input_text)
        assert extracted is not None
        assert extracted == input_text.strip()


# ===========================================================================
# TC-032 / TC-035 — chunk count & per-chunk token size bounds
# ===========================================================================
class TestChunkBounds:
    def test_chunk_count_respects_200_cap(self) -> None:
        # 200k chars of alternating ASCII text → tiktoken will split into
        # many 600-token chunks. With overlap=50 and chunk_size=600 and
        # character density ≈3.5 chars/token (cl100k_base for English
        # prose), 200k chars ≈ ~57k tokens → ~96 chunks nominally. We
        # conservatively assert the hard 200 cap.
        input_text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                      "Sed do eiusmod tempor incididunt ut labore. ") * 4000
        _, chunks = _extract(input_text)
        assert chunks is not None
        assert len(chunks) <= 200, f"chunk count {len(chunks)} exceeds 200 cap"

    def test_each_chunk_is_at_most_600_tokens(self) -> None:
        try:
            import tiktoken
        except ModuleNotFoundError:  # pragma: no cover — tiktoken is a hard dep
            pytest.skip("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")

        input_text = "word " * 10_000
        _, chunks = _extract(input_text)
        assert chunks is not None
        assert len(chunks) > 1, "expected more than one chunk"
        for i, chunk in enumerate(chunks):
            n_tokens = len(enc.encode(chunk))
            # Splitter uses `from_tiktoken_encoder(chunk_size=600)` which
            # limits token count per chunk. Last chunk may be shorter.
            assert n_tokens <= 600, (
                f"chunk {i} has {n_tokens} tokens, exceeds 600"
            )


# ===========================================================================
# TC-033 — very short document → single chunk
# ===========================================================================
class TestShortDocument:
    def test_minimal_text_produces_single_chunk(self) -> None:
        extracted, chunks = _extract("Hello world.")
        assert extracted == "Hello world."
        assert chunks == ["Hello world."]


# ===========================================================================
# TC-034 — document shorter than overlap size
# ===========================================================================
class TestShortDocumentOverlapEdge:
    def test_document_below_overlap_window_completes_cleanly(self) -> None:
        # 50-token overlap with cl100k_base ≈ 40-50 English words. A 5-word
        # doc is well below that window.
        extracted, chunks = _extract("one two three four five")
        assert extracted == "one two three four five"
        assert chunks is not None
        assert len(chunks) >= 1
        # Defensive: no infinite-loop / duplicate explosion.
        assert len(chunks) <= 5


# ===========================================================================
# TC-036 — _CLASSIFY_MAX_CHARS unchanged
# ===========================================================================
class TestClassifyMaxCharsConstant:
    def test_constant_is_4000(self) -> None:
        assert _CLASSIFY_MAX_CHARS == 4_000


# ===========================================================================
# TC-037 — forward-only idempotency proxy
# ===========================================================================
class TestForwardOnlyExtractIdempotence:
    """
    Repeated calls to `_extract_text` with the same input produce identical
    output. This is the code-side proxy for the FR-5 "forward-only" property
    (existing uploads are not touched until reprocess) — the extraction step
    itself is pure / deterministic given input bytes.
    """

    def test_same_input_produces_same_output(self) -> None:
        input_text = "Stable content. " * 100
        t1, c1 = _extract(input_text)
        t2, c2 = _extract(input_text)
        assert t1 == t2
        assert c1 == c2


# ===========================================================================
# TC-050 — `langchain-text-splitters` dependency is declared
# ===========================================================================
class TestDependencyDeclared:
    """TC-050: `langchain-text-splitters` must be pinned in requirements."""

    def test_requirements_pins_langchain_text_splitters(self) -> None:
        req_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "requirements.txt",
        )
        with open(req_path, encoding="utf-8") as f:
            content = f.read()
        assert "langchain-text-splitters" in content, (
            f"langchain-text-splitters must be declared in {req_path}"
        )
