"""
Evaluator for AnswerRelevanceClassifier.

Usage
-----
from evals.evaluators.answer_relevance import run_eval, compare_signatures, optimize
from evals.datasets import answer_relevance as ds
from app.dspy.answer_relevance_classifier import OpenAIAnswerRelevanceClassifier

devset = ds.load()

# Score the production module
score = run_eval(OpenAIAnswerRelevanceClassifier(), devset)

# Compare all signature field-structure variants
results = compare_signatures(devset)

# Optimise with MIPROv2
compiled = optimize(OpenAIAnswerRelevanceClassifier(), trainset=devset[:15], devset=devset[15:])
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import dspy

from evals.datasets import answer_relevance as _ds
from evals.evaluators._base import (
    compare_signatures as _compare_signatures,
    optimize as _optimize,
    print_comparison_table,
    run_eval as _run_eval,
)
from evals.metrics import answer_relevance_metric
from evals.signatures.answer_relevance import DEFAULT, REGISTRY

METRIC: Callable = answer_relevance_metric


def run_eval(
    module: dspy.Module,
    devset: list[dspy.Example] | None = None,
    *,
    num_threads: int = 4,
) -> float:
    devset = devset if devset is not None else _ds.load()
    return _run_eval(module, devset, METRIC, num_threads=num_threads)


def compare_signatures(
    devset: list[dspy.Example] | None = None,
    *,
    signature_names: list[str] | None = None,
    num_threads: int = 4,
) -> dict[str, float]:
    devset = devset if devset is not None else _ds.load()
    results = _compare_signatures(
        REGISTRY,
        devset,
        METRIC,
        signature_names=signature_names,
        num_threads=num_threads,
    )
    print_comparison_table("answer_relevance", len(devset), results)
    return results


def optimize(
    module: dspy.Module,
    trainset: list[dspy.Example] | None = None,
    devset: list[dspy.Example] | None = None,
    *,
    optimizer: str = "mipro",
    save_path: str | Path | None = None,
    **kwargs: Any,
) -> dspy.Module:
    """
    Compile `module` and optionally save the result.

    If `trainset` / `devset` are not provided the full dataset is loaded
    and split 75/25.
    """
    if trainset is None or devset is None:
        all_examples = _ds.load()
        split = int(len(all_examples) * 0.75)
        trainset = trainset if trainset is not None else all_examples[:split]
        devset = devset if devset is not None else all_examples[split:]
    return _optimize(
        module,
        trainset,
        devset,
        METRIC,
        optimizer=optimizer,
        save_path=save_path,
        **kwargs,
    )


def default_module(signature_name: str = DEFAULT) -> dspy.Module:
    """Return a fresh dspy.Predict for the named (or default) signature variant."""
    return dspy.Predict(REGISTRY[signature_name])
