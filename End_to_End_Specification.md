# Dao of Drugs – End-to-End Knowledge Graph Specification

**Status:** Foundational system implemented (Extract + Hydrate + Resolver v1)  
**Version:** 1.0  
**Last Updated:** Jan 2026  
**Audience:** Engineers, AI agents, technical founders, future contributors

---

## 1. Purpose & Framing

Dao of Drugs (DoD) is building a **reasoning substrate for early-stage drug development and indication expansion**.

This is **not**:

- a search engine
- a document index
- a synonym-normalization tool

This **is**:

- a system that preserves _raw truth_ from messy real-world sources
- a graph that introduces **explicit identity backbones**
- a foundation for **auditable, reversible, expert-validated reasoning**

The core insight:

> Most “AI for biotech” systems fail not because models are weak,  
> but because **identity is implicit, inconsistent, and untrusted**.

This system makes identity **explicit, versioned, and inspectable**.

---

## 2. Core Architectural Principles (Non-Negotiable)

### 2.1 Separation of Concerns

| Layer       | Responsibility                     |
| ----------- | ---------------------------------- |
| **Extract** | Read source data faithfully        |
| **Hydrate** | Materialize raw facts into a graph |
| **Resolve** | Create derived identity & meaning  |

**Hydration never infers.  
Resolution is always reversible.**

---

### 2.2 Mentions First, Concepts Second

Raw strings are **never trusted as identity**.

Instead:

- raw strings become **Mention nodes**
- canonical meaning is expressed via **Concept nodes**
- the relationship between them is explicit and status-gated

This pattern is applied consistently:

- Conditions
- Interventions
- (later) symptoms, biomarkers, phenotypes

---

### 2.3 Identity Backbones Over Strings

Stable identifiers anchor reasoning:

| Domain        | Backbone                          |
| ------------- | --------------------------------- |
| Diseases      | **MONDO**                         |
| Trials        | **NCT ID**                        |
| Targets       | **UniProt**                       |
| Interventions | **InterventionConcept (curated)** |

No reasoning is performed directly on raw strings.

---

### 2.4 Derived Knowledge Must Have Receipts

Any inferred relationship must carry:

- `run_id`
- `method`
- `status` (`proposed` / `accepted`)
- provenance (`pack_id`, `rule_id`, source)

If it cannot be audited, it cannot be trusted.

---

### 2.5 High Precision First, Recall Later

Early-stage biotech decisions punish false positives more than false negatives.

Therefore:

- deterministic matching first
- ambiguity rejected
- fuzzy logic only generates **proposals**, never acceptance

---

## 3. Source Systems & Data Domains

### 3.1 MONDO

- Disease ontology
- Stable disease identifiers
- Hierarchy, definitions, synonyms, xrefs

### 3.2 AACT (ClinicalTrials.gov)

- Clinical trials
- Conditions (dirty, sponsor-entered)
- Interventions (dirty, sponsor-entered)
- Sponsors

### 3.3 ChEMBL (v36)

- Molecules
- Synonyms
- Targets
- Mechanisms of Action
- External UniProt mapping file

**Important:**  
UniProt mappings are intentionally external to the SQLite DB.  
They are treated as **identity alignment artifacts**, not raw data.

---

## 4. Extract Layer (Source Fidelity)

### Purpose

Transform external datasets into **structured, versioned CSVs** without interpretation.

### Guarantees

- No canonicalization
- No fuzzy logic
- No assumptions of completeness
- Missing mappings preserved as missing

### Key Outputs

- `diseases.csv`
- `clinical_trials.csv`
- `intervention_mentions.csv`
- `chembl_molecules.csv`
- `chembl_synonyms.csv`
- `chembl_targets.csv`
- `chembl_moa.csv`

---

## 5. Hydrate Layer (Raw Graph Materialization)

Hydration answers:

> “What does the source data _say_?”

Not:

> “What does it _mean_?”

---

### 5.1 Core Node Types

#### Disease (from MONDO)

```text
(:Disease {
  mondo_id,
  name,
  definition,
  synonyms[],
  xrefs[]
})
```

#### ClinicalTrial (from AACT)

```text
(:ClinicalTrial {
  nct_id,
  title,
  phase,
  status
})
```

#### InterventionMention (from AACT)

```text
(:InterventionMention {
  mention,
  mention_norm,
  intervention_type,
  is_noise
})
```

These are **verbatim sponsor statements**, not drugs.

---

#### ChEMBLMolecule

```text
(:ChEMBLMolecule {
  molecule_chembl_id,
  pref_name,
  molecule_type
})
```

#### ChEMBLSynonym

```text
(:ChEMBLSynonym {
  synonym,
  synonym_norm,
  syn_type,
  source
})
```

#### ChEMBLTarget

```text
(:ChEMBLTarget {
  target_chembl_id,
  pref_name,
  uniprot_ids[]   // empty list if none
})
```

---

### 5.2 Core Relationships

```text
(Disease)-[:IS_A]->(Disease)
(ClinicalTrial)-[:HAS_CONDITION]->(Disease)        // accepted mappings only
(ClinicalTrial)-[:HAS_INTERVENTION]->(InterventionMention)
(ChEMBLMolecule)-[:HAS_MOA]->(ChEMBLTarget)
```

Hydration creates **facts only**.

---

### 5.3 Hydration Invariants

