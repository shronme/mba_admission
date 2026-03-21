"""
Evaluator for ProfileAgent (ProfileCompletenessSignature).

Usage
-----
from evals.evaluators.profile_agent import run_eval, compare_signatures, optimize
from evals.datasets import profile_agent as ds
from app.dspy.profile_agent import OpenAIProfileAgent

devset = ds.load()
score = run_eval(OpenAIProfileAgent(), devset)
results = compare_signatures(devset)
compiled = optimize(OpenAIProfileAgent(), trainset=devset[:6], devset=devset[6:])
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import dspy

from evals.datasets import profile_agent as _ds
from evals.evaluators._base import (
    compare_signatures as _compare_signatures,
    optimize as _optimize,
    print_comparison_table,
    run_eval as _run_eval,
)
from evals.metrics import profile_composite_metric
from evals.signatures.profile_agent import DEFAULT, REGISTRY

METRIC: Callable = profile_composite_metric


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
    print_comparison_table("profile_agent", len(devset), results)
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
