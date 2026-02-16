Below is a **cleaned, de-duplicated, V1.0 “complete agent instructions”** for **IL2 + Alzheimer deep-dive (NOT expansion)**, updated to reflect the **bridges and traversals you actually validated**:

- **BioLink:** `HGNC:6001 (IL2)` ↔ `PR:P60568 (IL-2 protein)` via `ENCODES_PROTEIN` ✅
- **ChEMBL:** `CHEMBL1201438 (Aldesleukin)` targets **IL-2 receptor complex** (`CHEMBL2364167`) whose **components** map to **receptor subunit proteins** (`PR:P01589/PR:P14784/PR:P31785`) via `CHEMBL_COMPONENT_SEQUENCE -> ALIGNS_TO_TARGET -> Target -> ALIGNS_TO_PROTEIN -> BIOLINK_PROTEIN` ✅
- **AACT:** your graph has `ClinicalTrialRaw`, `ConditionMention`, `StudyReferenceRaw`, `Publication`, and `StudyReferenceRaw-[:PUBMED_ARTICLE]->Publication` ✅
- **Important reality:** Aldesleukin **does NOT traverse to IL2 ligand protein (P60568)** in your current ChEMBL mechanism path; it traverses to **receptor subunits**. That’s correct biologically and consistent with your observed component uniprots.

---

# Agent Instructions (V1.0 Stable): IL2 + Alzheimer Deep-Dive

## 0) Background & Goal (give this to the agent)

You are an external LLM agent with access to Neo4j (MCP). Your job is to produce a **graph-grounded deep-dive report** assessing whether there is “a there there” for **IL-2 biology** in **Alzheimer’s disease**, using deterministic traversals and explicit evidence paths.

**Scope:** This is **NOT** indication expansion. Assume Alzheimer is already selected as a candidate. Your job is to **double-click** into:

- **Biological rationale** (mechanism, pathways/processes, receptor biology, immune context)
- **Disease anchoring** (MONDO Alzheimer root + descendants)
- **Evidence** in-graph: genetics edges (if any), ChEMBL mechanism edges, AACT trials + PubMed references
- **Gaps**: where graph cannot support a claim deterministically

You must:

- Prefer **graph evidence** over “LLM intuition”
- Be explicit about **expected empty** checks (and what emptiness means)
- Use **fallback traversals** when primary paths are absent
- Use **mechanistic trial-selection constraints** (below) so AACT evidence doesn’t drift into irrelevant behavioral/registry trials

---

## 1) Output Requirements (what you must produce)

Produce a report with these sections:

1. **Anchors (Deterministic IDs)**
   - IL2 gene: `HGNC:6001`
   - Alzheimer root disease: `MONDO:0004975`
   - IL2 protein: `PR:P60568` (via `ENCODES_PROTEIN`)
   - ChEMBL drug anchor: `CHEMBL1201438` (Aldesleukin)
   - ChEMBL mechanism target: IL-2 receptor complex `CHEMBL2364167`
   - Receptor subunit proteins (UniProt): `P01589, P14784, P31785` (from the complex)

2. **Graph Evidence Summary**
   - What direct BioLink IL2→Disease exists (if any) — **expected empty**
   - What Alzheimer genetics exist (BioLink gene associations in Alzheimer subtree)
   - What mechanistic neighborhood exists for IL2 (pathways/processes/molecular activity)
   - What drug mechanism exists (Aldesleukin → receptor complex → subunits)
   - What AACT trial evidence exists under mechanistic constraints
   - What PubMed evidence is linked (trial references + citations + PMIDs)

3. **Interpretation Rules**
   - Never claim a direct IL2→Alzheimer association unless a direct edge exists.
   - If IL2 doesn’t connect directly, pivot to:
     - receptor subunits (IL2RA/IL2RB/IL2RG)
     - downstream pathways/processes
     - Alzheimer genetics overlap with interactors / receptor subunit disease edges

   - Trials must be constrained mechanistically (see below); if none exist, say so.

4. **Gaps & Fix List**
   - Missing edges or missing canonical joins (e.g., receptor subunit proteins lacking gene encoding edges except IL2)
   - Missing AACT property names in query pack (fix by preflight introspection queries)
   - Any missing ChEMBL → BioLink alignments beyond the receptor path

---

## 2) Mechanistic Trial-Selection Constraint (must implement)

AACT has many Alzheimer trials that are **behavioral / registry / imaging** and will weaken mechanistic reasoning.

**Therefore, only treat an Alzheimer trial as mechanistically relevant if:**

