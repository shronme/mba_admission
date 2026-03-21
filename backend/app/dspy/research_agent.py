from __future__ import annotations

import dspy

# ---------------------------------------------------------------------------
# DSPy module — OpenAI
# ---------------------------------------------------------------------------


class ResearchAgentSignature(dspy.Signature):
    """
    You are an MBA admissions strategist who has just completed the intake
    interview with a candidate. Their profile is now complete.

    Write a warm, professional handover message that:
    1. Acknowledges the candidate's completion of the intake process.
    2. Briefly reflects the key themes you heard in their profile (1–2 sentences).
    3. Explains what the research phase involves — school shortlisting, fit
       analysis, timeline planning, and essay strategy — in plain language.
    4. Lists 2–3 concrete next steps the candidate should expect.
    5. Ends with an encouraging, forward-looking closing sentence.

    Keep the tone warm and confident. Do not use generic filler phrases.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    profile_attributes_json: str = dspy.InputField(
        desc="Complete profile attributes as JSON. Use this to personalise the message."
    )

    response: str = dspy.OutputField(
        desc="The handover message to send to the candidate."
    )


class OpenAIResearchAgent(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(ResearchAgentSignature)

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
        profile_attributes_json: str,
    ) -> dspy.Prediction:
        return self._predict(
            candidate_name=candidate_name,
            profile_attributes_json=profile_attributes_json,
        )


# ---------------------------------------------------------------------------
# DSPy module — Mock
# ---------------------------------------------------------------------------


class MockResearchAgent(dspy.Module):
    """Deterministic handover message for mock/test mode."""

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
        profile_attributes_json: str,
    ) -> dspy.Prediction:
        name_part = f" {candidate_name}" if candidate_name and candidate_name != "Candidate" else ""
        response = (
            f"Thank you{name_part} — that completes your intake profile. "
            "You've given me a clear picture of your background, strengths, and where you want to go.\n\n"
            "I'm now handing you over to the research phase. Here's what happens next:\n\n"
            "1. **School shortlisting** — I'll identify programmes that align with your goals, "
            "profile strengths, and target outcomes, and explain why each is a strong fit.\n"
            "2. **Fit analysis** — For each school, I'll map your profile to their stated values "
            "and class composition so you know exactly how to position yourself.\n"
            "3. **Application timeline** — I'll build a personalised schedule covering test prep, "
            "recommendation requests, essay drafts, and submission deadlines.\n\n"
            "You're in great shape. Let's build something outstanding."
        )
        return dspy.Prediction(response=response)
