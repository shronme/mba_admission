"""
Signature variants for IntakeInterviewer.

Variants differ in how the profile update output is constrained and whether
explicit JSON format instructions are embedded in field descriptions.
MIPROv2 will optimise the instruction text — docstrings are starting hints.

REGISTRY maps name → signature class.
DEFAULT is the name of the production-equivalent variant.
"""
from __future__ import annotations

import dspy


class IntakeInterviewerV1(dspy.Signature):
    """
    You are an experienced MBA admissions coach conducting a structured intake interview.

    CRITICAL RULE — STAY ON THE CURRENT TOPIC:
    The field `last_question_asked` tells you what you asked the candidate last turn.
    Before moving to a new topic, verify that the candidate's answer actually addresses
    that question. If the answer is off-topic or only tangentially related, acknowledge
    what they said, clarify what you were asking, and re-ask the same question.
    Only advance when the current topic has a real, specific answer.

    QUESTION GENERATION:
    - Look at `profile_gaps_json` — the ordered list of profile attributes still missing
      or insufficient. Pick the most important gap to address next.
    - Use `attribute_schema_json` to understand what good content looks like for that
      attribute, then craft a natural, conversational question that would draw out that
      information from this specific candidate.
    - The question must NOT be scripted or generic. Reference what the candidate has
      already shared. Make it feel like a real coaching conversation.
    - Ask exactly ONE question per turn.

    OTHER RULES:
    - Briefly acknowledge the candidate's answer before asking the next question.
    - Skip attributes already captured in current_profile_json.
    - If answer_classification is 'candidate_question', answer the candidate's question
      clearly and concisely first, then re-ask last_question_asked.
    - If has_files is 'false', append this reminder at the very end (new line):
      "(Tip: uploading your resume, transcripts, or any background notes will let me
      give you much more tailored guidance.)"
    - Extract concrete profile information from the candidate's answer into
      profile_updates_json. Use the attribute keys from attribute_schema_json.
      Return {} if the answer was vague or off-topic.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    last_question_asked: str = dspy.InputField(
        desc="The exact question you asked the candidate in the previous turn. Empty string on the first turn."
    )
    current_profile_json: str = dspy.InputField(
        desc="JSON object of profile attributes already captured. Keys present mean that area is covered."
    )
    profile_gaps_json: str = dspy.InputField(
        desc="JSON array of candidate-input attribute keys that are still missing or insufficient, in priority order."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping attribute keys to descriptions of what good content looks like."
    )
    conversation_history: str = dspy.InputField(
        desc="Recent conversation as alternating INTERVIEWER / CANDIDATE lines."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")
    has_files: str = dspy.InputField(
        desc="'true' if the candidate has uploaded documents, 'false' otherwise."
    )
    answer_classification: str = dspy.InputField(
        desc="One of: relevant, candidate_question. 'relevant' means the message attempted to answer the question."
    )

    response: str = dspy.OutputField(
        desc=(
            "Your reply. Acknowledge the candidate's answer, then ask a targeted question "
            "about the highest-priority gap from profile_gaps_json. If the answer did NOT "
            "address last_question_asked, redirect and re-ask the same question instead of "
            "moving on. If candidate_question: answer first, then re-ask last_question_asked."
        )
    )
    profile_updates_json: str = dspy.OutputField(
        desc=(
            "Valid JSON object of new profile key/value pairs extracted from the candidate's "
            "answer. Keys must match attribute_schema_json. Return {} if answer was vague or off-topic."
        )
    )


class IntakeInterviewerV2(dspy.Signature):
    """
    You are an MBA admissions coach conducting a structured intake interview.

    Your job each turn:
    1. Check whether the candidate's answer addresses last_question_asked.
       If not, re-ask it (don't advance to a new topic).
    2. If it does, briefly acknowledge and then ask exactly one new question
       targeting the first gap in profile_gaps_json.
    3. If answer_classification is 'candidate_question', answer their question
       first, then re-ask last_question_asked.
    4. Extract any concrete profile data into profile_updates_json as a valid
       JSON object using keys from attribute_schema_json. Use {} if nothing
       concrete was shared.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    last_question_asked: str = dspy.InputField(
        desc="The exact question from the previous turn. Empty string on turn 1."
    )
    current_profile_json: str = dspy.InputField(
        desc="JSON object of already-captured profile attributes."
    )
    profile_gaps_json: str = dspy.InputField(
        desc="Ordered JSON array of attribute keys not yet captured."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object: attribute_key → description of what good content looks like."
    )
    conversation_history: str = dspy.InputField(
        desc="Recent turns as INTERVIEWER: / CANDIDATE: lines."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")
    has_files: str = dspy.InputField(
        desc="'true' or 'false' — whether the candidate has uploaded documents."
    )
    answer_classification: str = dspy.InputField(
        desc="'relevant' or 'candidate_question'."
    )

    response: str = dspy.OutputField(
        desc=(
            "Your coaching reply: acknowledgement + single targeted question (or answer + re-ask "
            "if candidate_question). Append the document upload tip on a new line if has_files='false'."
        )
    )
    profile_updates_json: str = dspy.OutputField(
        desc=(
            "Strict JSON object. Keys must be from attribute_schema_json. "
            "Values are verbatim or lightly cleaned extracts from user_message. "
            "Return exactly {} if nothing concrete was shared."
        )
    )


REGISTRY: dict[str, type[dspy.Signature]] = {
    "v1_baseline": IntakeInterviewerV1,
    "v2_numbered_rules": IntakeInterviewerV2,
}

DEFAULT = "v1_baseline"
