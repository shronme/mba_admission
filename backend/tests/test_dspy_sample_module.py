from __future__ import annotations

from app.dspy.static_intent_classifier import StaticIntentClassifier
from app.core.dspy_runtime import run_dspy_module


def test_static_intent_classifier_documents() -> None:
    mod = StaticIntentClassifier()
    out = run_dspy_module(mod, message="Upload my grades and transcript. What should I do?")
    assert out.intent == "intake_documents"


def test_static_intent_classifier_goals() -> None:
    mod = StaticIntentClassifier()
    out = run_dspy_module(mod, message="What are good goals for an MBA admission?")
    assert out.intent == "intake_goals"


def test_static_intent_classifier_off_topic() -> None:
    mod = StaticIntentClassifier()
    out = run_dspy_module(mod, message="I want calculus tutoring, not admissions.")
    assert out.intent == "off_topic"

