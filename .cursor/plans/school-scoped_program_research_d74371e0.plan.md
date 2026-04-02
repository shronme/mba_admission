---
name: School-scoped program research
overview: Add a per-school LLM discovery step that filters the existing `GRAD_PROGRAM_FOCUS` taxonomy to programs actually offered at each school, then run the current dossier researcher for each (school, program) pair. Persist a school→programs catalog for intake cascading, plus JSONL RAG records derived from dossiers. Intake API/UI wiring is a separate follow-up that consumes the generated catalog.
todos:
  - id: dspy-offerings
    content: Add `school_program_offerings` DSPy module + `run_school_program_offerings` with JSON allowlist filtering
    status: completed
  - id: script-phases
    content: "Refactor `research_program_dossiers.py`: discovery phase, catalog JSON, `--skip-discovery`/`--catalog-path`, dossier loop from catalog"
    status: completed
  - id: rag-jsonl
    content: Implement dossier → JSONL RAG records + `out_dir/rag/chunks.jsonl` writer
    status: completed
  - id: test-rag-helper
    content: Unit test for RAG flatten helper with fixture dossier (no network)
    status: completed
  - id: dotenv-script
    content: Load `.env` in research script + document keys in `.env.example` (optional `--env-file`)
    status: completed
isProject: false
---

# School-scoped graduate program dossiers + RAG export

## Current behavior

`[backend/scripts/research_program_dossiers.py](backend/scripts/research_program_dossiers.py)` builds a **full Cartesian product** of `ALL_TARGET_US_SCHOOLS` × `[GRAD_PROGRAM_FOCUS_TO_TYPE](backend/app/constants/grad_program_focus.py)` keys and calls `[run_program_dossier_researcher](backend/app/dspy/program_dossier_researcher.py)` for each pair. That over-generates dossiers for combinations a school does not offer and does not produce a **school-specific program list** for the intake flow.

## Target behavior (per your scope choice)

1. **Discovery**: For each school, call a new DSPy module that, given the school name and the **allowed intake slugs** (minus undergrad / “still_deciding” / other non-dossier meta options), returns which slugs are **plausibly offered** at that institution, with a **display label** (and optional `official_program_name`) used when researching the dossier.
2. **Research**: For each discovered `(school, slug)`, call the **existing** `run_program_dossier_researcher(school, program=<label>, cycle_year=...)` so the collected JSON shape stays the same as today.
3. **Catalog artifact**: Write a single machine-readable map, e.g. `graduate_programs_by_school.json`, shaped like `{ "<school name>": [ { "slug", "label", ... }, ... ], ... }` under the run output dir (and optionally a stable path under `backend/data/` via `--catalog-out` or symlink copy) so the intake form can later **filter programs by selected school**.
4. **RAG artifact**: For each dossier JSON, emit **append-only JSONL** records (e.g. `rag/chunks.jsonl`) where each line has `text` (concatenated narrative suitable for embedding), `metadata` (`school`, `program_slug`, `program_label`, `cycle_year`, `source_file`, `section` or similar). This matches common “RAG dataset” patterns and does **not** require DB changes yet. Full pgvector ingestion can be a later phase (would need a new table or doc type; existing `[DocumentChunk](backend/app/db/models/document_chunk.py)` is tied to `candidate_id` + `file_id` for uploads only).

## Implementation outline

### 0. Environment file (no manual `export`)

The project already depends on `[python-dotenv](backend/requirements.txt)`. Update `[research_program_dossiers.py](backend/scripts/research_program_dossiers.py)` to call `load_dotenv()` **before** reading `os.getenv` / configuring DSPy:

- **Search order** (first file found wins, or merge with later overriding earlier depending on `load_dotenv` usage): resolve the **repo root** from the script path (`backend/scripts/…` → parents[2]), then try in order: `repo_root/.env`, `repo_root/backend/.env`. This matches running from repo root or `cd backend`.
- **CLI**: optional `--env-file PATH` to point at a specific file (overrides or supplements the default search for local dev).
- **Precedence**: keep current behavior that **already-set environment variables** take precedence over `.env` (`load_dotenv(override=False)`), so CI and one-off overrides still work.
- **Documentation**: add a **Program dossier research** subsection to `[.env.example](.env.example)` with commented placeholders for `PERPLEXITY_API_KEY`, `PERPLEXITY_MODEL`, `PERPLEXITY_BASE_URL`, `CYCLE_YEAR`, `PROGRAM_DOSSIER_SLEEP_SECONDS`, `PROGRAM_DOSSIER_LIMIT`, `PROGRAM_DOSSIER_OUT_DIR` (match what the script already reads). Do **not** commit real secrets.

