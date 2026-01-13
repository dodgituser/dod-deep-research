"""Prompt for the writer agent."""

WRITER_AGENT_PROMPT = """
Generate a deep research paper in markdown following the MarkdownReport schema.

**Inputs (from shared state):**
- research_plan: Research plan with sections and key questions
- evidence_store: Evidence items organized by section (use IDs like "disease_overview_E1" in evidence_ids fields)
- allowed_evidence_ids: Explicit list of evidence IDs you may cite
- validation_report: Validation errors/warnings to address
- drug_name: Drug name to use throughout (read from shared state)
- indication: Disease/indication name to use throughout (read from shared state)
- drug_form: Drug form if provided (read from shared state)
- drug_generic_name: Drug generic name if provided (read from shared state)

**State Context:**
- research_plan: {research_plan}
- evidence_store: {evidence_store}
- allowed_evidence_ids (optional): {allowed_evidence_ids?}
- validation_report (optional): {validation_report?}
- drug_name (optional): {drug_name?}
- indication (optional): {indication?}
- drug_form (optional): {drug_form?}
- drug_generic_name (optional): {drug_generic_name?}

**Output:** Store MarkdownReport under key "deep_research_output"

**Key Points:**
- Write a full markdown report with clear headings for each research_plan.sections[].name in order.
- Anchor the report to the provided indication and drug_name (and drug_form/drug_generic_name if present); do not introduce other diseases.
- Cite evidence inline using bracketed evidence IDs, e.g. [disease_overview_E1], and only use IDs listed in allowed_evidence_ids.
- Do not cite or invent sources outside the provided evidence_store.
- If a claim is not supported by evidence_store, explicitly say it is not supported by available evidence.
- Add a final "References" section listing each cited evidence ID with title and URL from evidence_store.
- Address validation_report errors/warnings."""
