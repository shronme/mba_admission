# AI Admissions Platform -- Product Requirements Document (PRD)

## 1. Overview

### 1.1 Product Vision

Build an AI-native admissions operating system that replaces traditional
admissions consulting workflows with a persistent, intelligent, and
structured platform.

### 1.2 Goals

-   Replace fragmented consulting workflows (email, docs, calls)
-   Provide structured candidate intelligence
-   Enable scalable, high-quality admissions guidance
-   Combine AI-first experience with optional human consultants

------------------------------------------------------------------------

## 2. Target Users

### 2.1 Graduate Applicants

-   MBA, Master's, LLM candidates
-   Short-cycle (3--12 months)
-   Need positioning, strategy, execution

### 2.2 Undergraduate Applicants

-   Students + families
-   Long-cycle (3--5 years)
-   Need development, direction, profile building

------------------------------------------------------------------------

## 3. Core Problem

Current admissions consulting is: - Unstructured - Non-scalable -
Dependent on human memory - Lacks continuity and data reuse

------------------------------------------------------------------------

## 4. Solution

A unified platform that: - Structures candidate data - Drives strategy
decisions - Guides execution - Maintains persistent memory - Integrates
AI + human consultants

------------------------------------------------------------------------

## 5. Core User Flows

### 5.1 Graduate Flow

1.  Input (CV, transcripts, goals)
2.  AI structuring
3.  Diagnosis
4.  Strategy selection (Upgrade / Pivot / Hybrid)
5.  School research
6.  Narrative creation
7.  Execution (essays, applications)
8.  Iteration

### 5.2 Undergraduate Flow

1.  Baseline assessment
2.  Exploration
3.  Filtering
4.  Direction building
5.  Activity tracking
6.  Spike development
7.  Monitoring
8.  Final positioning
9.  Execution

------------------------------------------------------------------------

## 6. Core Features

### 6.1 Chat Interface

-   Primary interaction layer
-   Accepts questions, uploads, commands
-   Drives all workflows

### 6.2 Candidate Profile Engine

-   Structured representation of user
-   Stores:
    -   academics
    -   experience
    -   activities
    -   strengths/weaknesses
    -   narrative
    -   strategy

### 6.3 Strategy Engine

-   Determines:
    -   Upgrade / Pivot / Hybrid
    -   School fit
    -   Risk level
-   Explains reasoning

### 6.4 Task Engine

-   Converts strategy into actions
-   Tracks progress

### 6.5 Essay Review Engine

-   Suggests improvements
-   Edits clarity and structure
-   Does NOT fully generate essays

### 6.6 Research Engine

-   Program and school insights
-   Candidate-specific recommendations

### 6.7 Repository

-   Stores:
    -   CVs
    -   essays
    -   transcripts
    -   documents

### 6.8 Log System

-   Tracks:
    -   decisions
    -   conversations
    -   revisions

### 6.9 Consultant Mode

-   Human consultant access
-   Shared context with AI

------------------------------------------------------------------------

## 7. Functional Requirements

### 7.1 Intake

-   Upload documents
-   Free-text input
-   Multi-language support

### 7.2 Profile Structuring

-   Extract structured data
-   Normalize inputs
-   Identify gaps

### 7.3 Strategy Recommendation

-   Provide explicit strategy type
-   Justify decisions

### 7.4 Task Generation

-   Actionable next steps
-   Prioritized

### 7.5 Essay Review

-   Feedback loops
-   Version comparison

### 7.6 Research

-   Query schools
-   Provide comparisons

### 7.7 Memory

-   Persist all interactions
-   Enable context recall

------------------------------------------------------------------------

## 8. Non-Functional Requirements

-   High availability
-   Data privacy (PII handling)
-   Low latency AI responses
-   Scalable architecture
-   Multilingual support

------------------------------------------------------------------------

## 9. System Architecture (High Level)

User → Chat → Orchestration Layer → Engines → Storage

### Components:

-   LLM Layer
-   Orchestrator
-   Profile Service
-   Strategy Service
-   Task Service
-   Essay Service
-   Research Service
-   Storage (DB + Files)

------------------------------------------------------------------------

## 10. Data Model (Simplified)

Candidate: - id - type (UG / Grad) - profile - strategy - tasks -
essays - files - chat history - logs

------------------------------------------------------------------------

## 11. Pricing

  Plan              Price         Features
  ----------------- ------------- -----------------
  Grad AI           \$100         AI only
  Grad Consultant   \$2000        AI + human
  UG AI             \$1000/year   AI system
  UG Consultant     \$5000/year   AI + consultant

------------------------------------------------------------------------

## 12. Success Metrics

-   Conversion rate
-   Retention / engagement
-   Application success rate
-   Task completion rate
-   Essay improvement score

------------------------------------------------------------------------

## 13. Risks

-   Trust in AI vs humans
-   Poor input quality
-   Over-automation
-   Outcome dependency

------------------------------------------------------------------------

## 14. Future Enhancements

-   DSPy optimization
-   Data flywheel from past candidates
-   Benchmarking engine
-   Recommendation system improvements

------------------------------------------------------------------------

## 15. Summary

This product is a structured, intelligent admissions OS that: - replaces
consultants - scales expertise - maintains long-term candidate context -
delivers strategy + execution
