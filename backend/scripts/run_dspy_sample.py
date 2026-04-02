#!/usr/bin/env python3
from __future__ import annotations

import logging

from app.core.dspy_runtime import run_dspy_module
from app.dspy.static_intent_classifier import StaticIntentClassifier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_dspy_sample")


def main() -> None:
    logger.info("Running StaticIntentClassifier sample…")
    module = StaticIntentClassifier()
    out = run_dspy_module(module, message="I uploaded my grades. What are my goals for the MBA?")
    # DSPy Prediction is printable.
    logger.info("DSPy output: %s", out)


if __name__ == "__main__":
    main()

