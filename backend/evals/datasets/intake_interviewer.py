"""
Labeled examples for IntakeInterviewer.

Each Example has all interviewer inputs plus:
  - expected_profile_keys: frozenset[str]
      Keys that should appear in profile_updates_json after the LLM processes the turn.
      An empty frozenset means we only check that profile_updates_json is valid JSON
      and that a response was generated.

The attribute_schema_json field is shared across all examples and imported from
the production module so it stays in sync.
"""
from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import _ATTRIBUTE_SCHEMA_JSON, CANDIDATE_INPUT_ATTRIBUTES

_INPUT_FIELDS = (
    "candidate_name",
    "last_question_asked",
    "current_profile_json",
    "profile_gaps_json",
    "attribute_schema_json",
    "conversation_history",
    "user_message",
    "has_files",
    "answer_classification",
)

_ALL_GAPS = json.dumps(CANDIDATE_INPUT_ATTRIBUTES)
_EMPTY_PROFILE = "{}"


def _example(
    *,
    candidate_name: str,
    last_question_asked: str,
    current_profile_json: str,
    profile_gaps_json: str,
    conversation_history: str,
    user_message: str,
    has_files: str,
    answer_classification: str,
    expected_profile_keys: frozenset[str],
) -> dspy.Example:
    return dspy.Example(
        candidate_name=candidate_name,
        last_question_asked=last_question_asked,
        current_profile_json=current_profile_json,
        profile_gaps_json=profile_gaps_json,
        attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON,
        conversation_history=conversation_history,
        user_message=user_message,
        has_files=has_files,
        answer_classification=answer_classification,
        expected_profile_keys=expected_profile_keys,
    ).with_inputs(*_INPUT_FIELDS)


