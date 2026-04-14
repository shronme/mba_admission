from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any, Callable, Awaitable

import anyio
from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.sync_db import sync_session_scope
from app.db.enums import AiRunStatus
from app.db.models.ai_run import AiRun

logger = logging.getLogger(__name__)


class JobType(StrEnum):
    PROCESS_UPLOADED_DOCUMENT = "process_uploaded_document"
    UPDATE_PROFILE_FROM_DOCUMENT = "update_profile_from_document"
    ADMISSION_EVALUATION = "admission_evaluation"
    SAMPLE_SLEEP = "sample_sleep"


@dataclass(frozen=True)
class JobRequest:
    job_type: JobType
    payload: dict[str, Any]
    enqueued_at_monotonic: float


class InProcessJobRunner:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[JobRequest] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._started = False
        self._stop_event: asyncio.Event | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def enqueue(self, job_type: JobType, payload: dict[str, Any]) -> None:
        if not settings.job_runner_enabled:
            logger.info("job_runner enqueue_skipped disabled job_type=%s", job_type)
            return
        if self._queue is None:
            raise RuntimeError("job runner not started")
        req = JobRequest(job_type=job_type, payload=payload, enqueued_at_monotonic=time.monotonic())
        self._queue.put_nowait(req)

    async def start(self) -> None:
        if not settings.job_runner_enabled:
            logger.info("job_runner disabled")
            return
        if self._started:
            return

        self._queue = asyncio.Queue(maxsize=max(1, int(settings.job_runner_queue_maxsize)))
        self._stop_event = asyncio.Event()
        # Use a single dedicated sync executor thread. DSPy settings are thread-affine, so
        # running sync jobs in a pool can cause cross-thread configuration errors.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="job_runner_sync",
        )
        self._started = True

        try:
            await self._reconcile_stale_ai_runs()
        except Exception:  # noqa: BLE001 - best-effort recovery only
            logger.exception("job_runner reconcile_failed (continuing without recovery)")

        conc = max(1, int(settings.job_runner_concurrency))
        for idx in range(conc):
            self._workers.append(asyncio.create_task(self._worker_loop(idx)))

        logger.info(
            "job_runner started concurrency=%s queue_maxsize=%s",
            conc,
            settings.job_runner_queue_maxsize,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        assert self._stop_event is not None
        self._stop_event.set()
        for t in list(self._workers):
            t.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._queue = None
        self._stop_event = None
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
        self._executor = None
        self._started = False
        logger.info("job_runner stopped")

    async def _run_sync_job(self, func: Callable[..., Any], /, *args: Any) -> Any:
        """
        Run sync job functions in the single dedicated executor thread.
        """
        if self._executor is None:
            # Should never happen after start(), but fall back to AnyIO default.
            return await anyio.to_thread.run_sync(func, *args)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def _worker_loop(self, worker_idx: int) -> None:
        assert self._queue is not None
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                req = await self._queue.get()
            except asyncio.CancelledError:
                return

            started = time.monotonic()
            try:
                logger.info(
                    "job_runner job_start worker=%s job_type=%s", worker_idx, req.job_type
                )
                await self._dispatch(req.job_type, req.payload)
                elapsed_ms = (time.monotonic() - started) * 1000.0
                logger.info(
                    "job_runner job_done worker=%s job_type=%s elapsed_ms=%.2f",
                    worker_idx,
                    req.job_type,
                    elapsed_ms,
                )
            except Exception:
                logger.exception(
                    "job_runner job_failed worker=%s job_type=%s payload_keys=%s",
                    worker_idx,
                    req.job_type,
                    list(req.payload.keys()),
                )
            finally:
                self._queue.task_done()

    async def _dispatch(self, job_type: JobType, payload: dict[str, Any]) -> None:
        if job_type == JobType.PROCESS_UPLOADED_DOCUMENT:
            file_id = str(payload["file_id"])
            from app.workers.tasks.document_processing import process_uploaded_document

            await self._run_sync_job(process_uploaded_document, file_id)
            # Chain profile update (mirrors Celery behavior).
            self.enqueue(JobType.UPDATE_PROFILE_FROM_DOCUMENT, {"file_id": file_id})
            return

        if job_type == JobType.UPDATE_PROFILE_FROM_DOCUMENT:
            from app.workers.tasks.profile_update import update_profile_from_document

            await self._run_sync_job(update_profile_from_document, str(payload["file_id"]))
            return

        if job_type == JobType.SAMPLE_SLEEP:
            from app.workers.tasks.sample_ai_job_task import sample_sleep_ai_job

            await self._run_sync_job(sample_sleep_ai_job, payload)
            return

        if job_type == JobType.ADMISSION_EVALUATION:
            from app.workers.tasks.admission_evaluation_task import admission_evaluation_job

            await self._run_sync_job(admission_evaluation_job, payload)
            return

        raise ValueError(f"unknown job_type: {job_type}")

    async def _reconcile_stale_ai_runs(self) -> None:
        """
        Best-effort recovery for in-process execution.

        We do not add schema columns, so we use `updated_at` as a heartbeat proxy:
        - QUEUED runs are re-enqueued (idempotent tasks should tolerate duplicates).
        - RUNNING runs older than JOB_RUNNER_STALE_SECONDS are moved back to QUEUED and re-enqueued.
        """

        stale_after = max(60, int(settings.job_runner_stale_seconds))

        def _reconcile_sync() -> list[uuid.UUID]:
            now = datetime.now(timezone.utc)
            stale_cutoff = now - timedelta(seconds=stale_after)
            to_enqueue: list[uuid.UUID] = []
            with sync_session_scope() as session:
                rows = list(
                    session.execute(
                        select(AiRun).where(AiRun.status.in_([AiRunStatus.QUEUED, AiRunStatus.RUNNING]))
                    ).scalars()
                )
                for r in rows:
                    if r.status == AiRunStatus.QUEUED:
                        to_enqueue.append(r.id)
                        continue
                    # RUNNING
                    updated = r.updated_at
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                    if updated <= stale_cutoff:
                        r.status = AiRunStatus.QUEUED
                        r.error_message = None
                        to_enqueue.append(r.id)
            return to_enqueue

        run_ids = await anyio.to_thread.run_sync(_reconcile_sync)

        # Map ai_run.request.kind to job type (for supported jobs).
        enq_count = 0
        for rid in run_ids:
            job = await anyio.to_thread.run_sync(_job_from_ai_run_id, rid)
            if job is None:
                continue
            self.enqueue(job.job_type, job.payload)
            enq_count += 1

        if enq_count:
            logger.info("job_runner reconciled re_enqueued=%s", enq_count)


def _job_from_ai_run_id(run_id: uuid.UUID) -> JobRequest | None:
    with sync_session_scope() as session:
        row = session.get(AiRun, run_id)
        if row is None:
            return None
        req = row.request or {}
        kind = str(req.get("kind") or "").strip().lower()
        if kind == "sample_sleep":
            return JobRequest(
                job_type=JobType.SAMPLE_SLEEP,
                payload={
                    "ai_run_id": str(run_id),
                    **req,
                },
                enqueued_at_monotonic=time.monotonic(),
            )
        if kind == "admission_evaluation":
            # admission_evaluation route stores candidate_id elsewhere; it is included in the Celery payload,
            # but `ai_runs.request` contains kind/correlation_id. Reconciliation can't infer candidate_id safely.
            return None
        return None


job_runner = InProcessJobRunner()


def attach_job_runner(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _startup() -> None:
        await job_runner.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await job_runner.stop()

