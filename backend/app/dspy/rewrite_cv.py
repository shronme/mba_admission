"""
DSPy module for rewriting a candidate CV (FR-3).

Inputs: the candidate's full CV text (required, non-empty), plus optional
life-story text, candidate profile JSON, target-school dossier text, target
school name, and emphasis hint. Output: the rewritten CV body string
(markdown-ish, ready to hand back to the advisor chat / `save_artifact`).

The tool wrapper in `agent_tools.py::rewrite_cv` is responsible for loading
inputs, invoking this module, and persisting the artifact — this module has
**no** side effects.

In `DSPY_MODE=mock`, `MockRewriteCVModule` returns deterministic text that
preserves the source CV verbatim, which is what the offline coverage eval
(T-14) relies on for the ≥95% field-coverage gate.
"""

from __future__ import annotations

import dspy


class RewriteCVSignature(dspy.Signature):
    """
    You are rewriting an MBA candidate's CV.

    Content rules (STRICT):
    - Preserve every role, company, date range, education entry, award, and
      metric that appears in the source CV. Do not invent or speculate.
    - If a field (e.g. GPA, location, dates, interests) is NOT in the source,
      OMIT it entirely. Never output placeholder tokens such as `???`,
      `??????`, `TBD`, `N/A`, `[placeholder]`, `—`, or blanks to signal
      missing data.
    - If an entire section (e.g. "Voluntary Work", "Additional Information")
      has no substantive content in the source, omit that section heading
      entirely — do not emit an empty section.
    - You may reorder or regroup bullets for clarity, tighten phrasing,
      strengthen action verbs, and quantify only where the source already
      contains the number.
    - Use `life_story` for tone only — do NOT merge narrative content from
      the life story into the CV body.
    - Use `emphasis` and `school_dossier` to prioritize which source bullets
      to foreground. Never add new bullets that aren't grounded in the source.

    Output format (STRICT Markdown, used by the PDF/DOCX renderer):
    - Start with a single H1 line containing ONLY the candidate's full name
      (e.g. `# Asaf Hadar`). No tagline, no "Polished MBA CV", no
      "Harvard-ready" suffix.
    - The next line is plain-text contact info (address / phone / email,
      separated by ` | `). No Markdown syntax on this line.
    - Section headings use `## ` (H2). Canonical order when present:
      Education, Professional Experience, Military Service, Voluntary Work,
      Additional Information. Omit any section with no source content.
    - Inside each section, each role/entry is a bold line:
      `**Company/School** — Location (Start–End)` followed by a bold title
      line: `**Title**`.
    - Achievements are bullet lines starting with `- `. Use bold sparingly
      inside bullets for a handful of key nouns (company names, awards,
      metrics). Do NOT bold full bullets or entire paragraphs.
    - No H3 or deeper headings. No tables. No horizontal rules. No code
      fences. No HTML tags. No emojis.

    Return the rewritten CV only — no preamble, commentary, or trailing
    notes.
    """

    cv_text: str = dspy.InputField(
        desc="The candidate's full CV extracted text (required, non-empty)."
    )
    life_story: str = dspy.InputField(
        desc="Optional candidate life-story / personal narrative text. Empty string if not available."
    )
    profile_json: str = dspy.InputField(
        desc="Candidate profile attributes as JSON. Empty string or '{}' if not available."
    )
    school_dossier: str = dspy.InputField(
        desc="Optional target school dossier text. Empty string if no target school or no dossier match."
    )
    target_school: str = dspy.InputField(
        desc="Target school name (empty string for a school-agnostic rewrite)."
    )
    emphasis: str = dspy.InputField(
        desc="Optional hint about what to emphasize (empty string if none)."
    )

    rewritten_cv: str = dspy.OutputField(
        desc="The full rewritten CV body, ready to save as a draft."
    )


class OpenAIRewriteCVModule(dspy.Module):
    """Production rewriter backed by the configured DSPy LM."""

    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(RewriteCVSignature)

    def forward(  # type: ignore[override]
        self,
        cv_text: str,
        life_story: str = "",
        profile_json: str = "",
        school_dossier: str = "",
        target_school: str = "",
        emphasis: str = "",
    ) -> dspy.Prediction:
        if not isinstance(cv_text, str) or not cv_text.strip():
            raise ValueError("cv_text is required and must be non-empty")
        return self._predict(
            cv_text=cv_text,
            life_story=life_story or "",
            profile_json=profile_json or "",
            school_dossier=school_dossier or "",
            target_school=target_school or "",
            emphasis=emphasis or "",
        )

    async def aforward(  # type: ignore[override]
        self,
        cv_text: str,
        life_story: str = "",
        profile_json: str = "",
        school_dossier: str = "",
        target_school: str = "",
        emphasis: str = "",
    ) -> dspy.Prediction:
        if not isinstance(cv_text, str) or not cv_text.strip():
            raise ValueError("cv_text is required and must be non-empty")
        return await self._predict.aforward(
            cv_text=cv_text,
            life_story=life_story or "",
            profile_json=profile_json or "",
            school_dossier=school_dossier or "",
            target_school=target_school or "",
            emphasis=emphasis or "",
        )


class MockRewriteCVModule(dspy.Module):
    """
    Deterministic stand-in for the rewriter used under `DSPY_MODE=mock`.

    Strategy: keep the entire source CV body verbatim (so coverage evals can
    match every role, company, date, and education entry), wrap it in a
    short header that mentions the target school / emphasis when present.
    This preserves the offline coverage contract (T-14, ≥95% field match)
    without making any LLM calls.
    """

    def forward(  # type: ignore[override]
        self,
        cv_text: str,
        life_story: str = "",
        profile_json: str = "",
        school_dossier: str = "",
        target_school: str = "",
        emphasis: str = "",
    ) -> dspy.Prediction:
        if not isinstance(cv_text, str) or not cv_text.strip():
            raise ValueError("cv_text is required and must be non-empty")

        header_parts = ["# Rewritten CV (mock)"]
        if target_school:
            header_parts.append(f"Target school: {target_school}")
        if emphasis:
            header_parts.append(f"Emphasis: {emphasis}")
        header = "\n".join(header_parts)

        body = cv_text.strip()
        rewritten = f"{header}\n\n{body}"
        return dspy.Prediction(rewritten_cv=rewritten)

    async def aforward(  # type: ignore[override]
        self,
        cv_text: str,
        life_story: str = "",
        profile_json: str = "",
        school_dossier: str = "",
        target_school: str = "",
        emphasis: str = "",
    ) -> dspy.Prediction:
        return self.forward(
            cv_text=cv_text,
            life_story=life_story,
            profile_json=profile_json,
            school_dossier=school_dossier,
            target_school=target_school,
            emphasis=emphasis,
        )