- `ClinicalTrialRaw.study_type = 'INTERVENTIONAL'`, **AND**
- It has **Phase** populated OR drug-like intervention evidence (see below), **AND**
- It contains an **IL-2 axis intervention** OR **immune-modulating intervention** plausibly tied to IL2 signaling (priority list), **AND**
- It has at least one PubMed-linked reference OR posted results (if available in your graph)

**IL-2 axis intervention keyword set (start strict):**

- `aldesleukin`, `IL-2`, `interleukin 2`, `bempegaldesleukin`, `NKTR-214`, `rezpegaldesleukin`, `pegilodecakin` (if relevant), `IL2RA`, `CD25`, `IL2RB`, `IL2RG`

If strict filter yields **0 Alzheimer trials**, relax in this order:

1. keep “INTERVENTIONAL” but allow immune interventions (checkpoint / Treg / cytokine axis)
2. allow “not Alzheimer-only” if Alzheimer appears in ConditionMention and the intervention is IL-2 axis (rare)
3. if still 0, conclude: **no mechanistically anchored IL-2 trials in Alzheimer in this graph snapshot** and use PubMed mechanistic literature instead.

---

## 3) Execution Instructions

1. Run the query pack below **in order**.
2. For any query marked **EXPECTED EMPTY**, emptiness is an output you must report, not “fix” in narrative.
3. For AACT “payload” queries, first run the **AACT property introspection** queries to avoid property-name mismatches.
4. Do bounded traversals only—avoid `[*]` expansions unless explicitly constrained.

---

# 4) IL2 + Alzheimer Deep-Dive Query Pack (single block; comment per query)

