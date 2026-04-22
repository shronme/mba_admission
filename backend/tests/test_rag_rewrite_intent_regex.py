"""
Unit tests for FR-1 rewrite-intent classifier (`classify_rewrite_intent` /
`_REWRITE_INTENT_RE`).

Covers TC-001..TC-010 from the `rag-full-document-retrieval` QA plan:
verb-first / doc-first matches, Q&A and near-miss negatives, 6-token window
boundary, Unicode (`résumé`), `SOP` whole-word behavior, and whitespace
variants for `life story`.

These tests exercise only the authoritative regex (no DB, no DSPy). The
semantics asserted here are the ones pinned in `02-product-spec.md` FR-1.
"""

from __future__ import annotations

import pytest

from app.dspy.intent import _REWRITE_INTENT_RE, classify_rewrite_intent


# ---------------------------------------------------------------------------
# TC-001 — clear match, verb before document noun
# ---------------------------------------------------------------------------
class TestClearMatchVerbFirst:
    @pytest.mark.parametrize(
        "message",
        [
            "please rewrite my CV",
            "rewrite my cv",
            "Revise my resume ASAP",
            "Can you polish my essay for me?",
            "Improve my life story",
            "Please redraft my statement of purpose",
            "Edit my SOP before Friday",
            "rework my CV tonight",
        ],
    )
    def test_verb_first_matches(self, message: str) -> None:
        assert classify_rewrite_intent(message) is True
        assert _REWRITE_INTENT_RE.search(message) is not None


# ---------------------------------------------------------------------------
# TC-002 — clear match, document noun before verb (within 6-token window)
# ---------------------------------------------------------------------------
class TestClearMatchDocFirst:
    @pytest.mark.parametrize(
        "message",
        [
            "CV please polish",
            "My essay I want to rewrite tonight",
            "Resume could you polish?",
            "Life story please revise",
            "SOP quick polish tonight please",
        ],
    )
    def test_doc_first_matches(self, message: str) -> None:
        assert classify_rewrite_intent(message) is True


# ---------------------------------------------------------------------------
# TC-003 — Q&A / semantic prompts must NOT match (NFR regression guard)
# ---------------------------------------------------------------------------
class TestQAPromptsNoMatch:
    @pytest.mark.parametrize(
        "message",
        [
            "Summarize my leadership",
            "What's my GMAT?",
            "Tell me about my undergrad GPA",
            "What did I say about impact?",
            "How do I describe my experience?",
            "What should I emphasize for Wharton?",
            "",
        ],
    )
    def test_semantic_qa_does_not_match(self, message: str) -> None:
        assert classify_rewrite_intent(message) is False


# ---------------------------------------------------------------------------
# TC-004..TC-007 — near-miss negatives
# ---------------------------------------------------------------------------
class TestNearMissNegatives:
    # TC-004: rewrite verb without any document noun.
    @pytest.mark.parametrize(
        "message",
        [
            "rewrite that section",
            "please polish this paragraph for me",
            "revise the draft I sent earlier",
            "improve the bullet point",
        ],
    )
    def test_verb_without_doc_noun_no_match(self, message: str) -> None:
        assert classify_rewrite_intent(message) is False

    # TC-005: document noun with no verb nearby.
    @pytest.mark.parametrize(
        "message",
        [
            "here is my CV",
            "Attached is my resume",
            "this is my life story",
            "My statement of purpose is short",
            "SOP is attached",
        ],
    )
    def test_doc_without_verb_no_match(self, message: str) -> None:
        assert classify_rewrite_intent(message) is False

    # TC-006: verb + doc noun > 6 tokens apart — outside window.
    @pytest.mark.parametrize(
        "message",
        [
            # 7 filler tokens between verb and doc noun
            "please rewrite the one thing I wanted for tomorrow is my CV",
            # Doc noun first, but 10 filler tokens before verb
            "My CV which I worked on for many many weekends I want to polish",
        ],
    )
    def test_outside_6_token_window_no_match(self, message: str) -> None:
        assert classify_rewrite_intent(message) is False

    # TC-007: rewrite-like phrase embedded in unrelated context.
    @pytest.mark.parametrize(
        "message",
        [
            # `rewrite` to `essays` spans > 6 tokens
            "I plan to rewrite history one of these future weekends when my essays are finalized",
            # `Improve` and `resume` far apart (10+ tokens), doc noun never meets verb
            "Improve was the operating slogan for my whole team over many many many years that my resume barely mentions",
        ],
    )
    def test_unrelated_context_no_match(self, message: str) -> None:
        assert classify_rewrite_intent(message) is False


# ---------------------------------------------------------------------------
# TC-008 — Unicode `résumé` with verb within window
# ---------------------------------------------------------------------------
class TestUnicodeResume:
    @pytest.mark.parametrize(
        "message",
        [
            "please rewrite my résumé",
            "polish my résumé tonight",
            "résumé quick polish please",
        ],
    )
    def test_resume_unicode_matches(self, message: str) -> None:
        assert classify_rewrite_intent(message) is True


# ---------------------------------------------------------------------------
# TC-009 — `SOP` vs `sop` whole-word semantics
# ---------------------------------------------------------------------------
class TestSopCaseBehavior:
    def test_uppercase_sop_matches(self) -> None:
        # `\bSOP\b` under (?i) matches case-insensitively; both should match.
        assert classify_rewrite_intent("Please polish my SOP") is True

    def test_lowercase_sop_matches_due_to_case_insensitive_flag(self) -> None:
        # Regex uses (?i) so whole-word `sop` also matches. Pin this behavior
        # so any future change to the regex is intentional.
        assert classify_rewrite_intent("please polish my sop") is True

    def test_sop_inside_larger_word_no_match(self) -> None:
        # `\bSOP\b` guards against matching inside "soap" / "soppy" etc.
        # No document-noun match here, so classifier should be False.
        assert classify_rewrite_intent("please polish my soapy sopping draft") is False


# ---------------------------------------------------------------------------
# TC-010 — `life story` whitespace variants
# ---------------------------------------------------------------------------
class TestLifeStoryWhitespace:
    def test_single_space_life_story_matches(self) -> None:
        assert classify_rewrite_intent("rewrite my life story") is True

    def test_extra_space_life_story_matches(self) -> None:
        # `life\s+story` allows 1+ whitespace — two spaces should still match.
        assert classify_rewrite_intent("rewrite my life  story") is True

    def test_newline_between_life_and_story_matches(self) -> None:
        # `\s+` matches any whitespace including newlines.
        assert classify_rewrite_intent("rewrite my life\nstory") is True


# ---------------------------------------------------------------------------
# Guard: None / non-string inputs
# ---------------------------------------------------------------------------
class TestNonStringInputs:
    def test_none_returns_false(self) -> None:
        assert classify_rewrite_intent(None) is False  # type: ignore[arg-type]

    def test_empty_string_returns_false(self) -> None:
        assert classify_rewrite_intent("") is False

    def test_non_string_returns_false(self) -> None:
        assert classify_rewrite_intent(12345) is False  # type: ignore[arg-type]
