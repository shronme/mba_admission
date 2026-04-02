from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import dspy

_STATE_DIR = Path("backend/data/program_dossiers")
_LAST_RUN_PATH = _STATE_DIR / "last_run.json"


def _ensure_backend_on_path() -> None:
    """
    Allow running this file directly via `python backend/scripts/...py` by
    ensuring `backend/` is on sys.path for `import app.*`.
    """
    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _slug_to_label(slug: str) -> str:
    s = (slug or "").strip().replace("_", " ")
    if not s:
        return slug
    tokens = {
        "mba": "MBA",
        "ms": "MS",
        "phd": "PhD",
        "jd": "JD",
        "md": "MD",
        "llm": "LLM",
        "mpp": "MPP",
        "mpa": "MPA",
        "mph": "MPH",
        "msw": "MSW",
        "mfa": "MFA",
        "meng": "MEng",
        "dnp": "DNP",
        "med": "MEd",
        "ai": "AI",
        "ml": "ML",
        "stem": "STEM",
        "i20": "I-20",
    }
    out: list[str] = []
    for part in s.split():
        low = part.lower()
        out.append(tokens.get(low, part.capitalize() if low.isalpha() else part))
    return " ".join(out)


def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = "".join(ch if ch.isalnum() or ch in ("-", "_", " ", ".") else " " for ch in s)
    s = " ".join(s.split())
    return s.replace(" ", "_")[:160] or "item"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _configure_perplexity_dspy(*, model: str, api_key: str, base_url: str) -> None:
    """
    Configure DSPy/LiteLLM to use Perplexity's OpenAI-compatible API.
    """
    os.environ.setdefault("DSPY_MODE", "mock")
    os.environ["DSPY_MODEL"] = model
    # DSPy forwards kwargs to LiteLLM; depending on versions, the parameter name
    # for the OpenAI-compatible base URL may differ.
    try:
        lm = dspy.LM(model, api_key=api_key, api_base=base_url)
    except TypeError:
        lm = dspy.LM(model, api_key=api_key, base_url=base_url)
    dspy.configure(lm=lm)


def _iter_targets(
    *,
    schools: Iterable[str],
    program_slugs: Iterable[str],
) -> Iterable[tuple[str, str, str]]:
    for school in schools:
        for slug in program_slugs:
            yield school, slug, _slug_to_label(slug)


