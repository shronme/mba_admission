"""
Offline evaluation harness for the `rewrite_cv` DSPy module (FR-7).

Default run (DSPY_MODE=mock):

    cd backend && DSPY_MODE=mock python -m evals.rewrite_cv

The coverage pass asserts that at least 95% of the structured fields from
each CV fixture (roles, companies, date ranges, education) appear in the
rewritten output. An optional LLM-judge hallucination pass is gated on
`DSPY_MODE=openai` (see `evals.rewrite_cv.judge`).
"""

__all__: list[str] = []
