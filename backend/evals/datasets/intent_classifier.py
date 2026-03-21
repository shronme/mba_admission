"""
Labeled examples for IntentClassifier.

Each Example has:
  - message: str
  - intent: str  (intake_documents | intake_goals | admissions_general_help | off_topic)

Extends and significantly expands the three smoke-test cases in
backend/tests/test_dspy_sample_module.py.
"""
from __future__ import annotations

import dspy

_INPUT_FIELDS = ("message",)

EXAMPLES: list[dspy.Example] = [
    # -------------------------------------------------------------- intake_documents
    dspy.Example(
        message="Upload my grades and transcript. What should I do?",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="I want to share my CV with you — how do I upload it?",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Here is my recommendation letter. Can you take a look?",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="I'm trying to upload my resume but I'm not sure what format you accept.",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Should I attach my life story essay before we continue the interview?",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="My transcript from undergrad is ready. Where do I send it?",
        intent="intake_documents",
    ).with_inputs(*_INPUT_FIELDS),
    # --------------------------------------------------------------- intake_goals
    dspy.Example(
        message="What are good goals for an MBA admission?",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="I want to pivot into consulting after my MBA — does that sound realistic?",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="My goal is to launch a social enterprise in West Africa. How does that fit an MBA narrative?",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="I'm trying to figure out what my post-MBA career plan should look like.",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="How specific should my goal statement be? I have a few options I'm considering.",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Is it okay to say I want to do venture capital right after the MBA?",
        intent="intake_goals",
    ).with_inputs(*_INPUT_FIELDS),
    # -------------------------------------------------------- admissions_general_help
    dspy.Example(
        message="How do I write a great MBA essay?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="What GMAT score do I need for HBS?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Can you help me understand what the Wharton application process looks like?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="When are Round 1 deadlines for M7 schools typically?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="What makes a strong recommendation letter?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="How important is community involvement in MBA applications?",
        intent="admissions_general_help",
    ).with_inputs(*_INPUT_FIELDS),
    # ------------------------------------------------------------------- off_topic
    dspy.Example(
        message="What is the derivative of x squared?",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Can you write me a Python script to parse CSV files?",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Who won the 2023 FIFA World Cup?",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="What is photosynthesis?",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Tell me a joke.",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        message="Translate this sentence to French: 'The weather is nice today.'",
        intent="off_topic",
    ).with_inputs(*_INPUT_FIELDS),
]


def load() -> list[dspy.Example]:
    return list(EXAMPLES)
