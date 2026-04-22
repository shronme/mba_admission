"""
Non-functional / process-level tests for `rag-full-document-retrieval`.

Covers TC-049 (no new migrations) and TC-050 (langchain-text-splitters
declared in backend requirements). TC-048 is exercised in
`test_rag_tool_selection.py::TestPreloadFanOut::test_qa_seeds_use_semantic_search_only`.
TC-051 (end-to-end streaming smoke) is intentionally deferred to manual
staging verification per the QA plan's "Hard-to-Test Areas" note.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# TC-049 — no new migration files for this feature
# ===========================================================================
class TestNoNewMigrations:
    """
    The product spec mandates: "no new Alembic migration for this feature".
    We assert that the migration count matches the pre-feature baseline
    recorded by the dev log (16 revisions on main at feature-start). If a
    new migration is ever added legitimately, bump `EXPECTED_MAX_COUNT`
    consciously and update the spec.
    """

    EXPECTED_MAX_COUNT = 16

    def test_migration_count_unchanged(self) -> None:
        versions_dir = BACKEND_ROOT / "alembic" / "versions"
        assert versions_dir.is_dir(), f"missing {versions_dir}"
        files = [
            p
            for p in versions_dir.iterdir()
            if p.is_file()
            and p.suffix == ".py"
            and not p.name.startswith("_")
        ]
        assert len(files) <= self.EXPECTED_MAX_COUNT, (
            "A new Alembic migration was added for "
            "`rag-full-document-retrieval` but the spec forbids schema "
            "changes for this feature. "
            f"Found {len(files)} files, expected at most "
            f"{self.EXPECTED_MAX_COUNT}."
        )


# ===========================================================================
# TC-050 — `langchain-text-splitters` declared for token-aware chunking
# ===========================================================================
class TestDependencyDeclarations:
    def test_langchain_text_splitters_declared(self) -> None:
        req = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert re.search(
            r"(?mi)^\s*langchain-text-splitters\s*==", req
        ), "langchain-text-splitters must be pinned in backend/requirements.txt"

    def test_tiktoken_declared(self) -> None:
        """
        FR-5 token-aware chunking uses a tiktoken-backed splitter. The
        dependency must be pinned to keep tokenization deterministic
        across dev / CI / prod.
        """
        req = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert re.search(
            r"(?mi)^\s*tiktoken\s*==", req
        ), "tiktoken must be pinned in backend/requirements.txt"

    def test_text_splitter_importable(self) -> None:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        assert callable(
            getattr(
                RecursiveCharacterTextSplitter,
                "from_tiktoken_encoder",
                None,
            )
        )