If `.env` is not already gitignored at the repo root, consider adding it (secrets); `.env*.local` is already ignored for the web app.

### 1. New DSPy module: school × slug offerings

Add something like `backend/app/dspy/school_program_offerings.py`:

- **Signature**: inputs `school`, `candidate_slugs` (list of strings from a Python-defined allowlist), optional `cycle_year`.
- **Output**: strict JSON array of objects, e.g. `{ "slug", "label", "confidence": "high"|"medium"|"low", "notes": string | null }`, only including slugs the model believes the school offers (document in the prompt that uncertain cases should be omitted or flagged low-confidence).
- Reuse the same JSON extraction pattern as `[program_dossier_researcher._safe_json_loads](backend/app/dspy/program_dossier_researcher.py)`.
- Expose `run_school_program_offerings(...)` that uses `[run_dspy_module](backend/app/core/dspy_runtime.py)` like the dossier researcher.

**Slug allowlist for discovery**: derive from `ALLOWED_GRAD_PROGRAM_FOCUS` but **exclude** keys that are not meaningful for per-school graduate dossiers (e.g. `bs_ba_undergraduate`, `transfer_undergraduate`, `still_deciding`, etc.) — implement as a small explicit `DOSSIER_DISCOVERY_SLUGS` frozenset in the new module or next to the script to avoid drift.

### 2. Refactor `[research_program_dossiers.py](backend/scripts/research_program_dossiers.py)`

- **Phase A — discovery loop**: For each school, run the offerings module, validate returned slugs ⊆ allowlist, dedupe, write **per-school** snapshot (optional) and merge into `graduate_programs_by_school.json`. Support `**--skip-discovery`** + `**--catalog-path`** to reuse a prior catalog (for faster re-runs / dossier-only refresh).
- **Phase B — dossier loop**: Build targets from the catalog entries `(school, slug, label)` instead of `_iter_targets` over the global slug list. Keep `--limit` applying to **dossier** targets (or add `--discovery-limit` if you need to cap schools during testing).
- **Filenames**: Prefer `SchoolName__slug.json` (unchanged pattern) so existing tooling still works; ensure labels with slashes/spaces remain safe via existing `_safe_filename`.
- `**run_config.json`**: Record discovery model vs dossier model if you allow different models later; at minimum record `catalog_path`, counts per school, and excluded slugs.

### 3. RAG JSONL writer

- Add a small pure function, e.g. `_dossier_to_rag_records(dossier: dict, meta: dict) -> list[dict]`, in the script or `app/dspy/rag_export.py`:
  - Flatten or section-split: `overview`, `evaluation_criteria`, `fit_signals`, `class_profile`, etc., into separate records **or** one record per dossier with a long `text` field (section-split is better for retrieval granularity).
  - Each record: `{"id": stable_id, "text": "...", "metadata": {...}}`.
- Write to `out_dir/rag/chunks.jsonl` (and optionally `manifest.json` with row counts).

### 4. Intake integration (follow-up, not only script)

The script can **produce** `[graduate_programs_by_school.json](backend/data/…)` for the frontend to load. Productizing “school then program” requires:

- **API**: e.g. `GET /candidates/intake/graduate-programs?school=...` returning allowed slugs/labels for that school, or bundle the full map once (smaller if filtered server-side).
- **Schema**: Extend `[CandidateIntakeUpdate](backend/app/schemas/candidates.py)` / attributes to store the chosen program in a way that pairs with `target_schools` (e.g. primary school + program, or per-school program map) — **design choice** when you implement the UI.
- **Validation**: Reject `grad_program_focus` values not listed for any selected school (or for a designated primary school), using the same catalog the script generated.

No Alembic migration in this phase unless you decide to store embeddings in Postgres; the user preference is to generate migrations via Alembic autogen when that is confirmed.

## Testing / ops

- Add a **unit test** for `_dossier_to_rag_records` with a minimal fake dossier dict (no live LLM).
- Env vars: reuse `PERPLEXITY`_* for both discovery and dossier unless split (optional `PERPLEXITY_MODEL_DISCOVERY`); all loaded from `.env` via section **0** so operators are not reliant on shell `export`.

## Risk notes

- LLM “offering” detection can be wrong; the catalog should store **confidence** and be **versioned** (`generated_at`, `cycle_year`) for refresh policies.
- Even with taxonomy alignment, full school list × many slugs is still many calls; keep `--limit`, sleep, and catalog caching.

