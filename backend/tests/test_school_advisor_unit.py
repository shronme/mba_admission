from __future__ import annotations

import os
import uuid

import pytest

from app.dspy.pipeline import generate_assistant_response


@pytest.mark.asyncio
async def test_advisor_module_mock_returns_non_empty() -> None:
    os.environ["DSPY_MODE"] = "mock"
    out = await generate_assistant_response(
        user_message="Help with my CV gaps",
        file_count=0,
        candidate_profile={"full_name": "Test", "attributes": {"foo": "bar"}},
        docs_snippets=[],
        recent_messages=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
        profile_complete=True,
        current_completeness_score=100,
        thread_stage="advisor",
        selected_schools=[{"school": "Harvard Business School", "program_slug": "mba"}],
        admission_evaluation_result={"status": "complete", "primary": [], "extra": []},
        session=object(),
        candidate_id=uuid.uuid4(),
        openai_client=object(),
    )
    # Advisor stage returns a Prediction.
    text = str(getattr(out, "response", "") or "")
    assert text.strip()

