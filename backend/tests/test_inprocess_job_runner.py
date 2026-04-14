import asyncio

import pytest

from app.core.job_runner import InProcessJobRunner, JobType


@pytest.mark.asyncio
async def test_job_runner_processes_enqueued_job(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = InProcessJobRunner()

    processed: list[tuple[JobType, dict]] = []

    async def fake_dispatch(job_type: JobType, payload: dict) -> None:
        processed.append((job_type, payload))
        # Stop after first job to keep the test bounded.
        assert runner._stop_event is not None
        runner._stop_event.set()

    monkeypatch.setattr(runner, "_dispatch", fake_dispatch)

    runner._queue = asyncio.Queue()
    runner._stop_event = asyncio.Event()
    runner._started = True

    # Spawn a single worker loop.
    worker = asyncio.create_task(runner._worker_loop(0))
    runner.enqueue(JobType.SAMPLE_SLEEP, {"ai_run_id": "x", "sleep_seconds": 0})

    await asyncio.wait_for(worker, timeout=2.0)

    assert processed == [(JobType.SAMPLE_SLEEP, {"ai_run_id": "x", "sleep_seconds": 0})]

