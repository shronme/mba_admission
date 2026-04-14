from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import dspy

_SCRIPT_PATH = Path(__file__).resolve()
_BACKEND_DIR = _SCRIPT_PATH.parents[1]
_REPO_ROOT = _SCRIPT_PATH.parents[2]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rank_schools")

CATALOG_PATH_DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "constants"
    / "graduate_programs_by_school.json"
)


def _ensure_backend_on_path() -> None:
    """
    Allow running via `python backend/scripts/rank_schools.py` by ensuring
    `backend/` is on sys.path for `import app.*`.
    """
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))


def _extract_env_file_arg(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--env-file" and i + 1 < len(argv):
            return argv[i + 1].strip() or None
    return None


def _load_dotenv_files(*, cli_env_file: str | None) -> None:
    from dotenv import load_dotenv

    # Shell env wins over file values.
    for env_path in (_REPO_ROOT / ".env", _REPO_ROOT / "backend" / ".env"):
        if env_path.is_file():
            load_dotenv(env_path, override=False)
    if cli_env_file:
        p = Path(cli_env_file).expanduser()
        if p.is_file():
            load_dotenv(p, override=False)


def _has_flag(argv: list[str], flag: str) -> bool:
    return any(a == flag for a in argv)


def _value_after_flag(argv: list[str], flag: str) -> str | None:
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            v = argv[i + 1].strip()
            return v or None
    return None


def _force_perplexity_for_this_run(*, argv: list[str]) -> None:
    """
    Convenience: allow forcing Perplexity without editing `.env`.

    This only affects the current Python process (no files changed).
    """

    if not _has_flag(argv, "--use-perplexity"):
        return

    model = (
        _value_after_flag(argv, "--perplexity-model")
        or (os.getenv("PERPLEXITY_MODEL") or "").strip()
        or "perplexity/sonar-pro"
    )
    os.environ["DSPY_MODE"] = "perplexity"
    os.environ["DSPY_MODEL"] = model
    logger.info("forced_perplexity mode=perplexity model=%s", model)


def _bootstrap_dspy_env_defaults() -> None:
    """
    Convenience mapping so `.env` can be minimal:
    - If DSPY_MODEL is unset, use PERPLEXITY_MODEL or PROGRAM_DISCOVERY_OPENAI_MODEL.
    - If DSPY_MODE is unset, infer it from model prefix / available API keys.
    """

    dspy_model = (os.getenv("DSPY_MODEL") or "").strip()
    if not dspy_model:
        dspy_model = (
            (os.getenv("PERPLEXITY_MODEL") or "").strip()
            or (os.getenv("PROGRAM_DISCOVERY_OPENAI_MODEL") or "").strip()
        )
        if dspy_model:
            os.environ["DSPY_MODEL"] = dspy_model

    dspy_mode = (os.getenv("DSPY_MODE") or "").strip().lower()
    if not dspy_mode:
        model = (os.getenv("DSPY_MODEL") or "").strip()
        has_pplx = bool((os.getenv("PERPLEXITY_API_KEY") or os.getenv("PERPLEXITYAI_API_KEY") or "").strip())
        has_openai = bool((os.getenv("OPENAI_API_KEY") or "").strip())

        if model.startswith("perplexity/") or has_pplx:
            os.environ["DSPY_MODE"] = "perplexity"
        elif has_openai:
            os.environ["DSPY_MODE"] = "openai"


def _safe_json_loads_any(raw: str) -> Any | None:
    # Reuse the same behavior as other DSPy helpers in the repo: accept either
    # a JSON array/object, and tolerate accidental markdown fences.
    import re

    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _load_school_names(catalog_path: Path) -> list[str]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw = data.get("schools")
    if not isinstance(raw, dict):
        raise ValueError(f"{catalog_path}: missing/invalid 'schools' object")
    out: list[str] = []
    for k in raw.keys():
        name = str(k).strip()
        if name:
            out.append(name)
    return sorted(set(out))


def _apply_contains_filters(names: list[str], contains: list[str]) -> list[str]:
    if not contains:
        return names
    lowered = [c.lower() for c in contains if c.strip()]
    if not lowered:
        return names
    out: list[str] = []
    for n in names:
        nl = n.lower()
        if all(c in nl for c in lowered):
            out.append(n)
    return out


def _apply_allowlist(names: list[str], allowlist_path: Path | None) -> list[str]:
    if allowlist_path is None:
        return names
    raw = allowlist_path.read_text(encoding="utf-8").splitlines()
    allow = {line.strip() for line in raw if line.strip() and not line.strip().startswith("#")}
    if not allow:
        return []
    allow_lower = {a.lower() for a in allow}
    return [n for n in names if n.lower() in allow_lower]


def _chunked(xs: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(xs), size):
        yield xs[i : i + size]


@dataclass(frozen=True)
class RankedSchool:
    school: str
    rank: int | None
    source: str
    evidence_url: str | None
    notes: str | None


class RankSchoolsSignature(dspy.Signature):
    """
    You are ranking schools using an explicit public ranking source.

    Task:
    - Given a ranking source name (e.g. "U.S. News Best Business Schools 2026")
      and a list of school names, produce a ranking-ordered list.
    - Use the ranking source as the ground truth; do not invent ranks.

    Output rules:
    - Output MUST be valid JSON (no markdown): a JSON array only.
    - Each element MUST be:
      {"school": string, "rank": number|null, "source": string,
       "evidence_url": string|null, "notes": string|null}
    - If a school is not present / ambiguous in the source, set rank to null and
      include a short disambiguation note.
    - Preserve input school names exactly in the "school" field.
    - Sort primarily by ascending rank (1 is best); null ranks go last.
    """

    ranking_source: str = dspy.InputField(
        desc="Ranking source, e.g. 'U.S. News Best Business Schools 2026'."
    )
    schools_json: str = dspy.InputField(desc='JSON array of school names (strings).')
    ranked_json: str = dspy.OutputField(desc="JSON array only (no markdown).")


class RankSchoolsSecondPassSignature(dspy.Signature):
    """
    Second-pass recovery for schools that were unranked in the first pass.

    Task:
    - Prefer the provided primary ranking source (ranking_source_primary).
    - If a school is missing/ambiguous in the primary source, broaden the search using
      the fallback sources list (ranking_sources_fallback), and set "source" to the
      exact source you used.
    - Be tolerant of naming variants (e.g. "University of X" vs "X University",
      campus suffixes, abbreviations like "UC Berkeley").
    - Include an evidence_url whenever possible.

    Output MUST be valid JSON (no markdown): a JSON array only.
    Element shape:
      {"school": string, "rank": number|null, "source": string,
       "evidence_url": string|null, "notes": string|null}
    """

    ranking_source_primary: str = dspy.InputField(desc="Primary ranking source to prefer.")
    ranking_sources_fallback: str = dspy.InputField(
        desc="JSON array of fallback source strings (may be empty)."
    )
    schools_json: str = dspy.InputField(desc="JSON array of school names to recover.")
    ranked_json: str = dspy.OutputField(desc="JSON array only (no markdown).")


class RankSchoolsModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(RankSchoolsSignature)

    def forward(self, *, ranking_source: str, schools_json: str) -> dspy.Prediction:  # type: ignore[override]
        return self._predict(ranking_source=ranking_source, schools_json=schools_json)


class RankSchoolsSecondPassModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(RankSchoolsSecondPassSignature)

    def forward(  # type: ignore[override]
        self,
        *,
        ranking_source_primary: str,
        ranking_sources_fallback: str,
        schools_json: str,
    ) -> dspy.Prediction:
        return self._predict(
            ranking_source_primary=ranking_source_primary,
            ranking_sources_fallback=ranking_sources_fallback,
            schools_json=schools_json,
        )


def _normalize_ranked(raw: Any, *, source: str) -> list[RankedSchool]:
    items: list[Any]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("rankings"), list):
        items = raw["rankings"]
    else:
        items = []

    out: list[RankedSchool] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        school = str(it.get("school") or "").strip()
        if not school:
            continue
        rank_val = it.get("rank")
        rank: int | None
        if rank_val is None or rank_val == "":
            rank = None
        else:
            try:
                rank = int(rank_val)
            except Exception:
                rank = None

        evidence_url_val = it.get("evidence_url")
        evidence_url = None if evidence_url_val is None else str(evidence_url_val).strip() or None
        notes_val = it.get("notes")
        notes = None if notes_val is None else str(notes_val).strip() or None

        out.append(
            RankedSchool(
                school=school,
                rank=rank,
                source=str(it.get("source") or source).strip() or source,
                evidence_url=evidence_url,
                notes=notes,
            )
        )

    out.sort(key=lambda r: (r.rank is None, r.rank if r.rank is not None else 10**9, r.school))
    return out


