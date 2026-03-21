"""
Shared helpers used by all module evaluators.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

import dspy

logger = logging.getLogger(__name__)

_OPTIMIZERS = ("labeled_few_shot", "bootstrap", "bootstrap_random_search", "mipro")


def run_eval(
    module: dspy.Module,
    devset: list[dspy.Example],
    metric: Callable,
    *,
    num_threads: int = 4,
) -> float:
    """
    Score `module` against `devset` using `metric`.

    Returns the aggregated score (float in [0, 100] as reported by dspy.Evaluate).
    """
    evaluate = dspy.Evaluate(
        devset=devset,
        metric=metric,
        num_threads=num_threads,
        display_progress=True,
        display_table=5,
    )
    return evaluate(module)


def compare_signatures(
    registry: dict[str, type[dspy.Signature]],
    devset: list[dspy.Example],
    metric: Callable,
    *,
    signature_names: list[str] | None = None,
    num_threads: int = 4,
) -> dict[str, float]:
    """
    Instantiate ``dspy.Predict(sig_cls)`` for each named signature, evaluate
    against `devset`, and return ``{name: score}``.

    If `signature_names` is None all entries in `registry` are evaluated.
    """
    results: dict[str, float] = {}
    for name, sig_cls in registry.items():
        if signature_names and name not in signature_names:
            continue
        logger.info("Evaluating signature variant: %s", name)
        module = dspy.Predict(sig_cls)
        results[name] = run_eval(module, devset, metric, num_threads=num_threads)
    return results


def optimize(
    module: dspy.Module,
    trainset: list[dspy.Example],
    devset: list[dspy.Example],
    metric: Callable,
    *,
    optimizer: str = "mipro",
    save_path: str | Path | None = None,
    **kwargs: Any,
) -> dspy.Module:
    """
    Compile `module` using the named optimizer and optionally save the result.

    Parameters
    ----------
    module:
        An uncompiled DSPy module instance.
    trainset:
        Examples used during compilation (bootstrapping / instruction search).
    devset:
        Examples used to evaluate candidate programs during compilation.
    metric:
        The metric function passed to the optimizer.
    optimizer:
        One of: ``labeled_few_shot``, ``bootstrap``,
        ``bootstrap_random_search``, ``mipro``.
    save_path:
        If provided, the compiled module is saved as JSON at this path.
    **kwargs:
        Extra keyword arguments forwarded to the optimizer constructor.

    Returns
    -------
    dspy.Module
        The compiled (optimised) module.
    """
    if optimizer not in _OPTIMIZERS:
        raise ValueError(
            f"Unknown optimizer {optimizer!r}. Choose from: {', '.join(_OPTIMIZERS)}"
        )

    compiled: dspy.Module

    if optimizer == "labeled_few_shot":
        from dspy.teleprompt import LabeledFewShot  # type: ignore[import-not-found]

        k = kwargs.pop("k", 4)
        teleprompter = LabeledFewShot(k=k, **kwargs)
        compiled = teleprompter.compile(module, trainset=trainset)

    elif optimizer == "bootstrap":
        from dspy.teleprompt import BootstrapFewShot  # type: ignore[import-not-found]

        max_bootstrapped = kwargs.pop("max_bootstrapped_demos", 4)
        max_labeled = kwargs.pop("max_labeled_demos", 4)
        teleprompter = BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=max_bootstrapped,
            max_labeled_demos=max_labeled,
            **kwargs,
        )
        compiled = teleprompter.compile(module, trainset=trainset)

    elif optimizer == "bootstrap_random_search":
        from dspy.teleprompt import BootstrapFewShotWithRandomSearch  # type: ignore[import-not-found]

        max_bootstrapped = kwargs.pop("max_bootstrapped_demos", 4)
        max_labeled = kwargs.pop("max_labeled_demos", 4)
        num_candidate_programs = kwargs.pop("num_candidate_programs", 8)
        teleprompter = BootstrapFewShotWithRandomSearch(
            metric=metric,
            max_bootstrapped_demos=max_bootstrapped,
            max_labeled_demos=max_labeled,
            num_candidate_programs=num_candidate_programs,
            **kwargs,
        )
        compiled = teleprompter.compile(module, trainset=trainset, valset=devset)

    elif optimizer == "mipro":
        from dspy.teleprompt import MIPROv2  # type: ignore[import-not-found]

        auto = kwargs.pop("auto", "medium")
        num_candidates = kwargs.pop("num_candidates", 10)
        teleprompter = MIPROv2(
            metric=metric,
            auto=auto,
            num_candidates=num_candidates,
            **kwargs,
        )
        compiled = teleprompter.compile(
            module,
            trainset=trainset,
            valset=devset,
            requires_permission_to_run=False,
        )

    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        compiled.save(str(path))
        logger.info("Compiled module saved to %s", path)

    return compiled


def print_comparison_table(
    module_name: str,
    devset_n: int,
    results: dict[str, float],
) -> None:
    """Pretty-print a ranked comparison table to stdout."""
    if not results:
        print("No results to display.")
        return

    best = max(results, key=lambda k: results[k])
    col_width = max(len(name) for name in results) + 2
    header = f"\n{module_name} signature comparison (devset n={devset_n})"
    print(header)
    print("-" * len(header.strip()))
    for name, score in sorted(results.items(), key=lambda kv: kv[1], reverse=True):
        marker = "  <- best" if name == best else ""
        print(f"{name:<{col_width}} {score:.2f}{marker}")
    print()