```cypher
// Q0 — Sanity: required labels exist (BioLink + ChEMBL + AACT core)
UNWIND ['BIOLINK_GENE','BIOLINK_DISEASE','BIOLINK_PROTEIN',
        'CHEMBL_MOLECULE','CHEMBL_TARGET','CHEMBL_COMPONENT_SEQUENCE','Target',
        'ClinicalTrialRaw','ConditionMention','StudyReferenceRaw','Publication',
        'ResultGroupRaw','AdverseEventRaw','OutcomeRaw','OutcomeMeasurementRaw'] AS L
CALL {
  WITH L
  MATCH (n) WHERE L IN labels(n)
  RETURN count(n) AS c
}
RETURN L AS label, c AS nodes
ORDER BY nodes DESC, label ASC;

// Q1 — Anchor: IL2 gene (human, deterministic)
MATCH (g:BIOLINK_GENE {id:'HGNC:6001'})
RETURN g.id, g.symbol, g.full_name, g.in_taxon, g.provided_by;

// Q2 — Anchor: Alzheimer root disease (deterministic)
MATCH (d:BIOLINK_DISEASE {id:'MONDO:0004975'})
RETURN d.id, d.name;

// Q3 — Directionality check for BIOLINK_SUBCLASS_OF (disease taxonomy orientation)
MATCH (child:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF]->(parent:BIOLINK_DISEASE)
RETURN 'child_to_parent' AS direction, count(*) AS edges
UNION ALL
MATCH (parent:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF]->(child:BIOLINK_DISEASE)
RETURN 'parent_to_child' AS direction, count(*) AS edges;

// Q4 — Alzheimer descendants: build Alzheimer family set (child -> parent direction)
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (child:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
RETURN count(DISTINCT child) AS n_alz_family, collect(DISTINCT child.id)[0..25] AS example_ids;

// Q5 — Alzheimer family nodes for inspection (names)
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (child:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
RETURN child.id, child.name
ORDER BY child.id
LIMIT 50;

// Q6 — Alzheimer genetics ground truth: which genes associate to Alzheimer-family diseases
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (d:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
MATCH (g:BIOLINK_GENE)-[:BIOLINK_GENE_ASSOCIATED_WITH_CONDITION]->(d)
RETURN d.id AS mondo_id, d.name AS disease_name, count(DISTINCT g) AS n_genes
ORDER BY n_genes DESC
LIMIT 50;

// Q7 — EXPECTED EMPTY CHECK: IL2 direct gene→disease edges at all (any disease)
MATCH (g:BIOLINK_GENE {id:'HGNC:6001'})-[r]->(d:BIOLINK_DISEASE)
RETURN type(r) AS rel, count(*) AS edges
ORDER BY edges DESC;

// Q8 — EXPECTED EMPTY CHECK: IL2 direct gene→Alzheimer-family disease edges
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (d:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
MATCH (g:BIOLINK_GENE {id:'HGNC:6001'})-[r]->(d)
RETURN type(r) AS rel, d.id AS mondo_id, d.name AS disease_name, count(*) AS evidence
ORDER BY evidence DESC;

// Q9 — BioLink fallback: IL2 → interacting genes → diseases (rank by # supporting interactors)
MATCH (il2:BIOLINK_GENE {id:'HGNC:6001'})
MATCH (il2)-[:BIOLINK_INTERACTS_WITH]->(g2:BIOLINK_GENE)
MATCH (g2)-[:BIOLINK_GENE_ASSOCIATED_WITH_CONDITION]->(d:BIOLINK_DISEASE)
RETURN d.name AS disease, count(DISTINCT g2) AS n_supporting_genes, collect(DISTINCT g2.symbol)[0..25] AS examples
ORDER BY n_supporting_genes DESC
LIMIT 50;

// Q10 — Alzheimer-scoped version of fallback: IL2 → interactors → Alzheimer-family diseases
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (d:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
MATCH (il2:BIOLINK_GENE {id:'HGNC:6001'})
MATCH (il2)-[:BIOLINK_INTERACTS_WITH]->(g2:BIOLINK_GENE)
MATCH (g2)-[:BIOLINK_GENE_ASSOCIATED_WITH_CONDITION]->(d)
RETURN d.id AS mondo_id, d.name AS disease, count(DISTINCT g2) AS n_supporting_genes, collect(DISTINCT g2.symbol)[0..25] AS examples
ORDER BY n_supporting_genes DESC;

// Q11 — IL2 mechanistic neighborhood: pathways
MATCH (il2:BIOLINK_GENE {id:'HGNC:6001'})-[:BIOLINK_PARTICIPATES_IN]->(pw:BIOLINK_PATHWAY)
RETURN pw.name AS pathway, count(*) AS edges
ORDER BY edges DESC
LIMIT 50;

// Q12 — IL2 mechanistic neighborhood: biological processes (two common rels)
MATCH (il2:BIOLINK_GENE {id:'HGNC:6001'})-[:BIOLINK_ACTIVELY_INVOLVED_IN]->(bp:BIOLINK_BIOLOGICALPROCESS)
RETURN bp.name AS bio_process, count(*) AS edges
ORDER BY edges DESC
LIMIT 50;

// Q13 — ChEMBL anchor: Aldesleukin mechanism target (prove what drug acts on)
MATCH (m:CHEMBL_MOLECULE {chembl_id:'CHEMBL1201438'})-[:CHEMBL_MECHANISM_ON_TARGET]->(ct:CHEMBL_TARGET)
RETURN m.chembl_id, m.pref_name, ct.target_chembl_id, ct.pref_name, ct.target_type, ct.tax_id;

// Q14 — Aldesleukin target components: UniProt accessions of receptor subunits
MATCH (m:CHEMBL_MOLECULE {chembl_id:'CHEMBL1201438'})-[:CHEMBL_MECHANISM_ON_TARGET]->(ct:CHEMBL_TARGET)
MATCH (ct)-[:CHEMBL_TARGET_HAS_COMPONENT]-(cs:CHEMBL_COMPONENT_SEQUENCE)
RETURN ct.target_chembl_id, ct.pref_name, cs.uniprot_accession AS component_uniprot, cs.component_id
ORDER BY component_uniprot
LIMIT 100;

// Q15 — Drug → BioLink proteins via ALIGNS_TO_TARGET + ALIGNS_TO_PROTEIN (should yield 3 receptor subunits)
MATCH (m:CHEMBL_MOLECULE {chembl_id:'CHEMBL1201438'})-[:CHEMBL_MECHANISM_ON_TARGET]->(ct:CHEMBL_TARGET)
MATCH (ct)-[:CHEMBL_TARGET_HAS_COMPONENT]-(cs:CHEMBL_COMPONENT_SEQUENCE)
MATCH (cs)-[:ALIGNS_TO_TARGET]->(t:Target)
MATCH (t)-[:ALIGNS_TO_PROTEIN]->(p:BIOLINK_PROTEIN)
RETURN DISTINCT
  m.chembl_id, m.pref_name,
  ct.target_chembl_id, ct.pref_name,
  cs.uniprot_accession AS component_uniprot,
  p.id AS protein_id, p.name AS protein_name
ORDER BY component_uniprot;

// Q16 — EXPECTED EMPTY CHECK: prove drug mechanism does NOT traverse to IL2 ligand protein (P60568)
MATCH (m:CHEMBL_MOLECULE {chembl_id:'CHEMBL1201438'})-[:CHEMBL_MECHANISM_ON_TARGET]->(ct:CHEMBL_TARGET)
MATCH (ct)-[:CHEMBL_TARGET_HAS_COMPONENT]-(cs:CHEMBL_COMPONENT_SEQUENCE)
MATCH (cs)-[:ALIGNS_TO_TARGET]->(t:Target)
MATCH (t)-[:ALIGNS_TO_PROTEIN]->(p:BIOLINK_PROTEIN)
WHERE p.uniprot_id = 'P60568'
RETURN count(*) AS n_paths_to_il2_ligand_protein;

// Q17 — Deterministic receptor subunit gene anchors (human)
MATCH (g:BIOLINK_GENE)
WHERE (g.in_taxon = 'NCBITaxon:9606' OR g.in_taxon_label = 'NCBITaxon:9606')
  AND toUpper(g.symbol) IN ['IL2RA','IL2RB','IL2RG']
RETURN g.symbol, g.id, g.provided_by
ORDER BY g.symbol;

// Q18 — Receptor subunit genes → diseases (this is your drug→mechanism→disease bridge)
MATCH (g:BIOLINK_GENE)
WHERE g.id IN ['HGNC:6008','HGNC:6009','HGNC:6010']
MATCH (g)-[:BIOLINK_GENE_ASSOCIATED_WITH_CONDITION]->(d:BIOLINK_DISEASE)
RETURN g.symbol AS receptor_gene, d.name AS disease, count(*) AS evidence
ORDER BY evidence DESC
LIMIT 100;

// Q19 — Receptor subunit genes → Alzheimer-family diseases (may be sparse; report emptiness)
MATCH (parent:BIOLINK_DISEASE {id:'MONDO:0004975'})
MATCH (d:BIOLINK_DISEASE)-[:BIOLINK_SUBCLASS_OF*0..]->(parent)
MATCH (g:BIOLINK_GENE)
WHERE g.id IN ['HGNC:6008','HGNC:6009','HGNC:6010']
MATCH (g)-[:BIOLINK_GENE_ASSOCIATED_WITH_CONDITION]->(d)
RETURN g.symbol AS receptor_gene, d.id AS mondo_id, d.name AS disease, count(*) AS evidence
ORDER BY evidence DESC;

// Q20 — AACT cohort discovery: Alzheimer-ish trials by ConditionMention (broad)
MATCH (t:ClinicalTrialRaw)-[:HAS_CONDITION_MENTION]->(cm:ConditionMention)
WHERE toLower(cm.name) CONTAINS 'alzheimer'
WITH t, count(DISTINCT cm) AS n_condition_mentions
RETURN t.nct_id AS nct_id, n_condition_mentions
ORDER BY n_condition_mentions DESC
LIMIT 50;

// Q21 — Mechanistic trial selection (strict): Alzheimer ConditionMention + intervention mentions include IL2-axis keywords
MATCH (t:ClinicalTrialRaw)-[:HAS_CONDITION_MENTION]->(cm:ConditionMention)
WHERE toLower(cm.name) CONTAINS 'alzheimer'
MATCH (t)-[:HAS_INTERVENTION_MENTION]->(im:InterventionMention)
WHERE toLower(im.name) CONTAINS 'interleukin 2'
   OR toLower(im.name) CONTAINS 'il-2'
   OR toLower(im.name) CONTAINS 'il2'
   OR toLower(im.name) CONTAINS 'aldesleukin'
   OR toLower(im.name) CONTAINS 'bempegaldesleukin'
   OR toLower(im.name) CONTAINS 'nktr-214'
   OR toLower(im.name) CONTAINS 'rezpegaldesleukin'
WITH t, collect(DISTINCT im.name)[0..25] AS intervention_hits
RETURN t.nct_id AS nct_id, t.study_type AS study_type, t.phase AS phase, t.overall_status AS overall_status, t.enrollment AS enrollment, intervention_hits, t.brief_title AS brief_title
ORDER BY enrollment DESC
LIMIT 50;

// Q22 — Mechanistic trial selection (guardrail): keep only interventional trials (if Q21 is too strict, relax keywords but keep this)
MATCH (t:ClinicalTrialRaw)-[:HAS_CONDITION_MENTION]->(cm:ConditionMention)
WHERE toLower(cm.name) CONTAINS 'alzheimer'
  AND t.study_type = 'INTERVENTIONAL'
RETURN t.nct_id, t.phase, t.overall_status, t.enrollment, t.brief_title
ORDER BY t.enrollment DESC
LIMIT 50;

// Q23 — Trial → PubMed evidence: count PMIDs per trial (Alzheimer ConditionMention)
MATCH (t:ClinicalTrialRaw)-[:HAS_CONDITION_MENTION]->(cm:ConditionMention)
WHERE toLower(cm.name) CONTAINS 'alzheimer'
MATCH (t)-[:HAS_REFERENCE]->(sr:StudyReferenceRaw)
WHERE sr.pmid IS NOT NULL
RETURN t.nct_id AS nct_id, count(DISTINCT sr.pmid) AS n_pmids
ORDER BY n_pmids DESC
LIMIT 50;

// Q24 — Trial deep-dive anchor (parameterize): references with citations (preferred over Publication.title in your graph)
MATCH (t:ClinicalTrialRaw {nct_id:'$NCT_ID'})
MATCH (t)-[:HAS_REFERENCE]->(sr:StudyReferenceRaw)
WHERE sr.pmid IS NOT NULL
RETURN t.nct_id AS nct_id, sr.pmid AS pmid, sr.citation AS citation
ORDER BY pmid;

// Q25 — Publication node check (title may be null; still validate node exists)
MATCH (t:ClinicalTrialRaw {nct_id:'$NCT_ID'})
MATCH (t)-[:HAS_REFERENCE]->(sr:StudyReferenceRaw)
MATCH (sr)-[:PUBMED_ARTICLE]->(p:Publication)
RETURN p.pmid AS pmid, p.title AS title
LIMIT 50;

// Q26 — AACT payload preflight: discover AdverseEventRaw property keys (fix querypack fields deterministically)
MATCH (t:ClinicalTrialRaw {nct_id:'$NCT_ID'})-[:HAS_RESULT_GROUP]->(rg:ResultGroupRaw)
MATCH (rg)-[:HAS_ADVERSE_EVENT]->(ae:AdverseEventRaw)
RETURN keys(ae) AS adverse_event_keys
LIMIT 1;

// Q27 — AACT payload preflight: discover OutcomeMeasurementRaw property keys
MATCH (t:ClinicalTrialRaw {nct_id:'$NCT_ID'})-[:HAS_RESULT_GROUP]->(rg:ResultGroupRaw)
MATCH (rg)<-[:HAS_RESULT_GROUP]-(o:OutcomeRaw)
MATCH (o)-[:HAS_OUTCOME_MEASUREMENT]->(om:OutcomeMeasurementRaw)
RETURN keys(om) AS outcome_measurement_keys
LIMIT 1;
```

