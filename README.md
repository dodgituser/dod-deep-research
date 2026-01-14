# DOD Deep Research

A map-reduce agentic pipeline for deep research on disease indications and drug therapies, built with Google ADK.

## Architecture

The pipeline combines parallel evidence collection with a gap-driven refinement loop. Evidence is deduplicated into a shared store, then the writer produces a single markdown report.

### Pipeline Flow

```
Planner → Parallel Collectors → Evidence Aggregation → Research Head Loop → Writer
```

### Key Components

1. **Planner**: Builds a structured research plan and section-specific questions.
2. **Parallel Evidence Collectors**: Fetch PubMed, ClinicalTrials.gov, and web sources per section.
3. **Evidence Aggregation**: Deduplicates evidence and builds indexes for use by other agents.
4. **Research Head**: Detects gaps and triggers targeted collectors to fill missing evidence.
5. **Writer**: Produces the final markdown report and references from the evidence store.

## Data Models

### EvidenceItem

Individual evidence citation with:
- `id`: Unique evidence identifier
- `source`: Source type (pubmed, clinicaltrials, web)
- `title`: Title of the evidence source
- `url`: Source URL (optional)
- `quote`: Relevant quote or excerpt (optional)
- `year`: Publication year (optional)
- `tags`: List of categorization tags
- `section`: Section/topic this evidence belongs to

### EvidenceStore

Centralized evidence store with indexing and deduplication:
- `items`: List of all evidence items
- `by_section`: Dictionary mapping section names to evidence IDs
- `by_source`: Dictionary mapping source URLs to evidence IDs
- `hash_index`: Dictionary mapping content hashes to evidence IDs (for deduplication)

### ResearchPlan

Structured research plan containing:
- `disease`: Disease/indication name
- `research_areas`: List of research areas to investigate
- `sections`: List of `ResearchSection` objects with:
  - `name`: Section name (e.g., "disease_overview", "therapeutic_landscape")
  - `description`: Section description
  - `key_questions`: Section-specific research questions
  - `scope`: Research scope and boundaries

### ResearchHeadPlan

Gap analysis output containing:
- `continue_research`: Whether another targeted collection pass is needed
- `gaps`: List of missing questions per section

## Pipeline Stages

### Stage 1: Planning

The planner analyzes the indication and creates a structured research outline with:
- Defined sections for parallel processing
- Evidence type requirements per section
- Section-specific research questions

**Output**: `ResearchPlan` stored in `research_plan` state key

### Stage 2: Parallel Evidence Collection (Map)

Multiple collector agents run in parallel, each responsible for a specific section:
- Each collector reads the research plan
- Focuses on their assigned section's requirements
- Retrieves evidence from PubMed, ClinicalTrials.gov, and Exa web search (for guidelines/market/competitor sources)
- Outputs section-specific evidence

**Output**: Multiple `CollectorResponse` objects stored in `evidence_store_section_{section_name}` state keys

**Default Sections**:
- `rationale_executive_summary`
- `disease_overview`
- `therapeutic_landscape`
- `current_treatment_guidelines`
- `competitor_analysis`
- `clinical_trials_analysis`
- `market_opportunity_analysis`

### Stage 3: Aggregation (Reduce)

The aggregator merges all section-specific evidence stores:
- Combines evidence items from all collectors
- Performs deduplication using content hashing
- Builds indexes: `by_section`, `by_source`, `hash_index`
- Ensures proper section assignment

**Output**: Single `EvidenceStore` stored in `evidence_store` state key

### Stage 4: Gap-Driven Loop + Writing

The research head evaluates evidence coverage and triggers targeted collectors if gaps remain. Once gaps are resolved, the writer generates the report.

The writer generates the final structured output:
- Reads aggregated evidence store and research plan
- Uses section organization for coherent narrative
- Generates complete markdown report with:
  - Sectioned narrative aligned to the research plan
  - Evidence citations from the evidence store
  - Final references list

**Output**: `MarkdownReport` stored in `deep_research_output` state key

## Outputs

Each run writes to `outputs/<indication>-<timestamp>/`:
- `report.md`: Final markdown report
- `pipeline_events_<timestamp>.json`: Event log
- `session_state.json`: Full shared state
- `pipeline_evals.json`: Evaluation metrics
- `agent_logs/`: Per-agent callbacks for debugging

## Benefits

- **Avoids Duplication**: Parallel collectors share a single evidence store, preventing duplicate retrieval work
- **Coherent Narrative**: Single writer produces unified final report using organized evidence
- **Scalable**: Easy to add new sections by creating additional collector agents
- **Efficient**: Parallel collection reduces overall pipeline execution time

## Usage

```python
from dod_deep_research.deep_research import run_pipeline

shared_state = run_pipeline(
    indication="cancer",
    drug_name="IL-2",
    drug_form="low-dose IL-2",
    drug_generic_name="Aldesleukin",
)

# Access final output
output = shared_state.deep_research_output
```

## CLI Usage

```bash
uv run dod-deep-research \
  --indication "cancer" \
  --drug-name "IL-2" \
  --drug-form "low-dose IL-2" \
  --drug-generic-name "Aldesleukin" \
  --drug-alias Aldesleukin \
  --drug-alias "COYA 301" \
  --indication-alias "Alzheimer disease"

### Docker Compose

```
make run INDICATION="cancer" DRUG_NAME="IL-2"
```

### Alias Flags

```
uv run dod-deep-research \
  --indication "Alzheimer's disease" \
  --drug-name "IL-2" \
  --drug-alias Aldesleukin \
  --drug-alias "COYA 301" \
  --indication-alias "Alzheimer disease" \
  --indication-alias "Alzheimer dementia"
```
```

## Project Structure

```
dod_deep_research/
├── agents/
│   ├── planner/          # Meta-planner agent
│   ├── collector/        # Parallel evidence collectors
│   ├── writer/           # Final report writer
│   ├── research_head/    # Gap analysis + targeted collectors
│   └── evidence.py       # Evidence aggregation utilities
├── prompts/              # Indication prompt templates
└── deep_research.py      # Entry point
```

## State Keys

The pipeline uses the following state keys for inter-agent communication:

- `research_plan`: `ResearchPlan` (Meta-planner output)
- `evidence_store_section_{section_name}`: `CollectorResponse` (Collector outputs)
- `evidence_store`: `EvidenceStore` (Aggregator output)
- `research_head_plan`: `ResearchHeadPlan` (Research head output)
- `deep_research_output`: `MarkdownReport` (Writer output)

## Diagrams

See `docs/architecture.md` for a Mermaid pipeline diagram.
