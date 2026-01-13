"""Prompt for writer agents."""

LONG_WRITER_SECTION_PROMPT = """
Generate a single section of a deep research paper in markdown following the SectionDraft schema.

**State Context (inputs from shared state):**
- current_report_draft (full report so far; use to avoid repetition): {current_report_draft}
- current_section (section name, description, key questions, scope): {current_section}
- current_section_name (section heading to use): {current_section_name}
- evidence_store (full evidence across all sections): {evidence_store}
- section_evidence (evidence for the current section): {section_evidence}
- allowed_evidence_ids (optional, allowed citations): {allowed_evidence_ids?}
- validation_report (optional, errors/warnings to address): {validation_report?}
- drug_name (optional, use throughout): {drug_name?}
- indication (optional, use throughout): {indication?}
- drug_form (optional, if provided): {drug_form?}
- drug_generic_name (optional, if provided): {drug_generic_name?}

**Output:** Store SectionDraft under key "section_draft"

**Key Points:**
- Write only the current section; do not include other sections or a References section.
- Start the section with heading "## <current_section_name>" exactly.
- Avoid repeating content already present in current_report_draft.
- Cite evidence inline using bracketed evidence IDs, e.g. [disease_overview_E1].
- Only use IDs listed in allowed_evidence_ids.
- Do not cite or invent sources outside the provided evidence_store.
- If a claim is not supported by evidence_store, explicitly say it is not supported by available evidence.
- Address validation_report errors/warnings if provided."""
