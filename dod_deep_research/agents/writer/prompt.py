"""Prompt for the writer agent."""

WRITER_AGENT_PROMPT = """
Generate structured research output following the WriterOutput schema.

**Inputs (from shared state):**
- research_plan: Research plan with sections and key questions
- evidence_store: Evidence items organized by section (use IDs like "disease_overview_E1" in evidence_ids fields)
- validation_report: Validation errors/warnings to address
- drug_name: Drug name to use throughout (read from shared state)

**State Context:**
- research_plan: {state.research_plan}
- evidence_store: {state.evidence_store}
- validation_report (optional): {state.validation_report?}
- drug_name (optional): {state.drug_name?}

**Output:** Store WriterOutput under key "deep_research_output"

**Key Points:**
- Reference evidence via evidence_ids in mechanistic_rationales, competitive_landscape, drug_specific_trials
- Use section names from research_plan.sections[].name (exact enum values, not human-readable names)
- Address validation_report errors/warnings"""
