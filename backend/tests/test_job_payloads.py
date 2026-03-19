import uuid

import pytest
from pydantic import ValidationError

from app.workers.payloads import SampleSleepJobPayload, merge_request_meta


def test_sample_sleep_payload_coerces_uuid_string() -> None:
    rid = uuid.uuid4()
    p = SampleSleepJobPayload.model_validate(
        {
            "ai_run_id": str(rid),
            "sleep_seconds": 0.1,
            "correlation_id": "req-123",
        },
    )
    assert p.ai_run_id == rid
    assert p.correlation_id == "req-123"


def test_sample_sleep_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError):
        SampleSleepJobPayload.model_validate(
            {"ai_run_id": str(uuid.uuid4()), "unknown": 1},
        )


def test_merge_request_meta() -> None:
    out = merge_request_meta(
        {"a": 1},
        celery_task_id="celery-abc",
        correlation_id="corr-xyz",
    )
    assert out["a"] == 1
    assert out["_meta"]["celery_task_id"] == "celery-abc"
    assert out["_meta"]["correlation_id"] == "corr-xyz"
