import app.db.models  # noqa: F401 - register mappers
from app.db.base import Base


def test_all_task002_tables_registered() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    expected = {
        "candidates",
        "candidate_profiles",
        "chat_threads",
        "chat_messages",
        "cv_drafts",
        "uploaded_files",
        "strategy_decisions",
        "task_items",
        "essay_drafts",
        "essay_reviews",
        "ai_runs",
        "audit_events",
    }
    assert expected <= names
