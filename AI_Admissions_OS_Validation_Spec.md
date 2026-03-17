# AI Admissions Operating System – Combined Product Specification

## 1. Executive Summary
This product is an AI-native admissions operating system that digitizes and scales the full workflow of admissions consulting (MBA, graduate, and undergraduate), combining structured reasoning, persistent memory, and LLM-powered narrative generation.

It replaces fragmented workflows (email, docs, calls) with a unified system that:
- Structures candidate data
- Chooses strategy (upgrade / pivot / hybrid)
- Generates narratives and essay guidance
- Tracks execution over time
- Integrates optional human consultants

---

## 2. Vision
Build a persistent, intelligent system that:
- Understands candidates deeply
- Adapts to each school’s expectations
- Maintains continuity over time
- Produces high-quality, personalized application strategies

---

## 3. Problem
Applicants struggle with:
- Translating experience into compelling narratives
- Understanding school-specific expectations
- Structuring essays
- Maintaining coherent strategy

Consultants solve this manually at high cost.

---

## 4. Solution
An AI platform that:
1. Ingests candidate data (CV, story, goals)
2. Structures and diagnoses the profile
3. Maps candidate to schools
4. Generates strategy and narrative
5. Guides execution (essays, tasks, iterations)

---

## 5. Core Product Insight
The product is NOT:
- A chatbot
- An essay generator

It IS:
- A system that structures, reasons, decides, and remembers

Core functions:
- Structuring chaos
- Making decisions
- Driving execution
- Maintaining memory

---

## 6. User Segments
### Graduate (MBA / Masters)
- Short cycle (3–12 months)
- Strategy-heavy
- Narrative positioning

### Undergraduate
- Long cycle (3–5 years)
- Development-focused
- Activity + profile building

---

## 7. User Flow

### Step 1: Input
- CV / resume
- Life story
- Goals

### Step 2: School Selection
- Select schools
- System loads profiles

### Step 3: AI Processing
- Candidate analysis
- School analysis
- Strategy generation

### Step 4: Output
- Narrative strategy
- Essay themes
- Outline

### Step 5: Iteration
- User refines inputs
- System updates outputs

---

## 8. Consultant Workflow (Modeled by AI)

### Graduate Flow
dump → structure → diagnose → research → strategy → narrative → execute → iterate

### Undergraduate Flow
assess → explore → filter → build → spike → monitor → position → execute

---

## 9. System Architecture

### Core Components
- Candidate Analyzer
- School Profiler
- Strategy Engine
- Narrative Builder (DSPy)
- Essay Engine
- Task Engine
- Profile Engine
- Storage Layer
- Orchestration Layer

---

## 10. AI Pipeline

### Candidate Analyzer
Outputs structured profile:
- Career arc
- Leadership
- Impact
- Risks

### School Profiler
Extracts:
- Values
- Essay prompts
- Fit signals

### Narrative Builder (DSPy)
Generates:
- Core arc
- Themes
- Risks
- Evidence mapping

### Essay Engine
- Outline generation
- Draft review
- Iterative refinement

---

## 11. DSPy Optimization
- Few-shot learning using 30–40 accepted cases
- BootstrapFewShot → MIPROv2
- Dataset includes candidate + strategy + outcome

---

## 12. UX Design

### Core Pillars
- Chat (main interface)
- Log (history + decisions)
- Repository (documents)

### Supporting
- Profile state
- Tasks
- Research

---

## 13. Engagement Loop
chat → analyze → store → update → generate tasks → repeat

---

## 14. Data Model (Simplified)

Candidate:
- profile_data
- academics
- activities
- narrative
- strategy
- schools
- tasks
- essays
- history

---

## 15. Pricing

Graduate:
- AI: $100
- Consultant: $2000

Undergraduate:
- AI: $1000/year
- Consultant: $5000/year

---

## 16. Evaluation Metrics
- School fit
- Specificity
- Coherence
- Differentiation
- Grounding

---

## 17. Risks
- Generic outputs
- Data quality issues
- Over-automation
- Trust vs AI

---

## 18. Strategic Positioning
This is:
A persistent, intelligent admissions operating system

Differentiators:
- Structured memory
- Decision logic
- Workflow continuity
- AI + human hybrid

---

## 19. Roadmap
Phase 1: MVP  
Phase 2: Optimization  
Phase 3: Data flywheel + human layer  

---

## 20. Final Principle
The product is not the chat.

The product is:
A system that remembers, reasons, structures, and evolves the candidate over time.
