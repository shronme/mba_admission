import pytest
from pydantic import ValidationError

from app.schemas.candidates import CandidateEnterRequest


def test_enter_request_accepts_valid_email() -> None:
    r = CandidateEnterRequest(email="user@example.com", full_name="User Example")
    assert r.email == "user@example.com"


def test_enter_request_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        CandidateEnterRequest(email="not-an-email")
