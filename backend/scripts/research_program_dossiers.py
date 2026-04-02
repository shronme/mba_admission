from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import dspy

_SCRIPT_DIR = Path(__file__).resolve()
_REPO_ROOT = _SCRIPT_DIR.parents[2]
_STATE_DIR = _REPO_ROOT / "backend/data/program_dossiers"
_LAST_RUN_PATH = _STATE_DIR / "last_run.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_program_dossiers")


def _ensure_backend_on_path() -> None:
    """
    Allow running this file directly via `python backend/scripts/...py` by
    ensuring `backend/` is on sys.path for `import app.*`.
    """
    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _extract_env_file_arg(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--env-file" and i + 1 < len(argv):
            return argv[i + 1].strip() or None
    return None


def _load_dotenv_files(*, cli_env_file: str | None) -> None:
    from dotenv import load_dotenv

    for env_path in (_REPO_ROOT / ".env", _REPO_ROOT / "backend" / ".env"):
        if env_path.is_file():
            load_dotenv(env_path, override=False)
    if cli_env_file:
        p = Path(cli_env_file).expanduser()
        if p.is_file():
            load_dotenv(p, override=False)


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


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """
    Best-effort atomic-ish JSON write.
    Useful when long-running discovery writes intermediate catalog state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _configure_perplexity_dspy(*, model: str, api_key: str, base_url: str) -> None:
    """
    Configure DSPy/LiteLLM to use Perplexity's OpenAI-compatible API.
    """
    os.environ["DSPY_MODE"] = "perplexity"
    os.environ["DSPY_MODEL"] = model
    try:
        lm = dspy.LM(model, api_key=api_key, api_base=base_url)
    except TypeError:
        lm = dspy.LM(model, api_key=api_key, base_url=base_url)
    dspy.configure(lm=lm)


def _iter_targets_legacy(
    *,
    schools: Iterable[str],
    program_slugs: Iterable[str],
) -> Iterable[tuple[str, str, str]]:
    for school in schools:
        for slug in program_slugs:
            yield school, slug, _slug_to_label(slug)


def _catalog_rows_with_slug(v: Any) -> list[dict[str, Any]]:
    """Rows that will produce dossier targets (non-empty program slug)."""
    if not isinstance(v, list):
        return []
    out: list[dict[str, Any]] = []
    for row in v:
        if not isinstance(row, dict):
            continue
        if str(row.get("slug") or "").strip():
            out.append(row)
    return out


def _catalog_targets_from_map(
    schools: list[str],
    school_programs: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for school in schools:
        skey = school.strip()
        rows = school_programs.get(skey) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            slug = str(row.get("slug") or "").strip()
            if not slug:
                continue
            label = str(row.get("label") or "").strip() or _slug_to_label(slug)
            targets.append((skey, slug, label))
    return targets


def _append_rag_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    _ensure_backend_on_path()
    _load_dotenv_files(cli_env_file=_extract_env_file_arg(sys.argv))

    from app.constants.grad_program_focus import GRAD_PROGRAM_FOCUS_TO_TYPE
    from app.constants.target_us_schools import ALL_TARGET_US_SCHOOLS
    from app.dspy.program_dossier_researcher import run_program_dossier_researcher
    from app.dspy.rag_export import dossier_to_rag_records
    from app.dspy.school_program_offerings import (
        DOSSIER_DISCOVERY_SLUGS,
        run_school_program_offerings,
        run_school_program_offerings_openai,
    )

    parser = argparse.ArgumentParser(
        description="Research school+program admissions dossiers via DSPy + Perplexity "
        "(per-school program discovery, then dossier per program)."
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
        help="LiteLLM model for dossier research (default: perplexity/sonar-pro).",
    )
    parser.add_argument(
        "--discovery-model",
        type=str,
        default=None,
        help="LiteLLM model for per-school program listing (default: PERPLEXITY_MODEL_DISCOVERY or --model).",
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
        "--catalog-out",
        type=str,
        default=None,
        help="Optional extra path to write a copy of graduate_programs_by_school.json.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=None,
        help="Sleep between API calls to avoid rate limits.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If set > 0, only run the first N dossier targets.",
    )
    parser.add_argument(
        "--discovery-limit",
        type=int,
        default=None,
        help="If set > 0, only run program discovery for the first N schools.",
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
        help="(Legacy) Comma-separated program slugs for --legacy-cartesian only.",
    )
    parser.add_argument(
        "--legacy-cartesian",
        action="store_true",
        help="Use schools × global program slugs (old behavior) instead of per-school discovery.",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Load program catalog from --catalog-path instead of calling the LLM.",
    )
    parser.add_argument(
        "--catalog-path",
        type=str,
        default=None,
        help="Path to graduate_programs_by_school.json (required with --skip-discovery).",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Optional .env file path (loaded after repo .env files; does not override existing env).",
    )
    args = parser.parse_args()

    if args.env_file:
        _load_dotenv_files(cli_env_file=args.env_file)

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
    discovery_model = (
        (args.discovery_model if args.discovery_model else None)
        or os.getenv("PERPLEXITY_MODEL_DISCOVERY")
        or model
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
    discovery_limit = int(args.discovery_limit or os.getenv("PROGRAM_DOSSIER_DISCOVERY_LIMIT") or "0")
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

    api_key = (os.getenv("PERPLEXITY_API_KEY") or os.getenv("PERPLEXITYAI_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit(
            "Missing PERPLEXITY_API_KEY (or PERPLEXITYAI_API_KEY). "
            "Set it in `.env` at the repo root or `backend/.env`, or export it in the shell."
        )

    schools = (
        [s.strip() for s in str(schools_csv).split(",") if s.strip()]
        if schools_csv and str(schools_csv).strip()
        else list(ALL_TARGET_US_SCHOOLS)
    )

    default_out_dir = _STATE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir_raw = (
        (last_run.get("out_dir") if last_run else None)
        if (no_cli_flags and last_run and last_run.get("out_dir"))
        else (args.out_dir if args.out_dir else None)
    ) or os.getenv("PROGRAM_DOSSIER_OUT_DIR") or str(default_out_dir)
    out_dir = Path(out_dir_raw).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rag_path = out_dir / "rag" / "chunks.jsonl"
    catalog_filename = "graduate_programs_by_school.json"
    catalog_path = out_dir / catalog_filename

    if args.skip_discovery:
        if not args.catalog_path or not str(args.catalog_path).strip():
            raise SystemExit("--skip-discovery requires --catalog-path to a graduate_programs_by_school.json file.")
        loaded = _read_json(Path(args.catalog_path).expanduser().resolve())
        if not loaded or not isinstance(loaded.get("schools"), dict):
            raise SystemExit(f"Invalid catalog file: {args.catalog_path}")
        school_programs_map: dict[str, list[dict[str, Any]]] = {
            str(k): (v if isinstance(v, list) else [])
            for k, v in loaded["schools"].items()
        }
        targets = _catalog_targets_from_map(schools, school_programs_map)
        _write_json(catalog_path, loaded)
        if args.catalog_out:
            _write_json(Path(args.catalog_out).expanduser().resolve(), loaded)
    elif args.legacy_cartesian:
        program_slugs = (
            [p.strip() for p in str(programs_csv).split(",") if p.strip()]
            if programs_csv and str(programs_csv).strip()
            else list(GRAD_PROGRAM_FOCUS_TO_TYPE.keys())
        )
        targets = list(_iter_targets_legacy(schools=schools, program_slugs=program_slugs))
        sp: dict[str, list[dict[str, Any]]] = {}
        for sch, slug, lab in targets:
            sp.setdefault(sch, []).append(
                {"slug": slug, "label": lab, "confidence": "high", "notes": None}
            )
        catalog_payload = {
            "generated_at": datetime.now().isoformat(),
            "cycle_year": int(cycle_year),
            "mode": "legacy_cartesian",
            "discovery_model": None,
            "dossier_model": str(model),
            "schools": sp,
        }
        _write_json(catalog_path, catalog_payload)
        if args.catalog_out:
            _write_json(Path(args.catalog_out).expanduser().resolve(), catalog_payload)
    else:
        discovery_schools = schools[:discovery_limit] if discovery_limit > 0 else schools
        _configure_perplexity_dspy(model=discovery_model, api_key=api_key, base_url=base_url)

        # Auto-resume: if a catalog exists in out_dir, continue from it.
        loaded_catalog = _read_json(catalog_path) if catalog_path.exists() else None
        school_programs_map: dict[str, list[dict[str, Any]]] = {}
        if loaded_catalog and isinstance(loaded_catalog.get("schools"), dict):
            for k, v in loaded_catalog["schools"].items():
                sk = str(k)
                if isinstance(v, list):
                    # Keep entries as-is; normalize later when building targets.
                    school_programs_map[sk] = [x for x in v if isinstance(x, dict)]

        def _discovery_complete(s: str) -> bool:
            # Re-run discovery for [], missing keys, non-list values, or rows with no usable slug.
            return bool(_catalog_rows_with_slug(school_programs_map.get(s)))

        remaining_schools = [s for s in discovery_schools if not _discovery_complete(s)]
        existing_done_count = sum(1 for s in discovery_schools if _discovery_complete(s))

        if existing_done_count and not remaining_schools:
            logger.info(
                "Resuming discovery: catalog already complete (%d/%d schools).",
                existing_done_count,
                len(discovery_schools),
            )
        elif existing_done_count:
            logger.info(
                "Resuming discovery: %d/%d schools already present; %d remaining.",
                existing_done_count,
                len(discovery_schools),
                len(remaining_schools),
            )
        if remaining_schools and loaded_catalog:
            logger.info(
                "Re-running program discovery for empty/incomplete catalog entries: %s%s",
                ", ".join(remaining_schools[:8]),
                " …" if len(remaining_schools) > 8 else "",
            )

        for si, school in enumerate(remaining_schools, start=existing_done_count + 1):
            logger.info(
                "[%d/%d] discovering programs for: %s",
                si,
                len(discovery_schools),
                school,
            )
            try:
                offerings = run_school_program_offerings(
                    school=school,
                    cycle_year=int(cycle_year),
                    allowed_slugs=DOSSIER_DISCOVERY_SLUGS,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("discovery failed for %s: %s", school, e)
                offerings = []
            rows = [
                {
                    "slug": o.slug,
                    "label": o.label,
                    "confidence": o.confidence,
                    "notes": o.notes,
                }
                for o in offerings
            ]
            if not rows:
                openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
                openai_model = (
                    os.getenv("PROGRAM_DISCOVERY_OPENAI_MODEL")
                    or os.getenv("OPENAI_DISCOVERY_MODEL")
                    or "openai/gpt-4o-mini"
                )
                if openai_key:
                    logger.info(
                        "No programs from primary discovery for %s; trying OpenAI model=%s",
                        school,
                        openai_model,
                    )
                    try:
                        offerings_oai = run_school_program_offerings_openai(
                            school=school,
                            cycle_year=int(cycle_year),
                            model=openai_model,
                            api_key=openai_key,
                            allowed_slugs=DOSSIER_DISCOVERY_SLUGS,
                        )
                    except Exception as oai_e:  # noqa: BLE001
                        logger.warning(
                            "OpenAI discovery fallback failed for %s: %s",
                            school,
                            oai_e,
                        )
                        offerings_oai = []
                    if offerings_oai:
                        rows = [
                            {
                                "slug": o.slug,
                                "label": o.label,
                                "confidence": o.confidence,
                                "notes": o.notes,
                                "discovered_via": "openai_fallback",
                            }
                            for o in offerings_oai
                        ]
                        logger.info(
                            "OpenAI fallback found %d program(s) for %s",
                            len(rows),
                            school,
                        )
                if not rows:
                    logger.warning(
                        "No programs discovered for %s (skipping dossiers for this school).",
                        school,
                    )
            school_programs_map[school] = rows
            # Persist after each school so dropdowns can populate and we can resume.
            catalog_payload = {
                "generated_at": datetime.now().isoformat(),
                "cycle_year": int(cycle_year),
                "mode": "discovery",
                "discovery_model": str(discovery_model),
                "dossier_model": str(model),
                "schools": school_programs_map,
            }
            _write_json_atomic(catalog_path, catalog_payload)
            if args.catalog_out:
                _write_json_atomic(
                    Path(args.catalog_out).expanduser().resolve(),
                    catalog_payload,
                )

            if si < len(discovery_schools) and sleep_seconds > 0:
                time.sleep(float(sleep_seconds))

        targets = _catalog_targets_from_map(discovery_schools, school_programs_map)

    _configure_perplexity_dspy(model=model, api_key=api_key, base_url=base_url)

    if limit and limit > 0:
        targets = targets[:limit]

    run_config = {
        "generated_at": datetime.now().isoformat(),
        "cycle_year": int(cycle_year),
        "model": str(model),
        "discovery_model": str(discovery_model),
        "base_url": str(base_url),
        "sleep_seconds": float(sleep_seconds),
        "limit": int(limit),
        "discovery_limit": int(discovery_limit),
        "schools": (str(schools_csv) if (schools_csv is not None and str(schools_csv).strip()) else None),
        "programs": (str(programs_csv) if (programs_csv is not None and str(programs_csv).strip()) else None),
        "out_dir": str(out_dir),
        "skip_discovery": bool(args.skip_discovery),
        "catalog_path": str(args.catalog_path) if args.catalog_path else None,
        "legacy_cartesian": bool(args.legacy_cartesian),
        "catalog_file": str(catalog_path),
        "rag_chunks": str(rag_path),
    }
    _write_json(out_dir / "run_config.json", run_config)
    _write_json(_LAST_RUN_PATH, run_config)

    school_count = len({t[0] for t in targets}) if targets else 0
    logger.info(
        "Starting dossier run: targets=%d schools_in_targets=%d cycle_year=%s model=%s out_dir=%s sleep_s=%s overwrite=%s",
        len(targets),
        school_count,
        cycle_year,
        model,
        out_dir,
        sleep_seconds,
        args.overwrite,
    )

    index_rows: list[dict[str, Any]] = []
    ok = 0
    skipped = 0
    failed = 0
    rag_count = 0

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
                    "rag_records": rag_count,
                },
                "rows": index_rows,
            },
        )

    for i, (school, slug, program_label) in enumerate(targets, start=1):
        filename = f"{_safe_filename(school)}__{_safe_filename(slug)}.json"
        out_path = out_dir / filename
        if out_path.exists() and not args.overwrite:
            skipped += 1
            logger.info(
                "[%d/%d] skip (exists): %s / %s -> %s",
                i,
                len(targets),
                school,
                slug,
                out_path.name,
            )
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

        logger.info(
            "[%d/%d] researching: %s / %s (%s)",
            i,
            len(targets),
            school,
            slug,
            program_label,
        )
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

            meta = {
                "program_slug": slug,
                "program_label": program_label,
                "cycle_year": int(cycle_year),
                "source_file": str(out_path),
                "dossier_path": str(out_path),
            }
            rag_recs = dossier_to_rag_records(payload, metadata=meta)
            if rag_recs:
                _append_rag_jsonl(rag_path, rag_recs)
                rag_count += len(rag_recs)

            ok += 1
            logger.info(
                "[%d/%d] ok: wrote %s (running totals ok=%d skipped=%d failed=%d)",
                i,
                len(targets),
                out_path.name,
                ok,
                skipped,
                failed,
            )
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
            logger.error(
                "[%d/%d] failed: %s / %s — %s",
                i,
                len(targets),
                school,
                slug,
                e,
            )
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
            logger.info("Sleeping %.2fs before next target (rate limit)", float(sleep_seconds))
            time.sleep(float(sleep_seconds))

    rag_manifest = {
        "generated_at": datetime.now().isoformat(),
        "chunks_path": str(rag_path),
        "record_count": rag_count,
    }
    _write_json(out_dir / "rag" / "manifest.json", rag_manifest)

    logger.info("Done. ok=%d skipped=%d failed=%d rag_records=%d out_dir=%s", ok, skipped, failed, rag_count, out_dir)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