def _ensure_all_requested_schools_present(
    *,
    requested: list[str],
    got: list[RankedSchool],
    default_source: str,
) -> list[RankedSchool]:
    """
    The model may return a partial list (omit schools it couldn't find).
    We must keep the output aligned with the input set so downstream steps
    (like second pass) can see all missing items.
    """

    by_school: dict[str, RankedSchool] = {r.school: r for r in got}
    out = list(got)
    for s in requested:
        if s not in by_school:
            out.append(
                RankedSchool(
                    school=s,
                    rank=None,
                    source=default_source,
                    evidence_url=None,
                    notes="Model did not return an entry for this school in this pass.",
                )
            )
    out.sort(key=lambda r: (r.rank is None, r.rank if r.rank is not None else 10**9, r.school))
    return out


def _configure_dspy() -> None:
    """
    Configure DSPy using the same env conventions as the backend.

    Recommended (Perplexity, web-aware):
      export DSPY_MODE=perplexity
      export DSPY_MODEL=perplexity/sonar-pro
      export PERPLEXITY_API_KEY=...
    """

    from app.core.dspy_runtime import configure_dspy_from_env

    configure_dspy_from_env()
    if (os.getenv("DSPY_MODE") or "mock").lower() == "mock":
        raise RuntimeError(
            "DSPy is in mock mode. Set DSPY_MODE=perplexity (recommended) or "
            "DSPY_MODE=openai and OPENAI_API_KEY, plus DSPY_MODEL."
        )
    if dspy.settings.lm is None:
        raise RuntimeError("DSPy LM not configured (check API keys / DSPY_MODEL).")

    logger.info(
        "dspy_configured mode=%s model=%s",
        (os.getenv("DSPY_MODE") or "unknown").strip(),
        (os.getenv("DSPY_MODEL") or "unknown").strip(),
    )


