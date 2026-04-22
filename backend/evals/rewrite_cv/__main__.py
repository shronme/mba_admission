"""
CLI entry point for the offline `rewrite_cv` coverage eval.

Usage (from `backend/`):

    PYTHONPATH=. DSPY_MODE=mock python -m evals.rewrite_cv

Exits with non-zero status when any fixture falls below the coverage
threshold defined in `runner.COVERAGE_THRESHOLD`.
"""

from __future__ import annotations

import logging
import sys

from evals.rewrite_cv.runner import print_report, run


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    result = run()
    print_report(result)

    # Optional LLM judge — skipped unless DSPY_MODE=openai.
    try:
        from evals.rewrite_cv.judge import run_judge
    except Exception:  # pragma: no cover — judge module not critical for default gate
        logging.getLogger(__name__).exception("judge import failed")
    else:
        run_judge(result)

    return 0 if result.all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
