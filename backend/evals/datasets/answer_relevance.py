"""
Labeled examples for AnswerRelevanceClassifier.

Each Example has:
  - last_question_asked: str
  - user_message: str
  - classification: str  (relevant | irrelevant | candidate_question)

Labels were generated using MockAnswerRelevanceClassifier as an oracle and
then manually reviewed for correctness.
"""
from __future__ import annotations

import dspy

_INPUT_FIELDS = ("last_question_asked", "user_message")

EXAMPLES: list[dspy.Example] = [
    # ------------------------------------------------------------------ relevant
    dspy.Example(
        last_question_asked="Can you walk me through your career path so far?",
        user_message=(
            "I started as a software engineer at a fintech startup, then moved into product "
            "management after three years. I've been leading a team of eight for the past two years."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What is your primary motivation for pursuing an MBA right now?",
        user_message=(
            "I want to transition from engineering into strategy consulting. The MBA will give "
            "me the business fundamentals and network I need to make that pivot credibly."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What post-MBA role are you targeting?",
        user_message=(
            "My goal is to join a top-tier management consulting firm, ideally McKinsey or BCG, "
            "focused on digital transformation projects in healthcare."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Tell me about your undergraduate degree and where you studied.",
        user_message=(
            "I did a BSc in Computer Science at the University of Toronto, graduating with a 3.8 GPA."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What professional weaknesses are you aware of?",
        user_message=(
            "I tend to be overly detail-oriented and sometimes struggle to delegate. I've been "
            "actively working on this by giving my team more autonomy on day-to-day decisions."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Why haven't you pursued an MBA sooner?",
        user_message=(
            "Honestly, I felt I needed more operational experience before the degree would be "
            "valuable. I wanted concrete impact stories to bring to the classroom."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What evidence do you have that you can succeed in your target role?",
        user_message=(
            "I led a cross-functional team that reduced customer churn by 18% over six months, "
            "which gave me confidence in my ability to drive strategic outcomes."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Describe a major professional transition you made.",
        user_message=(
            "After five years in investment banking I moved to an early-stage startup because "
            "I wanted to see how decisions translate directly into product outcomes."
        ),
        classification="relevant",
    ).with_inputs(*_INPUT_FIELDS),
    # --------------------------------------------------------------- irrelevant
    dspy.Example(
        last_question_asked="What is your primary motivation for pursuing an MBA right now?",
        user_message="Okay.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Tell me about your undergraduate degree.",
        user_message="Sure thing.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What post-MBA role are you targeting?",
        user_message="I like pizza.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Can you describe a leadership experience?",
        user_message="Nice weather today.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What are your professional weaknesses?",
        user_message="I don't know.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Why now for the MBA?",
        user_message="Hmm.",
        classification="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    # --------------------------------------------------- candidate_question
    dspy.Example(
        last_question_asked="What post-MBA role are you targeting?",
        user_message="What schools do you think I should apply to?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Tell me about your career path.",
        user_message="How long does the MBA application process typically take?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Describe your leadership style.",
        user_message="Can you explain what a good GMAT score looks like?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What are your post-MBA goals?",
        user_message="Do I need a sponsor letter from my employer?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="Walk me through a major challenge you overcame.",
        user_message="Is it okay if I upload my resume now?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        last_question_asked="What weaknesses are you aware of?",
        user_message="Will this conversation be used in my application?",
        classification="candidate_question",
    ).with_inputs(*_INPUT_FIELDS),
]


def load() -> list[dspy.Example]:
    return list(EXAMPLES)
