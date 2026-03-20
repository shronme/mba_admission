"""Dependencies for API routes (auth, etc.)."""

from .auth import get_candidate_id_from_bearer_token

__all__ = ["get_candidate_id_from_bearer_token"]