def _run_rank_chunk(*, ranking_source: str, schools: list[str]) -> list[RankedSchool]:
    module = RankSchoolsModule()
    schools_json = json.dumps(schools, ensure_ascii=False)
    pred = module(ranking_source=ranking_source, schools_json=schools_json)
    parsed = _safe_json_loads_any(str(getattr(pred, "ranked_json", "") or ""))
    got = _normalize_ranked(parsed, source=ranking_source) if parsed is not None else []
    return _ensure_all_requested_schools_present(
        requested=schools,
        got=got,
        default_source=ranking_source,
    )


def _run_second_pass_chunk(
    *,
    primary_source: str,
    fallback_sources: list[str],
    schools: list[str],
) -> list[RankedSchool]:
    module = RankSchoolsSecondPassModule()
    schools_json = json.dumps(schools, ensure_ascii=False)
    fallback_json = json.dumps(fallback_sources, ensure_ascii=False)
    pred = module(
        ranking_source_primary=primary_source,
        ranking_sources_fallback=fallback_json,
        schools_json=schools_json,
    )
    parsed = _safe_json_loads_any(str(getattr(pred, "ranked_json", "") or ""))
    got = _normalize_ranked(parsed, source=primary_source) if parsed is not None else []
    return _ensure_all_requested_schools_present(
        requested=schools,
        got=got,
        default_source=primary_source,
    )

