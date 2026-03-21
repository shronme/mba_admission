"""
Labeled examples for ProfileAgent (ProfileCompletenessSignature).

Each Example has:
  - profile_attributes_json: str   — the current profile as a JSON object
  - attribute_schema_json: str     — fixed schema (imported from production module)
  - expected_is_complete: str      — "true" or "false"
  - expected_gaps: frozenset[str]  — attribute keys the agent should flag as missing/thin
  - expected_score_range: tuple    — (min, max) acceptable completeness_score integers

The `expected_gaps` and `expected_score_range` are intentionally lenient to
accommodate genuine model judgement on borderline "thin content" cases.
"""
from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    SYNTHESIZED_ATTRIBUTES,
    _ATTRIBUTE_SCHEMA_JSON,
)

_INPUT_FIELDS = ("profile_attributes_json", "attribute_schema_json")

_RICH_CORE_IDENTITY = (
    "Senior product manager with 6 years building fintech infrastructure at scale. "
    "Known for translating ambiguous market signals into concrete product roadmaps "
    "that engineering teams actually believe in."
)
_RICH_DOMAIN_BASE = (
    "B2B fintech, embedded payments, and open banking across North American markets. "
    "Functional background spans product management, some engineering, and commercial strategy. "
    "Mid-senior level with P&L exposure of $8M ARR product line."
)
_RICH_CORE_STRENGTHS = (
    "1. Cross-functional alignment: built consensus across eng, design, sales and compliance "
    "on a regulatory-constrained product redesign that shipped 6 weeks ahead of schedule. "
    "2. Data-driven prioritisation: introduced an impact-vs-effort scoring framework adopted "
    "across four product teams. "
    "3. Stakeholder trust: retained two enterprise clients worth $2.4M ARR through a major "
    "platform migration by proactive co-design."
)
_RICH_DIFFERENTIATION = (
    "First-generation university student from a working-class immigrant family. "
    "Spent three years volunteering with a financial literacy programme for newcomers, "
    "which directly influenced my decision to focus on inclusive fintech. "
    "Resilience under resource constraints is a core part of how I operate."
)
_RICH_INTELLECTUAL = (
    "Systematic and evidence-driven. Defaults to structured frameworks (e.g. JTBD, "
    "decision trees) but actively pressure-tests them against edge cases. "
    "Comfortable with ambiguity — will make a 70% confidence call rather than wait "
    "for perfect information when the cost of delay is high."
)
_RICH_MOTIVATION = (
    "The MBA is the bridge between where I am (strong individual contributor in fintech) "
    "and where I want to go (building and scaling inclusive financial products across "
    "emerging markets, where the infrastructure gap is massive). "
    "I need both the strategic toolkit and the network the MBA opens up. "
    "I'm applying now because I've hit the ceiling of what I can learn in my current role."
)
_RICH_CORE_TENSION = (
    "Transition from a specialist fintech PM role to a generalist operator / founder "
    "who can run a business across markets I haven't yet worked in. "
    "The risk is clear: I lack direct experience in emerging markets and have never "
    "managed a P&L above $10M."
)
_RICH_TRANSFERABLE = (
    "Deep technical fluency with API-first product design (directly transferable to "
    "infrastructure-led startups). Stakeholder management at the C-suite level. "
    "Experience shipping regulated products under tight timelines — a rare skill in "
    "early-stage environments. Community credibility in fintech circles through "
    "conference speaking and open-source contributions."
)
_RICH_RISKS = (
    "GPA of 3.1 from undergrad (engineering programme at a target school — context helps). "
    "No international work experience yet, which matters for the emerging-market narrative. "
    "Limited quant background relative to finance-track applicants — will need to "
    "address this in essays and potentially via a pre-MBA quant course."
)


def _ex(
    profile: dict,
    *,
    expected_is_complete: str,
    expected_gaps: frozenset[str],
    expected_score_range: tuple[int, int],
) -> dspy.Example:
    return dspy.Example(
        profile_attributes_json=json.dumps(profile, ensure_ascii=False),
        attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON,
        expected_is_complete=expected_is_complete,
        expected_gaps=expected_gaps,
        expected_score_range=expected_score_range,
    ).with_inputs(*_INPUT_FIELDS)


