# AI Admissions OS + Narrative Engine + Validation Plan

## Combined Product & Validation Specification

---

# 1. Product Definition

A persistent AI-native admissions operating system that replaces core functions of human admissions consultants.

Core capabilities:
- Structuring candidate data
- Strategic decision making
- Narrative generation
- Execution guidance
- Persistent memory
- Optional human consultant layer

---

# 2. Core System Layers

## Candidate Intelligence
Raw → Structured → Diagnosed profile

## Strategy Engine
- Strategy type: upgrade / pivot / hybrid
- Risk analysis
- School fit
- Positioning logic

## Narrative Engine (Core Experiment)
Input:
- candidate profile
- school profile
- successful examples

Output:
- narrative strategy

## Execution Engine
- essay guidance
- CV edits
- recommendations
- task tracking

## Memory System
- chat history
- decisions
- documents
- logs

## Orchestration Layer
Routes user intent to appropriate engine

---

# 3. Key Insight

The system must encode consultant decision logic:
- structuring chaos
- selecting strategy
- building narrative
- guiding execution

---

# 4. Validation Strategy

Focus ONLY on validating the narrative engine.

---

# 5. Experiment Setup

Folder structure:

experiment/
  run_experiment.py
  baseline.py
  retrieval.py
  evaluator.py
  data/
    train/
    dev/

---

# 6. Dataset Requirements

Each example must include:

{
  "candidate_structured": {},
  "school": {},
  "strategy": {
    "narrative_arc": "",
    "themes": [],
    "strengths": [],
    "risks": [],
    "school_fit": ""
  }
}

---

# 7. Experiment Design

## Baseline
candidate + school + examples → LLM → narrative

## Retrieval
- random
- same school
- similar profile

## Structured vs Raw
Compare structured vs raw input

---

# 8. Evaluation

Human evaluation (preferred):
- school fit
- differentiation
- coherence
- accuracy
- usability

Optional:
LLM judge scoring

---

# 9. Success Criteria

Success:
- expert approves output
- tailored, specific, grounded

Failure:
- generic outputs
- hallucinations
- no differentiation

---

# 10. DSPy Phase (After Validation)

1. baseline prompt
2. retrieval optimization
3. structured inputs
4. BootstrapFewShot
5. MIPROv2

---

# 11. Product Evolution

Phase 1:
- script experiment

Phase 2:
- API + narrative engine

Phase 3:
- full AI admissions OS

---

# 12. Strategic Conclusion

Business 1:
- Narrative engine (fast validation)

Business 2:
- Full admissions OS (long-term vision)

Only pursue Business 2 if Business 1 works.

---

# 13. Next Steps

1. Structure 5–10 examples
2. Build baseline script
3. Run evaluation with expert
4. Decide based on results