def main() -> int:
    _ensure_backend_on_path()

    from app.constants.grad_program_focus import GRAD_PROGRAM_FOCUS_TO_TYPE
    from app.constants.target_us_schools import ALL_TARGET_US_SCHOOLS
    from app.dspy.program_dossier_researcher import run_program_dossier_researcher

    parser = argparse.ArgumentParser(
        description="Research school+program admissions dossiers via DSPy + Perplexity."
    )
    parser.add_argument(
        "--cycle-year",
        type=int,
        default=None,
        help="Admissions cycle year (default: current year).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LiteLLM model name (default: perplexity/sonar-pro).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Perplexity API base URL.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Output directory for JSON dossiers.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=None,
        help="Sleep between calls to avoid rate limits.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If set > 0, only run the first N targets.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing dossier files.",
    )
    parser.add_argument(
        "--schools",
        type=str,
        default=None,
        help="Comma-separated list of schools. Default: the hardcoded target US schools list.",
    )
    parser.add_argument(
        "--programs",
        type=str,
        default=None,
        help="Comma-separated list of program focus slugs (e.g. mba_full_time, ms_data_science). Default: all hardcoded slugs.",
    )
    args = parser.parse_args()

    no_cli_flags = len(sys.argv) <= 1
    last_run = _read_json(_LAST_RUN_PATH) if no_cli_flags else None

    cycle_year = int(
        (last_run.get("cycle_year") if last_run else None)
        or (args.cycle_year if args.cycle_year is not None else None)
        or (os.getenv("CYCLE_YEAR") or "")
        or datetime.now().year
    )
    model = (
        (last_run.get("model") if last_run else None)
        or (args.model if args.model else None)
        or os.getenv("PERPLEXITY_MODEL")
        or "perplexity/sonar-pro"
    )
    base_url = (
        (last_run.get("base_url") if last_run else None)
        or (args.base_url if args.base_url else None)
        or os.getenv("PERPLEXITY_BASE_URL")
        or "https://api.perplexity.ai"
    )
    sleep_seconds = float(
        (last_run.get("sleep_seconds") if last_run else None)
        or (args.sleep_seconds if args.sleep_seconds is not None else None)
        or (os.getenv("PROGRAM_DOSSIER_SLEEP_SECONDS") or "1.0")
    )
    limit = int(
        (last_run.get("limit") if last_run else None)
        or (args.limit if args.limit is not None else None)
        or (os.getenv("PROGRAM_DOSSIER_LIMIT") or "0")
    )
    schools_csv = (
        (last_run.get("schools") if last_run else None)
        if (no_cli_flags and last_run and last_run.get("schools") is not None)
        else (args.schools if args.schools is not None else None)
    )
    programs_csv = (
        (last_run.get("programs") if last_run else None)
        if (no_cli_flags and last_run and last_run.get("programs") is not None)
        else (args.programs if args.programs is not None else None)
    )

    api_key = os.getenv("PERPLEXITY_API_KEY") or ""
    if not api_key:
        raise SystemExit(
            "Missing PERPLEXITY_API_KEY. Export it, e.g. `export PERPLEXITY_API_KEY=...`."
        )

    _configure_perplexity_dspy(model=model, api_key=api_key, base_url=base_url)

    schools = (
        [s.strip() for s in str(schools_csv).split(",") if s.strip()]
        if schools_csv and str(schools_csv).strip()
        else list(ALL_TARGET_US_SCHOOLS)
    )
    program_slugs = (
        [p.strip() for p in str(programs_csv).split(",") if p.strip()]
        if programs_csv and str(programs_csv).strip()
        else list(GRAD_PROGRAM_FOCUS_TO_TYPE.keys())
    )

    default_out_dir = _STATE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir_raw = (
        (last_run.get("out_dir") if last_run else None)
        if (no_cli_flags and last_run and last_run.get("out_dir"))
        else (args.out_dir if args.out_dir else None)
    ) or os.getenv("PROGRAM_DOSSIER_OUT_DIR") or str(default_out_dir)
    out_dir = Path(out_dir_raw).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = list(_iter_targets(schools=schools, program_slugs=program_slugs))
    if limit and limit > 0:
        targets = targets[:limit]

    run_config = {
        "generated_at": datetime.now().isoformat(),
        "cycle_year": int(cycle_year),
        "model": str(model),
        "base_url": str(base_url),
        "sleep_seconds": float(sleep_seconds),
        "limit": int(limit),
        "schools": (str(schools_csv) if (schools_csv is not None and str(schools_csv).strip()) else None),
        "programs": (str(programs_csv) if (programs_csv is not None and str(programs_csv).strip()) else None),
        "out_dir": str(out_dir),
    }
    _write_json(out_dir / "run_config.json", run_config)
    _write_json(_LAST_RUN_PATH, run_config)

    index_rows: list[dict[str, Any]] = []
    ok = 0
    skipped = 0
    failed = 0

    def _flush_index() -> None:
        _write_json(
            out_dir / "index.json",
            {
                "generated_at": datetime.now().isoformat(),
                "cycle_year": int(cycle_year),
                "model": str(model),
                "base_url": str(base_url),
                "counts": {
                    "ok": ok,
                    "skipped": skipped,
                    "failed": failed,
                    "total": len(targets),
                },
                "rows": index_rows,
            },
        )

    for i, (school, slug, program_label) in enumerate(targets, start=1):
        filename = f"{_safe_filename(school)}__{_safe_filename(slug)}.json"
        out_path = out_dir / filename
        if out_path.exists() and not args.overwrite:
            skipped += 1
            index_rows.append(
                {
                    "school": school,
                    "program_slug": slug,
                    "program_label": program_label,
                    "path": str(out_path),
                    "status": "skipped_exists",
                }
            )
            _flush_index()
            continue

        try:
            dossier = run_program_dossier_researcher(
                school=school,
                program=program_label,
                cycle_year=int(cycle_year),
            )
            payload = dossier.dossier
            payload.setdefault("program_slug", slug)
            payload.setdefault("generated_at", datetime.now().isoformat())
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ok += 1
            index_rows.append(
                {
                    "school": school,
                    "program_slug": slug,
                    "program_label": program_label,
                    "path": str(out_path),
                    "status": "ok",
                }
            )
        except Exception as e:  # noqa: BLE001
            failed += 1
            index_rows.append(
                {
                    "school": school,
                    "program_slug": slug,
                    "program_label": program_label,
                    "path": str(out_path),
                    "status": "error",
                    "error": str(e),
                }
            )

        _flush_index()

        if i < len(targets) and sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    print(f"Done. ok={ok} skipped={skipped} failed={failed} out_dir={out_dir}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