EXAMPLES: list[dspy.Example] = [
    # --------------------------------------------------------- Turn 1: core_identity
    _example(
        candidate_name="Alice Johnson",
        last_question_asked="",
        current_profile_json=_EMPTY_PROFILE,
        profile_gaps_json=_ALL_GAPS,
        conversation_history="",
        user_message=(
            "I am a senior product manager at a Series B fintech startup. "
            "I've spent the last four years building payments infrastructure and "
            "leading a team of eight engineers and designers."
        ),
        has_files="false",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"core_identity"}),
    ),
    # --------------------------------------------------------- Turn 2: domain_base
    _example(
        candidate_name="Alice Johnson",
        last_question_asked="Can you tell me more about the industry and sector you work in?",
        current_profile_json=json.dumps(
            {"core_identity": "Senior PM at fintech startup, 4 years building payments infra."}
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k != "core_identity"]
        ),
        conversation_history=(
            "INTERVIEWER: Can you walk me through who you are as a professional?\n"
            "CANDIDATE: I am a senior product manager at a Series B fintech startup..."
        ),
        user_message=(
            "I work in the B2B fintech sector, specifically payments and embedded finance. "
            "My background spans both product and some engineering, primarily in North American markets."
        ),
        has_files="false",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"domain_base"}),
    ),
    # --------------------------------------------------------- Turn 3: motivation
    _example(
        candidate_name="David Park",
        last_question_asked="What is driving you to pursue an MBA right now?",
        current_profile_json=json.dumps(
            {
                "core_identity": "Operations director at MedTech company.",
                "domain_base": "Healthcare operations, APAC markets.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base"}]
        ),
        conversation_history=(
            "INTERVIEWER: What is your professional background?\n"
            "CANDIDATE: I run operations for a MedTech firm across APAC.\n"
            "INTERVIEWER: What is driving you to pursue an MBA right now?\n"
        ),
        user_message=(
            "I want to transition into strategy consulting. I've hit a ceiling in operations "
            "and I need the MBA to pivot credibly and build a broader business toolkit."
        ),
        has_files="false",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"motivation", "core_tension"}),
    ),
    # -------------------------------- candidate asks a question mid-interview
    _example(
        candidate_name="Maria Santos",
        last_question_asked="What are the main strengths you'd bring to an MBA programme?",
        current_profile_json=json.dumps(
            {
                "core_identity": "Investment banking associate, 5 years.",
                "domain_base": "Finance, M&A advisory.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base"}]
        ),
        conversation_history=(
            "INTERVIEWER: What are the main strengths you'd bring to an MBA programme?\n"
        ),
        user_message="Do I need to have my GMAT score ready before we continue?",
        has_files="false",
        answer_classification="candidate_question",
        expected_profile_keys=frozenset(),  # no profile update expected — just answer + re-ask
    ),
    # --------------------------------------------------------- Turn: core_strengths
    _example(
        candidate_name="Maria Santos",
        last_question_asked="What are the main strengths you'd bring to an MBA programme?",
        current_profile_json=json.dumps(
            {
                "core_identity": "Investment banking associate, 5 years.",
                "domain_base": "Finance, M&A advisory.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base"}]
        ),
        conversation_history=(
            "INTERVIEWER: What are the main strengths you'd bring to an MBA programme?\n"
        ),
        user_message=(
            "My key strengths are analytical rigour, stakeholder management, and the ability "
            "to translate complex financial data into executive-level narratives. I excel at "
            "building trust with C-suite clients quickly."
        ),
        has_files="false",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"core_strengths"}),
    ),
    # --------------------------------------------------------- Turn: core_tension (honest application gaps)
    _example(
        candidate_name="Tom Wright",
        last_question_asked="Where do you see the biggest tension or credibility gap in your application?",
        current_profile_json=json.dumps(
            {
                "core_identity": "Non-profit director.",
                "domain_base": "Social sector, East Africa.",
                "core_strengths": "Leadership and community organising.",
                "motivation": "MBA to scale impact through business tools.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base", "core_strengths", "motivation"}]
        ),
        conversation_history=(
            "INTERVIEWER: Where do you see the biggest tension or credibility gap in your application?\n"
        ),
        user_message=(
            "My low GPA from undergrad is a concern — I had a 2.9 due to personal circumstances "
            "in my sophomore year. I'm also missing quantitative experience which could be a gap "
            "for more finance-heavy programmes."
        ),
        has_files="true",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"core_tension"}),
    ),
    # --------------------------------------------------------- Turn: transferable_assets
    _example(
        candidate_name="Yuki Tanaka",
        last_question_asked=(
            "What skills or experiences from your current role are most transferable "
            "to your post-MBA goals?"
        ),
        current_profile_json=json.dumps(
            {
                "core_identity": "Military officer transitioning to civilian business.",
                "domain_base": "Defence and government operations.",
                "motivation": "MBA to enter management consulting.",
                "core_tension": "Pivoting from military to private sector.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base", "motivation", "core_tension"}]
        ),
        conversation_history=(
            "INTERVIEWER: What skills from your background are transferable to consulting?\n"
        ),
        user_message=(
            "I bring experience in high-stakes decision-making under uncertainty, leading diverse "
            "teams of 50+ people, and leveraging data to brief senior leadership. These skills "
            "apply directly to consulting engagements."
        ),
        has_files="true",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"transferable_assets"}),
    ),
    # ------------------------------------- vague answer — expect empty profile update
    _example(
        candidate_name="Alice Johnson",
        last_question_asked="Can you give me a specific example of your leadership impact?",
        current_profile_json=json.dumps(
            {"core_identity": "Senior PM at fintech startup."}
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k != "core_identity"]
        ),
        conversation_history=(
            "INTERVIEWER: Can you give me a specific example of your leadership impact?\n"
        ),
        user_message="I've led some teams and done various projects.",
        has_files="false",
        answer_classification="relevant",
        expected_profile_keys=frozenset(),  # too vague — no confident extraction expected
    ),
    # ------------------------------------------------- differentiation_layer
    _example(
        candidate_name="Aisha Mwangi",
        last_question_asked=(
            "Is there something in your personal background — values, community involvement, "
            "or lived experience — that shapes how you lead?"
        ),
        current_profile_json=json.dumps(
            {
                "core_identity": "Public health program manager.",
                "domain_base": "Global health, Sub-Saharan Africa.",
                "motivation": "MBA to scale health tech ventures.",
            }
        ),
        profile_gaps_json=json.dumps(
            [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base", "motivation"}]
        ),
        conversation_history=(
            "INTERVIEWER: Is there something personal that shapes how you lead?\n"
        ),
        user_message=(
            "Growing up in a rural community with no healthcare access shaped everything. "
            "Resilience, community trust, and patience are values I bring into every programme I run. "
            "I've also volunteered as a mentor for girls in STEM in my region for six years."
        ),
        has_files="true",
        answer_classification="relevant",
        expected_profile_keys=frozenset({"differentiation_layer"}),
    ),
]


def load() -> list[dspy.Example]:
    return list(EXAMPLES)