- Empty lists preferred over nulls
- No InterventionConcepts created
- No canonical meaning asserted
- Fast, idempotent, repeatable

---

## 6. Resolver Layer (Identity & Meaning)

Resolver answers:

> “What _is_ this intervention?”

Resolver output is **derived**, **auditable**, and **reversible**.

---

### 6.1 InterventionConcept (Canonical Spine)

```text
(:InterventionConcept {
  concept_id,
  preferred_name,
  concept_type   // DRUG | BIOLOGICAL | CLASS
})
```

This is the identity anchor for reasoning.

---

### 6.2 CANONICALIZES_TO (Derived)

```text
(InterventionMention)-[:CANONICALIZES_TO {
  run_id,
  pack_id,
  rule_id,
  method,
  status
}]->(InterventionConcept)
```

- Only `status="accepted"` edges are traversed by agents
- Multiple proposed edges allowed
- At most one accepted edge per mention

---

### 6.3 GROUNDED_TO (Derived)

```text
(InterventionConcept)-[:GROUNDED_TO {
  run_id,
  source,
  method,
  status
}]->(ChEMBLMolecule)
```

Grounding connects clinical identity to molecular reality.

- Unique, unambiguous matches only
- Ambiguous matches are rejected or proposed
- Auto-grounding never auto-accepts

---

### 6.4 Concept Packs (Human Truth)

Concept packs are **versioned YAML files**.

Example:

```yaml
pack_id: cytokines_v1
concepts:
  - concept_id: INTCPT:IL2
    preferred_name: Interleukin-2
    concept_type: BIOLOGICAL
    allowed_types: [BIOLOGICAL, DRUG]
    rules:
      - rule_id: IL2_EXACT_V1
        match:
          exact_norm:
            - 'il-2'
            - 'interleukin 2'
            - 'aldesleukin'
            - 'rh il 2'
```

Packs are:

- human-authored
- reviewable
- promotable
- the highest trust source of identity

---

### 6.5 Resolver Execution Modes

| Mode               | Behavior                              |
| ------------------ | ------------------------------------- |
| `--dry-run`        | No writes                             |
| `--skip-grounding` | Canonicalization only                 |
| default            | Canonicalization + proposed grounding |

All resolver writes carry `run_id`.

---

### 6.6 Token Filtering (Performance Only)

Tokens are normalized words extracted from pack synonyms.

They are used **only** to reduce candidate scans.
They **do not** affect correctness.

---

## 7. What the System Enables Today

End-to-end traversal:

```text
Disease
 ← ClinicalTrial
   ← InterventionMention
     → InterventionConcept
       → ChEMBLMolecule
         → Target (UniProt)
```

This enables:

- disease clustering by mechanism
- intervention → target reasoning
- cross-trial biological inference

All with provenance.

---

## 8. Intentionally Deferred (Explicit)

The following are **designed but not implemented**:

- Fuzzy matching for acceptance
- Embedding-based similarity
- Condition resolution beyond exact matches
- Arm-level modeling
- Automatic pack generation
- Class-level concept expansion

This avoids accidental scope creep.

---

## 9. Backlog (Designed, Not Implemented)

### 9.1 ConditionMention “Purgatory”

Preserve dirty AACT condition strings even when MONDO mapping fails.

```text
(:ConditionMention {raw, norm, source, hash})
(ClinicalTrial)-[:HAS_CONDITION_MENTION]->(ConditionMention)
(ConditionMention)-[:RESOLVES_TO {status, method, run_id}]->(Disease)
```

Rationale: never reject real trials due to ontology mismatch.

---

### 9.2 Regimen / Combination Modeling

Prevent false inference when drugs only work together.

```text
(:TrialRegimen {regimen_id, signature})
(ClinicalTrial)-[:HAS_REGIMEN]->(TrialRegimen)
(TrialRegimen)-[:USES_MENTION]->(InterventionMention)
```

Later upgrade to true AACT arm tables.

---

### 9.3 Pack Factory

Scale canonical YAMLs without losing trust.

- Deterministic drafts from exact joins
- Human promotion to accepted
- LLMs allowed only in proposal lane

---

### 9.4 Conflict Management

- Enforce one accepted canonicalization per mention
- Flag conflicts for review

---

### 9.5 Fuzzy Matching (Proposed-Only)

- Used to generate candidates
- Never auto-accepted

---

## 10. Next-Weekend Execution Plan (Concrete)

### Focus (No Scope Creep)

1. Run resolver with **two packs**:
   - IL-2 (biologic)
   - Metformin (small molecule)

2. Validate:
   - canonicalization counts
   - grounding behavior
   - rollback safety

3. Finalize **plan** (not code) for canonical YAML generation
4. Do **not** implement fuzzy matching or backlog items yet

---

## 11. Long-Term Vision

Dao of Drugs is building a system where:

> Agents reason across **biology, clinical evidence, and economics**,
> while every step remains **auditable, reversible, and human-verifiable**.

The graph is not the product.
It is the **substrate for reasoning**.

---

## 12. Final Guiding Principle

> If it can’t be explained, it can’t be trusted.
> If it can’t be rolled back, it shouldn’t be inferred.

Everything built so far honors this principle.

```

---

If you want next:
- I can generate a **VC-facing technical appendix** distilled from this
- Or a **“How an agent should reason over this graph”** spec
- Or a **checklist** for validating resolver runs next weekend

You’ve built something *real* here.
```
