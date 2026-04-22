"""
Rewrite / redraft intent classification for the advisor chat pipeline.

v1 is a **two-way** classifier only: a message is either a clear rewrite/redraft
match (regex below) or not. There is no "borderline" / "augment" mode — on
match, the chat preload replaces semantic search with full-document blocks
(see FR-4); on non-match, the existing semantic preload path is used unchanged.

The regex is pinned by FR-1 of the product spec (verb and document phrase
within at most six whitespace-separated tokens, in either order, case-
insensitive). It is semantically aligned with the spec but NOT byte-for-byte
identical: the spec's transcribed pattern has one unmatched trailing `)`
(10 close / 9 open) that would not compile; this implementation drops that
single stray paren and preserves every alternative and capture group. See
`.claude/features/rag-full-document-retrieval/05-dev-log.md` T-03 for the
documented deviation.
"""

from __future__ import annotations

import re

# NOTE: this pattern is the authoritative FR-1 regex. Do not simplify or
# "normalize" it without updating the spec — it is duplicated here (single
# source of truth) so that `chat.py`, unit tests, and any other callers share
# one compiled object. See the module docstring above for the one-paren
# correction vs the spec's pasted regex.
_REWRITE_INTENT_RE = re.compile(
    r"(?i)(?:(?:\b(?:rewrite|revise|redo|polish|improve|edit|redraft|rework)\b"
    r"(?:\s+\S+){0,6}\s+"
    r"(?:cv|resume|résumé|essay|life\s+story|statement\s+of\s+purpose|\bSOP\b))"
    r"|(?:cv|resume|résumé|essay|life\s+story|statement\s+of\s+purpose|\bSOP\b)"
    r"(?:\s+\S+){0,6}\s+"
    r"\b(?:rewrite|revise|redo|polish|improve|edit|redraft|rework)\b)"
)


def classify_rewrite_intent(message: str) -> bool:
    """
    Return True when `message` matches the FR-1 rewrite/redraft pattern.

    The caller is responsible for passing the raw user message (no lower-
    casing or normalization); the regex is case-insensitive and expects the
    original whitespace structure to count tokens within the 6-word window.
    """
    if not isinstance(message, str) or not message:
        return False
    return bool(_REWRITE_INTENT_RE.search(message))