def _merge_chunks(chunks: list[list[RankedSchool]]) -> list[RankedSchool]:
    by_school: dict[str, RankedSchool] = {}
    for ch in chunks:
        for r in ch:
            prev = by_school.get(r.school)
            if prev is None:
                by_school[r.school] = r
                continue
            # Prefer non-null rank; then better (smaller) rank.
            if prev.rank is None and r.rank is not None:
                by_school[r.school] = r
            elif prev.rank is not None and r.rank is not None and r.rank < prev.rank:
                by_school[r.school] = r
            elif prev.rank is None and r.rank is None and (r.evidence_url and not prev.evidence_url):
                by_school[r.school] = r

    out = list(by_school.values())
    out.sort(key=lambda r: (r.rank is None, r.rank if r.rank is not None else 10**9, r.school))
    return out


def _write_json(path: Path | None, rows: list[RankedSchool]) -> None:
    payload = [
        {
            "school": r.school,
            "rank": r.rank,
            "source": r.source,
            "evidence_url": r.evidence_url,
            "notes": r.notes,
        }
        for r in rows
    ]
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, rows: list[RankedSchool]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["rank", "school", "source", "evidence_url", "notes"]
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "rank": "" if r.rank is None else r.rank,
                    "school": r.school,
                    "source": r.source,
                    "evidence_url": r.evidence_url or "",
                    "notes": r.notes or "",
                }
            )