Queries Q24–Q27 use `$NCT_ID` as a literal placeholder—replace it (e.g., `NCT00007189`) before execution.

---

## 5) How to Interpret Outputs (agent must follow these rules)

### BioLink directness

- If **Q7/Q8 = 0**, you must say:
  - “No direct IL2 (HGNC:6001) → Alzheimer (MONDO:0004975) gene→disease evidence exists in BioLink in this graph snapshot.”

### Mechanistic bridge (the “strongest cross-domain story” you actually have)

- The strongest deterministic chain in your graph is:

**Aldesleukin (CHEMBL1201438)**
→ **IL-2 receptor complex (CHEMBL2364167)**
→ components **P01589 / P14784 / P31785**
→ BioLink proteins **PR:P01589 / PR:P14784 / PR:P31785**
→ receptor genes **IL2RA / IL2RB / IL2RG** (from BioLink gene nodes)
→ disease associations (BioLink gene→disease edges)

That is the mechanistic “drug → receptor biology → disease” spine.

### AACT selection discipline

- Do **not** anchor on the highest-PMID Alzheimer trials if they’re registries / behavioral (you already saw this).
- Use **Q21** (strict mechanistic intervention filter) first.
- If it yields 0, document that and fall back to **Q23/Q24** for PubMed-driven mechanistic literature (not trial outcomes).

### PubMed use

- Treat `StudyReferenceRaw.citation` as your canonical “title/metadata” since `Publication.title` is null in your snapshot.
- For each selected PMID, your agent should:
  - summarize why it supports IL2-axis relevance in AD
  - tag it to one of: receptor biology, Treg modulation, neuroinflammation, microglia/T-cell axis, cytokine signaling, safety/tolerability (if trial)

---

## 6) Explicit Gaps to Report (don’t hide them)

1. **BioLink IL2 gene lacks direct disease edges** in your snapshot (expected).
2. **ChEMBL drug mechanism is receptor-complex-centric**, not ligand-protein-centric.
3. **Gene↔Protein edges are sparse** (you observed only 1 `ENCODES_PROTEIN` edge for IL2). Therefore, for receptor subunits you must not rely on protein→gene encoding links; use deterministic gene anchors (Q17).
4. **AACT property names are not standardized in your query pack** (warnings on `event_term`, `value`). Must be fixed by the preflight key discovery queries (Q26/Q27), then regenerate a corrected AACT payload query set.

---