EXAMPLES: list[dspy.Example] = [
    # ---------------------------------------------------------------- empty profile
    _ex(
        {},
        expected_is_complete="false",
        expected_gaps=frozenset(CANDIDATE_INPUT_ATTRIBUTES),
        expected_score_range=(0, 5),
    ),
    # ------------------------------------------ only core_identity filled (one line)
    _ex(
        {"core_identity": "I am a product manager."},
        expected_is_complete="false",
        expected_gaps=frozenset(k for k in CANDIDATE_INPUT_ATTRIBUTES if k != "core_identity"),
        expected_score_range=(0, 15),
    ),
    # -------------------------------------------------- two attributes, thin content
    _ex(
        {
            "core_identity": "Engineer turned PM.",
            "domain_base": "Fintech.",
        },
        expected_is_complete="false",
        expected_gaps=frozenset(k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in {"core_identity", "domain_base"}),
        expected_score_range=(0, 20),
    ),
    # ---------------------------------------- five attributes, mix of rich and thin
    _ex(
        {
            "core_identity": _RICH_CORE_IDENTITY,
            "domain_base": _RICH_DOMAIN_BASE,
            "motivation": "I want an MBA.",          # thin
            "core_tension": "I need to switch fields.",  # thin
            "core_strengths": _RICH_CORE_STRENGTHS,
        },
        expected_is_complete="false",
        expected_gaps=frozenset({
            "differentiation_layer",
            "intellectual_working_style",
            "transferable_assets",
            "risks",
            "motivation",
            "core_tension",
        }),
        expected_score_range=(20, 50),
    ),
    # ------------------------------------------ all 9 present but 2 are very thin
    _ex(
        {
            "core_identity": _RICH_CORE_IDENTITY,
            "domain_base": _RICH_DOMAIN_BASE,
            "core_strengths": _RICH_CORE_STRENGTHS,
            "differentiation_layer": _RICH_DIFFERENTIATION,
            "intellectual_working_style": _RICH_INTELLECTUAL,
            "motivation": _RICH_MOTIVATION,
            "core_tension": _RICH_CORE_TENSION,
            "transferable_assets": "I have transferable skills.",   # thin
            "risks": "Low GPA.",                                     # thin
        },
        expected_is_complete="false",
        expected_gaps=frozenset({"transferable_assets", "risks"}),
        expected_score_range=(50, 80),
    ),
    # --------------------------------------- missing only one attribute (risks)
    _ex(
        {
            "core_identity": _RICH_CORE_IDENTITY,
            "domain_base": _RICH_DOMAIN_BASE,
            "core_strengths": _RICH_CORE_STRENGTHS,
            "differentiation_layer": _RICH_DIFFERENTIATION,
            "intellectual_working_style": _RICH_INTELLECTUAL,
            "motivation": _RICH_MOTIVATION,
            "core_tension": _RICH_CORE_TENSION,
            "transferable_assets": _RICH_TRANSFERABLE,
        },
        expected_is_complete="false",
        expected_gaps=frozenset({"risks"}),
        expected_score_range=(65, 92),
    ),
    # -------------------------------------------- complete profile (all 9 rich)
    _ex(
        {
            "core_identity": _RICH_CORE_IDENTITY,
            "domain_base": _RICH_DOMAIN_BASE,
            "core_strengths": _RICH_CORE_STRENGTHS,
            "differentiation_layer": _RICH_DIFFERENTIATION,
            "intellectual_working_style": _RICH_INTELLECTUAL,
            "motivation": _RICH_MOTIVATION,
            "core_tension": _RICH_CORE_TENSION,
            "transferable_assets": _RICH_TRANSFERABLE,
            "risks": _RICH_RISKS,
        },
        expected_is_complete="true",
        expected_gaps=frozenset(),
        expected_score_range=(80, 100),
    ),
    # ------------------------------------------------ complete military-pivot profile
    _ex(
        {
            "core_identity": (
                "Army officer with 8 years leading multi-disciplinary teams in high-stakes "
                "operational environments. Transitioning to the private sector with a clear "
                "mandate: build organisations that run as precisely as a well-executed mission."
            ),
            "domain_base": (
                "Defence and government operations. Functional depth in logistics, resource "
                "allocation, and cross-agency coordination. No private-sector experience yet — "
                "intentional transition."
            ),
            "core_strengths": (
                "1. Leading under pressure: commanded a 60-person unit across three deployments. "
                "2. Systems thinking: redesigned a supply chain process that reduced delays by 40%. "
                "3. People development: 12 direct reports received accelerated promotions."
            ),
            "differentiation_layer": (
                "Combat veteran with two overseas tours. The discipline, composure, and moral "
                "clarity that military service demands is deeply embedded in how I make decisions "
                "and how I lead. I've navigated genuinely life-or-death trade-offs — business "
                "complexity is a different register of the same skill."
            ),
            "intellectual_working_style": (
                "Mission-planning mindset: define objective → identify constraints → allocate "
                "resources → execute → debrief. Very comfortable with structured uncertainty. "
                "Data-literate; ran operational analytics for brigade-level planning."
            ),
            "motivation": (
                "I'm applying now because I've reached the natural end of what uniformed service "
                "can teach me, and I want to build something in the private sector — specifically "
                "in defence tech or supply-chain resilience — where my operational credibility "
                "is an asset, not a liability. The MBA is the fastest credible path to getting "
                "a foot in the door with the operators and investors who matter."
            ),
            "core_tension": (
                "Civilian employers don't naturally translate military experience into business "
                "value. I need the MBA to build a bridge — but I also risk being typecast as "
                "a 'leadership candidate' without analytical credibility. I'm working on this."
            ),
            "transferable_assets": (
                "Operational rigour, decision-making under ambiguity, talent development, "
                "and a security clearance that gives me access to government-adjacent "
                "commercial opportunities. Strong ability to build trust with people from "
                "very different backgrounds."
            ),
            "risks": (
                "No MBA-track professional experience (consulting, banking, PE). Low quant "
                "signal — no finance or analytical roles on record. GRE taken 3 years ago "
                "(strong verbal, adequate quant). Will need to address the 'why not a "
                "government/defence think-tank' question in essays."
            ),
        },
        expected_is_complete="true",
        expected_gaps=frozenset(),
        expected_score_range=(80, 100),
    ),
]


def load() -> list[dspy.Example]:
    return list(EXAMPLES)
