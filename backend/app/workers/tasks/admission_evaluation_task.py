"""
Celery task: admission evaluation — per-program research (Perplexity), optional OpenAI
supplement, structured evaluation; optional extra programs if any primary score < 85.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.sync_db import sync_session_scope
from app.db.enums import AiRunStatus, CandidateStage
from app.db.models.candidate import Candidate, CandidateProfile
from app.dspy import admission_evaluation as aes
from app.workers.ai_run_sync import (
    get_ai_run,
    mark_ai_run_failed,
    mark_ai_run_running,
    mark_ai_run_succeeded,
)
from app.workers.base_task import AiJobTask, attach_worker_meta_to_ai_run
from app.workers.payloads import AdmissionEvaluationJobPayload
from app.workers.profile_attributes_sync import merge_profile_attributes_sync

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_update(
    *,
    ai_run_id: uuid.UUID,
    message: str,
    current_school: str,
    current_program_display_name: str,
    current_program_slug: str,
    program_index: int,
    programs_total: int,
    substep: str,
    phase_scope: str,
    progress_percent: int,
    programs_completed: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "ai_run_id": str(ai_run_id),
        "phase": "running",
        "message": message,
        "updated_at": _now_iso(),
        "current_school": current_school,
        "current_program_display_name": current_program_display_name,
        "current_program_slug": current_program_slug,
        "program_index": program_index,
        "programs_total": programs_total,
        "substep": substep,
        "phase_scope": phase_scope,
        "progress_percent": max(0, min(100, progress_percent)),
        "programs_completed": programs_completed,
    }


def _persist_job(
    session,
    candidate_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    merge_profile_attributes_sync(
        session,
        candidate_id,
        {"admission_evaluation_job": payload},
        overwrite=True,
    )


def _selections_from_attrs(attrs: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (attrs or {}).get("school_program_selections")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        school = str(row.get("school") or "").strip()
        slug = str(row.get("program_slug") or "").strip()
        if not school or not slug:
            continue
        out.append(row)
    return out


def json_dossier(d: dict[str, Any]) -> str:
    try:
        return json.dumps(d, ensure_ascii=False, indent=0)[:24000]
    except (TypeError, ValueError):
        return str(d)[:24000]


@celery_app.task(bind=True, base=AiJobTask, name="app.jobs.admission_evaluation")
def admission_evaluation_job(self, payload: dict) -> dict:
    data = AdmissionEvaluationJobPayload.model_validate(payload)
    attach_worker_meta_to_ai_run(
        ai_run_id=data.ai_run_id,
        celery_task_id=self.request.id,
        correlation_id=data.correlation_id,
    )

    with sync_session_scope() as session:
        run = get_ai_run(session, data.ai_run_id)
        if run is None:
            raise ValueError(f"ai_run not found: {data.ai_run_id}")
        if run.status == AiRunStatus.SUCCEEDED:
            return {"ai_run_id": str(data.ai_run_id), "skipped": True}
        mark_ai_run_running(session, data.ai_run_id)

    candidate_id = data.candidate_id

    with sync_session_scope() as session:
        prof = session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
        ).scalar_one_or_none()
        attrs = dict(prof.attributes or {}) if prof else {}
        selections = _selections_from_attrs(attrs)

    if not selections:
        with sync_session_scope() as session:
            merge_profile_attributes_sync(
                session,
                candidate_id,
                {
                    "admission_evaluation_result": {
                        "status": "failed",
                        "error": "missing school_program_selections",
                        "primary": [],
                        "extra": [],
                    },
                    "admission_evaluation_job": None,
                },
                overwrite=True,
            )
            mark_ai_run_failed(session, data.ai_run_id, "No school_program_selections on profile")
        return {"ai_run_id": str(data.ai_run_id), "status": "failed"}

    profile_text = aes.format_profile_snapshot(attrs)
    test_scores_text = aes.format_test_scores(attrs)
    primary_rows: list[dict[str, Any]] = []
    extra_rows: list[dict[str, Any]] = []
    programs_completed: list[dict[str, str]] = []
    cycle_year = datetime.now().year
    n_primary = len(selections)

    # Prime profile so the UI does not sit at 0% until the first slow Perplexity call returns.
    with sync_session_scope() as session:
        _persist_job(
            session,
            candidate_id,
            _job_update(
                ai_run_id=data.ai_run_id,
                message="Starting admission evaluation…",
                current_school="",
                current_program_display_name="",
                current_program_slug="",
                program_index=0,
                programs_total=n_primary,
                substep="research",
                phase_scope="primary",
                progress_percent=2,
                programs_completed=[],
            ),
        )

    try:
        for idx, sel in enumerate(selections):
            school = str(sel.get("school") or "").strip()
            slug = str(sel.get("program_slug") or "").strip()
            label = aes.program_display_label(school, slug)
            if str(sel.get("program_slug")) == "other_graduate":
                po = (sel.get("program_other") or "").strip()
                if po:
                    label = po

            pct_base = int(80 * idx / max(1, n_primary))

            def commit_job(
                msg: str,
                sub: str,
                prog: int,
            ) -> None:
                with sync_session_scope() as s:
                    _persist_job(
                        s,
                        candidate_id,
                        _job_update(
                            ai_run_id=data.ai_run_id,
                            message=msg,
                            current_school=school,
                            current_program_display_name=label,
                            current_program_slug=slug,
                            program_index=idx,
                            programs_total=n_primary,
                            substep=sub,
                            phase_scope="primary",
                            progress_percent=prog,
                            programs_completed=list(programs_completed),
                        ),
                    )

            commit_job(f"Researching {school}…", "research", pct_base + 2)

            dossier = aes.research_program_dossier(
                school=school, program_label=label, cycle_year=cycle_year
            )
            notes = json_dossier(dossier)

            if not aes.dossier_sufficient(dossier):
                commit_job(f"Gathering more sources for {school}…", "supplement", pct_base + 8)
                sup = aes.supplement_with_openai(
                    school=school,
                    program_label=label,
                    cycle_year=cycle_year,
                    prior_summary=notes,
                )
                notes = notes + "\n\n" + sup

            commit_job(f"Evaluating your fit for {school}…", "evaluate", pct_base + 15)

            ev = aes.evaluate_program_json(
                school=school,
                program_label=label,
                program_slug=slug,
                dossier=dossier,
                candidate_profile_text=profile_text + "\n\nResearch notes:\n" + notes[:20000],
                test_scores_text=test_scores_text,
            )
            ev["school"] = school
            ev["program_slug"] = slug
            ev["program_display_name"] = label
            primary_rows.append(ev)
            programs_completed.append({"school": school, "program_display_name": label})

        selected_keys = {(str(s.get("school")), str(s.get("program_slug"))) for s in selections}

        any_low = any(int(r.get("admission_chance_1_100") or 0) < 85 for r in primary_rows)
        extras: list[dict[str, str]] = []
        if any_low:
            extras = aes.pick_similar_programs(
                primary_evaluations=primary_rows,
                selected_keys=selected_keys,
                max_programs=3,
            )

        n_extra = len(extras)
        if n_extra:
            for j, ex in enumerate(extras):
                school = ex["school"]
                slug = ex["program_slug"]
                label = ex["program_display_name"]
                pct_base = 82 + int(15 * j / max(1, n_extra))

                def commit_extra(
                    msg: str,
                    sub: str,
                    prog: int,
                ) -> None:
                    with sync_session_scope() as s:
                        _persist_job(
                            s,
                            candidate_id,
                            _job_update(
                                ai_run_id=data.ai_run_id,
                                message=msg,
                                current_school=school,
                                current_program_display_name=label,
                                current_program_slug=slug,
                                program_index=j,
                                programs_total=n_extra,
                                substep=sub,
                                phase_scope="extra",
                                progress_percent=min(99, prog),
                                programs_completed=list(programs_completed),
                            ),
                        )

                commit_extra(f"Researching alternative: {school}…", "research", pct_base)
                dossier = aes.research_program_dossier(
                    school=school, program_label=label, cycle_year=cycle_year
                )
                notes = json_dossier(dossier)
                if not aes.dossier_sufficient(dossier):
                    commit_extra(f"Gathering more sources for {school}…", "supplement", pct_base + 2)
                    sup = aes.supplement_with_openai(
                        school=school,
                        program_label=label,
                        cycle_year=cycle_year,
                        prior_summary=notes,
                    )
                    notes = notes + "\n\n" + sup
                commit_extra(f"Evaluating {school}…", "evaluate", pct_base + 5)
                ex_ev = aes.evaluate_extra_program_json(
                    school=school,
                    program_label=label,
                    program_slug=slug,
                    dossier=dossier,
                    candidate_profile_text=profile_text + "\n\nResearch notes:\n" + notes[:16000],
                )
                extra_rows.append(ex_ev)

        result = {
            "status": "complete",
            "primary": primary_rows,
            "extra": extra_rows,
            "error": None,
        }

        with sync_session_scope() as session:
            merge_profile_attributes_sync(
                session,
                candidate_id,
                {
                    "admission_evaluation_result": result,
                    "admission_evaluation_job": None,
                    "admission_evaluation_complete": True,
                },
                overwrite=True,
            )
            cand = session.get(Candidate, candidate_id)
            if cand is not None:
                cand.stage = CandidateStage.PROGRAM_RESEARCH
            mark_ai_run_succeeded(
                session,
                data.ai_run_id,
                response={
                    "kind": "admission_evaluation",
                    "primary_count": len(primary_rows),
                    "extra_count": len(extra_rows),
                },
            )

        logger.info(
            "admission_evaluation succeeded ai_run_id=%s candidate_id=%s",
            data.ai_run_id,
            candidate_id,
        )
        return {"ai_run_id": str(data.ai_run_id), "status": "succeeded"}

    except Exception as e:  # noqa: BLE001
        logger.exception("admission_evaluation failed: %s", e)
        err_msg = str(e)[:8000]
        with sync_session_scope() as session:
            merge_profile_attributes_sync(
                session,
                candidate_id,
                {
                    "admission_evaluation_result": {
                        "status": "failed",
                        "error": err_msg,
                        "primary": primary_rows,
                        "extra": extra_rows,
                    },
                    "admission_evaluation_job": None,
                },
                overwrite=True,
            )
            mark_ai_run_failed(session, data.ai_run_id, err_msg)
        raise
