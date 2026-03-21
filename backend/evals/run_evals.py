"""
CLI entry point for DSPy evaluation and optimisation.

Run from backend/ with the appropriate PYTHONPATH / venv active.

Examples
--------
# Evaluate the default signature for a module
python -m evals.run_evals --module answer_relevance

# Evaluate a specific named signature variant
python -m evals.run_evals --module answer_relevance --signature v2_cot_literal

# Compare all signature variants side-by-side
python -m evals.run_evals --module document_classifier --compare-signatures

# Evaluate all modules with their default signatures
python -m evals.run_evals --module all

# Let MIPROv2 auto-optimise instructions + few-shot
python -m evals.run_evals --module document_classifier --signature v1_baseline \\
    --optimize --optimizer mipro --save-path evals/compiled/doc_v1_mipro.json

# Bootstrap few-shot demos only (cheaper)
python -m evals.run_evals --module answer_relevance \\
    --optimize --optimizer bootstrap --save-path evals/compiled/ar_bootstrap.json

# Override LLM mode
python -m evals.run_evals --module intent_classifier --mode openai
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------

_ALL_MODULES = (
    "answer_relevance",
    "document_classifier",
    "intent_classifier",
    "intake_interviewer",
    "profile_agent",
)


def _get_evaluator(module_name: str):
    """Lazy-import the evaluator for `module_name`."""
    if module_name == "answer_relevance":
        import evals.evaluators.answer_relevance as ev
    elif module_name == "document_classifier":
        import evals.evaluators.document_classifier as ev  # type: ignore[no-redef]
    elif module_name == "intent_classifier":
        import evals.evaluators.intent_classifier as ev  # type: ignore[no-redef]
    elif module_name == "intake_interviewer":
        import evals.evaluators.intake_interviewer as ev  # type: ignore[no-redef]
    elif module_name == "profile_agent":
        import evals.evaluators.profile_agent as ev  # type: ignore[no-redef]
    else:
        raise ValueError(f"Unknown module: {module_name!r}. Choose from: {', '.join(_ALL_MODULES)}")
    return ev


def _get_production_module(module_name: str):
    """Return the production OpenAI-backed module instance for `module_name`."""
    if module_name == "answer_relevance":
        from app.dspy.answer_relevance_classifier import OpenAIAnswerRelevanceClassifier
        return OpenAIAnswerRelevanceClassifier()
    elif module_name == "document_classifier":
        from app.dspy.document_classifier import OpenAIDocumentClassifier
        return OpenAIDocumentClassifier()
    elif module_name == "intent_classifier":
        from app.dspy.openai_intent_classifier import OpenAIIntentClassifier
        return OpenAIIntentClassifier()
    elif module_name == "intake_interviewer":
        from app.dspy.intake_interviewer import OpenAIIntakeInterviewer
        return OpenAIIntakeInterviewer()
    elif module_name == "profile_agent":
        from app.dspy.profile_agent import OpenAIProfileAgent
        return OpenAIProfileAgent()
    raise ValueError(module_name)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m evals.run_evals",
        description="Evaluate and optimise DSPy modules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--module",
        required=True,
        choices=[*_ALL_MODULES, "all"],
        help="Module to evaluate, or 'all' to run every module.",
    )
    p.add_argument(
        "--signature",
        default=None,
        help=(
            "Named signature variant to use (e.g. v2_cot_literal). "
            "Defaults to each module's DEFAULT if not specified. "
            "Ignored when --compare-signatures is set."
        ),
    )
    p.add_argument(
        "--compare-signatures",
        action="store_true",
        help="Evaluate all signature variants for the module and print a ranked table.",
    )
    p.add_argument(
        "--optimize",
        action="store_true",
        help="Run an optimizer after evaluation and save the compiled program.",
    )
    p.add_argument(
        "--optimizer",
        default="mipro",
        choices=["labeled_few_shot", "bootstrap", "bootstrap_random_search", "mipro"],
        help=(
            "Optimizer to use when --optimize is set. Default: mipro. "
            "mipro: auto-proposes instructions + few-shot demos via Bayesian search. "
            "bootstrap_random_search: demos only, best cost/quality tradeoff. "
            "bootstrap: demos only, cheaper. "
            "labeled_few_shot: hard-codes trainset examples, zero LM calls."
        ),
    )
    p.add_argument(
        "--save-path",
        default=None,
        metavar="PATH",
        help=(
            "Where to save the compiled program JSON. "
            "Defaults to evals/compiled/<module>_<signature>_<optimizer>.json."
        ),
    )
    p.add_argument(
        "--mode",
        choices=["mock", "openai"],
        default=None,
        help="Override DSPY_MODE env var (mock = no LLM calls, openai = real calls).",
    )
    p.add_argument(
        "--num-threads",
        type=int,
        default=4,
        metavar="N",
        help="Parallel threads for dspy.Evaluate. Default: 4.",
    )
    p.add_argument(
        "--loaded-program",
        default=None,
        metavar="PATH",
        help="Path to a previously compiled JSON to load before evaluation.",
    )
    return p


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def _run_single(
    module_name: str,
    args: argparse.Namespace,
) -> None:
    ev = _get_evaluator(module_name)

    # --compare-signatures: evaluate all field-structure variants
    if args.compare_signatures:
        logger.info("[%s] comparing signature variants …", module_name)
        ev.compare_signatures(num_threads=args.num_threads)
        return

    # Determine which module to use
    if args.signature:
        # Verify the signature name exists in this module's registry
        from evals import signatures as _sigs
        sig_module_name = module_name.replace("_classifier", "").replace("_interviewer", "_interviewer")
        # Map module_name → signatures sub-module
        _sig_module_map = {
            "answer_relevance": "evals.signatures.answer_relevance",
            "document_classifier": "evals.signatures.document_classifier",
            "intent_classifier": "evals.signatures.intent_classifier",
            "intake_interviewer": "evals.signatures.intake_interviewer",
            "profile_agent": "evals.signatures.profile_agent",
        }
        import importlib
        sig_mod = importlib.import_module(_sig_module_map[module_name])
        if args.signature not in sig_mod.REGISTRY:
            print(
                f"Error: signature {args.signature!r} not found in {module_name} registry. "
                f"Available: {', '.join(sig_mod.REGISTRY)}"
            )
            sys.exit(1)
        module = dspy.Predict(sig_mod.REGISTRY[args.signature])
    else:
        module = _get_production_module(module_name)

    # Optionally load a previously compiled program
    if args.loaded_program:
        path = Path(args.loaded_program)
        if not path.exists():
            print(f"Error: --loaded-program path does not exist: {path}")
            sys.exit(1)
        module.load(str(path))
        logger.info("Loaded compiled program from %s", path)

    # Always evaluate first
    logger.info("[%s] running evaluation …", module_name)
    score = ev.run_eval(module, num_threads=args.num_threads)
    sig_label = args.signature or "production"
    print(f"\n[{module_name}] {sig_label} score: {score:.2f}\n")

    # Optimise if requested
    if args.optimize:
        save_path = args.save_path
        if save_path is None:
            sig_label_safe = (args.signature or "default").replace("/", "_")
            save_path = f"evals/compiled/{module_name}_{sig_label_safe}_{args.optimizer}.json"

        logger.info(
            "[%s] optimising with %s → %s …",
            module_name,
            args.optimizer,
            save_path,
        )
        compiled = ev.optimize(
            module,
            optimizer=args.optimizer,
            save_path=save_path,
        )

        logger.info("[%s] evaluating compiled program …", module_name)
        compiled_score = ev.run_eval(compiled, num_threads=args.num_threads)
        print(f"[{module_name}] compiled ({args.optimizer}) score: {compiled_score:.2f}")
        print(f"[{module_name}] compiled program saved to: {save_path}\n")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Apply mode override before any DSPy imports touch the env
    if args.mode:
        os.environ["DSPY_MODE"] = args.mode
        logger.info("DSPY_MODE overridden to: %s", args.mode)

    # Configure DSPy
    from app.core.dspy_runtime import configure_dspy_from_env
    configure_dspy_from_env()

    # Import dspy after env is set
    global dspy
    import dspy as _dspy
    dspy = _dspy

    modules_to_run = _ALL_MODULES if args.module == "all" else (args.module,)

    for module_name in modules_to_run:
        try:
            _run_single(module_name, args)
        except Exception:
            logger.exception("[%s] evaluation failed", module_name)
            if args.module != "all":
                sys.exit(1)


if __name__ == "__main__":
    main()