def main(argv: list[str] | None = None) -> int:
    argv_in = list(sys.argv[1:] if argv is None else argv)
    _ensure_backend_on_path()
    _load_dotenv_files(cli_env_file=_extract_env_file_arg(argv_in))
    _force_perplexity_for_this_run(argv=argv_in)
    _bootstrap_dspy_env_defaults()

    p = argparse.ArgumentParser(
        description="Rank schools from graduate_programs_by_school.json using Perplexity/OpenAI via DSPy."
    )
    p.add_argument(
        "--env-file",
        default=None,
        help="Optional additional .env file to load (shell env still wins).",
    )
    p.add_argument(
        "--use-perplexity",
        action="store_true",
        help="Force Perplexity for this run only (sets DSPY_MODE=perplexity and DSPY_MODEL).",
    )
    p.add_argument(
        "--perplexity-model",
        default=None,
        help="When using --use-perplexity, override the model id (default: PERPLEXITY_MODEL or perplexity/sonar-pro).",
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=CATALOG_PATH_DEFAULT,
        help="Path to graduate_programs_by_school.json",
    )
    p.add_argument(
        "--ranking-source",
        default="U.S. News & World Report",
        help="Ranking source name the model should use as ground truth (e.g. include the year/category if relevant).",
    )
    p.add_argument(
        "--usnews-category",
        default="Best National Universities",
        help="When --ranking-source is the default 'U.S. News & World Report', this category is appended to make the source unambiguous.",
    )
    p.add_argument(
        "--usnews-year",
        type=int,
        default=int((os.getenv("CYCLE_YEAR") or "2026").strip() or "2026"),
        help="When --ranking-source is the default 'U.S. News & World Report', this year is appended to make the source unambiguous.",
    )
    p.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Optional newline-separated file of school names to include (exact match, case-insensitive).",
    )
    p.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Case-insensitive substring filter; may be repeated (AND).",
    )
    p.add_argument(
        "--max-schools",
        type=int,
        default=120,
        help="Max schools to send to the model (after filters).",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=40,
        help="Schools per model call (helps avoid context limits).",
    )
    p.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format.",
    )
    p.add_argument(
        "--second-pass",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run a second pass for schools that came back with rank=null.",
    )
    p.add_argument(
        "--second-pass-chunk-size",
        type=int,
        default=25,
        help="Schools per model call in the second pass.",
    )
    p.add_argument(
        "--fallback-source",
        action="append",
        default=[],
        help="Fallback ranking source to try in second pass (repeatable). If omitted, uses a small default set.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path. If omitted and format=json, prints to stdout.",
    )

    args = p.parse_args(argv_in)

    logger.info("loading_catalog path=%s", args.catalog)
    schools = _load_school_names(args.catalog)
    logger.info("catalog_loaded schools=%s", len(schools))
    schools = _apply_allowlist(schools, args.allowlist)
    if args.allowlist is not None:
        logger.info("allowlist_applied path=%s remaining=%s", args.allowlist, len(schools))
    schools = _apply_contains_filters(schools, args.contains)
    if args.contains:
        logger.info("contains_filters_applied filters=%s remaining=%s", args.contains, len(schools))
    schools = schools[: max(0, int(args.max_schools))]
    logger.info("schools_selected count=%s chunk_size=%s", len(schools), args.chunk_size)
    if not schools:
        raise SystemExit("No schools selected after filters.")

    ranking_source = str(args.ranking_source).strip()
    if ranking_source == "U.S. News & World Report":
        ranking_source = f"U.S. News & World Report — {args.usnews_category} {int(args.usnews_year)}"

    logger.info("ranking_start source=%s", ranking_source)
    _configure_dspy()

    chunks: list[list[RankedSchool]] = []
    chunk_size = max(1, int(args.chunk_size))
    chunk_list = list(_chunked(schools, chunk_size))
    total = len(chunk_list)
    for idx, chunk in enumerate(chunk_list, start=1):
        logger.info("ranking_chunk %s/%s schools=%s", idx, total, len(chunk))
        chunks.append(_run_rank_chunk(ranking_source=ranking_source, schools=chunk))

    merged = _merge_chunks(chunks)
    ranked_count = sum(1 for r in merged if r.rank is not None)
    logger.info(
        "ranking_done total=%s ranked=%s unranked=%s",
        len(merged),
        ranked_count,
        len(merged) - ranked_count,
    )

    if args.second_pass:
        unranked = [r.school for r in merged if r.rank is None]
        if unranked:
            fallback_sources = list(args.fallback_source or [])
            if not fallback_sources:
                # Conservative defaults: common, broad university rankings.
                fallback_sources = [
                    "ShanghaiRanking Academic Ranking of World Universities (ARWU) 2026",
                    "Times Higher Education World University Rankings 2026",
                    "QS World University Rankings 2026",
                    "Wall Street Journal/College Pulse Best Colleges in the U.S. 2026",
                ]
            logger.info(
                "second_pass_start unranked=%s fallback_sources=%s",
                len(unranked),
                fallback_sources,
            )
            sp_chunks: list[list[RankedSchool]] = []
            sp_size = max(1, int(args.second_pass_chunk_size))
            sp_list = list(_chunked(unranked, sp_size))
            for idx, chunk in enumerate(sp_list, start=1):
                logger.info("second_pass_chunk %s/%s schools=%s", idx, len(sp_list), len(chunk))
                sp_chunks.append(
                    _run_second_pass_chunk(
                        primary_source=ranking_source,
                        fallback_sources=fallback_sources,
                        schools=chunk,
                    )
                )
            recovered = _merge_chunks(sp_chunks)
            recovered_by_school = {r.school: r for r in recovered}
            merged = [
                recovered_by_school.get(r.school, r) if r.rank is None else r for r in merged
            ]
            merged.sort(
                key=lambda r: (
                    r.rank is None,
                    r.rank if r.rank is not None else 10**9,
                    r.school,
                )
            )
            ranked_count2 = sum(1 for r in merged if r.rank is not None)
            logger.info(
                "second_pass_done total=%s ranked=%s unranked=%s",
                len(merged),
                ranked_count2,
                len(merged) - ranked_count2,
            )

    if args.format == "csv":
        if args.out is None:
            raise SystemExit("--out is required for --format=csv")
        _write_csv(args.out, merged)
        logger.info("output_written format=csv path=%s rows=%s", args.out, len(merged))
        return 0

    _write_json(args.out, merged)
    logger.info(
        "output_written format=json path=%s rows=%s",
        str(args.out) if args.out is not None else "<stdout>",
        len(merged),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

