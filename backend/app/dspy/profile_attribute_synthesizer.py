from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    _ATTRIBUTE_SCHEMA_JSON,
)


class SingleAttributeSynthesisSignature(dspy.Signature):
    """
    You are a senior MBA admissions consultant.

    Task:
    Synthesize ONE requested profile attribute value using the provided evidence.

    Evidence:
    - document_text: full extracted text from an uploaded document (CV, life story, etc.)
    - current_profile_json: already-known profile attributes (may be partial)
    - target_attribute_key: which attribute to produce
    - attribute_schema_json: what "good" looks like for each attribute

    Rules:
    - Use only information supported by the evidence. If uncertain, return an empty string.
    - Do NOT ask the candidate questions. Output only the attribute value text.
    - Write in clear professional English.
    - For core_identity specifically: produce 3–8 sentences and include at least 1 concrete example
      anchored in roles, scope, or achievements from the evidence.
    """

    document_text: str = dspy.InputField(desc="Full extracted text from the uploaded document.")
    document_type: str = dspy.InputField(desc="Classified document type (e.g. cv, life_story).")
    current_profile_json: str = dspy.InputField(desc="Existing profile attributes as JSON.")
    target_attribute_key: str = dspy.InputField(desc="Attribute key to synthesize (e.g. core_identity).")
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping attribute keys to descriptions of what good content looks like."
    )

    value: str = dspy.OutputField(desc="The synthesized attribute value text, or empty string if unsupported.")


class OpenAISingleAttributeSynthesizer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(SingleAttributeSynthesisSignature)

    def forward(  # type: ignore[override]
        self,
        document_text: str,
        document_type: str,
        current_profile_json: str,
        target_attribute_key: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        return self._predict(
            document_text=document_text,
            document_type=document_type,
            current_profile_json=current_profile_json,
            target_attribute_key=target_attribute_key,
            attribute_schema_json=attribute_schema_json,
        )


class MockSingleAttributeSynthesizer(dspy.Module):
    """
    Deterministic fallback synthesizer for mock mode.

    This is intentionally conservative and only produces core_identity when the
    document has clear role/seniority signals.
    """

    def forward(  # type: ignore[override]
        self,
        document_text: str,
        document_type: str,
        current_profile_json: str,
        target_attribute_key: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        key = (target_attribute_key or "").strip()
        text = (document_text or "").strip()
        low = text.lower()

        if key != "core_identity":
            return dspy.Prediction(value="")

        # Lightweight heuristics: try to infer an identity phrase from seniority/role markers.
        seniority = None
        for tok in ("vp", "vice president", "director", "head of", "principal", "lead", "manager", "founder", "cto", "ceo", "co-founder"):
            if tok in low:
                seniority = tok
                break

        if not seniority:
            return dspy.Prediction(value="")

        # Try to capture a small concrete example window.
        example = ""
        for verb in ("led", "managed", "built", "launched", "delivered", "owned", "scaled", "grew"):
            idx = low.find(verb)
            if idx >= 0:
                example = " ".join(text[max(0, idx - 80) : min(len(text), idx + 180)].split())
                break

        out = (
            "I am a high-accountability operator and builder who takes ownership end-to-end and delivers measurable outcomes. "
            f"My experience includes roles with clear leadership scope (e.g., {seniority}). "
        )
        if example:
            out += f"For example, I {example}."
        else:
            out += "I have repeatedly led cross-functional execution from ambiguity to shipped results."

        return dspy.Prediction(value=out.strip())


def run_single_attribute_synthesizer(
    *,
    document_text: str,
    document_type: str,
    current_attributes: dict | None,
    target_attribute_key: str,
    use_openai: bool = False,
) -> str:
    """
    Synthesize exactly one attribute value (best-effort).

    Returns a string (possibly empty).
    """
    from app.core.dspy_runtime import run_dspy_module

    key = (target_attribute_key or "").strip()
    if key not in set(CANDIDATE_INPUT_ATTRIBUTES):
        return ""

    current_json = json.dumps(current_attributes or {}, ensure_ascii=False)
    module: dspy.Module = (
        OpenAISingleAttributeSynthesizer() if use_openai else MockSingleAttributeSynthesizer()
    )
    pred = run_dspy_module(
        module,
        document_text=document_text or "",
        document_type=document_type or "",
        current_profile_json=current_json,
        target_attribute_key=key,
        attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON,
    )
    value = str(getattr(pred, "value", "") or "").strip()
    return value

