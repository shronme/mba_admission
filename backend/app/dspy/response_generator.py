from __future__ import annotations

import dspy


class ResponseSignature(dspy.Signature):
    primary_intent = dspy.InputField()
    secondary_flags = dspy.InputField()
    requires_clarification = dspy.InputField()
    user_message = dspy.InputField()
    memory_context = dspy.InputField()
    final_answer = dspy.OutputField()


class AdmissionsResponseGenerator(dspy.Module):
    """
    Minimal response-generation DSPy module.

    This is deterministic for now (no LLM), but it demonstrates the intended
    DSPy-based "Response Generation" stage.
    """

    def forward(  # type: ignore[override]
        self,
        primary_intent: str,
        secondary_flags: list[str],
        requires_clarification: bool,
        user_message: str,
        memory_context: str,
    ) -> dspy.Prediction:
        if "disallowed_full_essay" in secondary_flags:
            final_answer = (
                "I can help you brainstorm, outline, and improve your draft, but I can’t write a full essay for you. "
                "Paste the prompt and share a few bullet points from your own story, and I’ll help shape a strong outline."
            )
        elif primary_intent == "off_topic":
            final_answer = (
                "I can only help with graduate admissions (documents, goals, school strategy, and essay planning). "
                "Tell me what program/cycle you’re targeting and what documents you have."
            )
        elif primary_intent == "intake_docs" or "needs_doc_upload" in secondary_flags:
            final_answer = (
                "Great — to get started, please upload any relevant documents you have (life story notes, grades/transcripts, resume, "
                "recommendations, or anything that shows your background). After uploading, tell me your top US grad goals: "
                "which schools (or types), your target timeline/round, and the main story you want to be known for."
            )
        elif primary_intent == "intake_goals" or "needs_goals_clarification" in secondary_flags:
            final_answer = (
                "Thanks for the documents. Now, tell me your Grad school goals for a top US university:\n"
                "1) Target schools (or program type + names)\n"
                "2) Your timeline (application cycle and preferred round)\n"
                "3) 2-3 themes you want your application to communicate\n"
                "4) Any constraints (work schedule, GPA range, test plan)\n\n"
                "Then I’ll propose a personalized roadmap and next steps."
            )
        else:
            final_answer = (
                "I can help with admissions planning. If you share what documents you uploaded and your target schools/timeline, "
                "I’ll suggest the next steps and what to prepare for each stage."
            )

        if requires_clarification:
            final_answer += "\n\nQuick clarifying question: what’s your preferred application round (e.g., Round 1/2) and any hard constraints?"

        return dspy.Prediction(
            primary_intent=primary_intent,
            final_answer=final_answer,
        )

