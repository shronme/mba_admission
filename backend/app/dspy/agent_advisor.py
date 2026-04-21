from __future__ import annotations

from collections.abc import Callable

import dspy


class AgentAdvisorSignature(dspy.Signature):
    """
    You are an MBA admissions advisor helping a specific candidate.

    CONTEXT YOU ALREADY HAVE
    - `profile_attributes_json`: structured facts the candidate provided during intake
      (work history, test scores, target programs, career goals, etc.).
    - `selected_schools_json`: the schools/programs the candidate is applying to.
    - `available_documents_json`: the list of documents the candidate has ALREADY
      uploaded. Every document listed here is indexed and retrievable through the
      `retrieve_candidate_context` tool.
    - `preloaded_document_snippets`: passages from the candidate's documents that
      were already retrieved for you using their latest message as the query. In
      most cases this is all the document context you need — read these before
      calling any tool.

    RULES
    1. NEVER ask the candidate to paste or re-send content that appears in
       `available_documents_json`. If they uploaded a "cv", you already have their
       CV.
    2. Start by reading `preloaded_document_snippets`. If it already contains what
       you need, answer directly WITHOUT calling any tool.
    3. Only call `retrieve_candidate_context` when `preloaded_document_snippets`
       is insufficient AND you can articulate what specific additional content
       you need. Call it AT MOST ONCE per turn, using a single broad query that
       covers everything you need in one shot. Do NOT re-query with refined
       wording — you will get similar results and waste time.
    4. Only ask the candidate for information that is genuinely not in their
       profile, selected schools, or documents (e.g. a new essay prompt, a target
       word count, which of their listed schools to prioritize this iteration).
    5. If the candidate has more than one selected school and hasn't specified
       which to tailor this iteration for, it IS reasonable to ask — that is not
       in any document.
    6. When you produce a concrete artifact (rewritten CV, essay draft), persist
       it with `save_artifact` and reference the returned download link in your
       response.

    Keep responses concise and focused on the next concrete step.
    """

    profile_attributes_json: str = dspy.InputField(
        desc="Candidate profile attributes as JSON."
    )
    selected_schools_json: str = dspy.InputField(
        desc="Schools the candidate is applying to as JSON."
    )
    available_documents_json: str = dspy.InputField(
        desc=(
            "JSON array of documents the candidate has already uploaded. Each item "
            "has `document_type` (e.g. 'cv', 'grade_sheet', 'recommendation_letter', "
            "'life_story') and `original_filename`. Treat every document here as "
            "content you already have access to — DO NOT ask the candidate to paste it."
        )
    )
    preloaded_document_snippets: str = dspy.InputField(
        desc=(
            "Passages from the candidate's uploaded documents, pre-retrieved using "
            "their latest message as the query. Read these FIRST. If they answer "
            "your needs, do not call any retrieval tool."
        )
    )
    conversation_history: str = dspy.InputField(
        desc="Full conversation history, newest last."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")

    response: str = dspy.OutputField(desc="The advisor's response to the candidate.")


class AgentAdvisorModule(dspy.Module):
    def __init__(self, retrieve_fn: Callable, save_artifact_fn: Callable) -> None:
        super().__init__()
        # max_iters=4: enough for (optional retrieve) + (optional save_artifact) +
        # final response, with one safety slot. Higher values let the LLM spin on
        # redundant retrieval calls and blow the client's stream timeout.
        self.react = dspy.ReAct(
            AgentAdvisorSignature,
            tools=[retrieve_fn, save_artifact_fn],
            max_iters=4,
        )

    def forward(self, **kwargs) -> dspy.Prediction:  # type: ignore[override]
        return self.react(**kwargs)

    async def aforward(self, **kwargs) -> dspy.Prediction:
        return await self.react.aforward(**kwargs)


class MockAgentAdvisorModule(dspy.Module):
    def forward(self, user_message: str, **kwargs) -> dspy.Prediction:  # type: ignore[override]
        msg = (user_message or "").lower()
        if "cv" in msg:
            return dspy.Prediction(
                response="[MOCK] Here is your improved CV.",
                artifact_id="mock-cv-artifact-id",
                artifact_type="cv_draft",
            )
        if "essay" in msg:
            return dspy.Prediction(
                response="[MOCK] Here is your essay feedback.",
                artifact_id="mock-essay-artifact-id",
                artifact_type="essay_draft",
            )
        return dspy.Prediction(response="[MOCK] How can I help you?")

    async def aforward(self, **kwargs) -> dspy.Prediction:
        return self.forward(**kwargs)
