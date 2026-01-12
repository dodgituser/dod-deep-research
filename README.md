# DOD Deep Research

A map-reduce agentic pipeline for comprehensive deep research on disease indications and drug therapy, built with Google ADK.

## Architecture

The pipeline uses a two-stage map-reduce architecture with a shared evidence store to avoid duplicated retrieval/validation work and produce coherent final narratives.

### Pipeline Flow

```
Meta-Planner → Parallel Evidence Collectors → Aggregator → Writer
     ↓                    ↓                      ↓          ↓
Research Plan    Section-specific        Merged Store   Final
              Evidence (parallel)                      Output
```

### Key Components

1. **Meta-Planner**: Creates a structured research outline with sections and required evidence types
2. **Parallel Evidence Collectors**: Multiple retriever agents run in parallel, each collecting evidence for a specific section
3. **Aggregator**: Merges parallel collector outputs into a single evidence store with deduplication
4. **Writer**: Generates the final structured research output using aggregated evidence

## Data Models

### EvidenceItem

Individual evidence citation with:
- `id`: Unique evidence identifier
- `source`: Source type (pubmed, clinicaltrials, guideline, press_release, other)
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
  - `name`: Section name (e.g., "epidemiology", "biomarkers")
  - `description`: Section description
  - `required_evidence_types`: List of required evidence types
  - `key_questions`: Section-specific research questions
- `key_questions`: Overall research questions
- `scope`: Research scope and boundaries

## Pipeline Stages

### Stage 1: Meta-Planning

The meta-planner (powerful model: `GEMINI_25_PRO`) analyzes the indication and creates a structured research outline with:
- Defined sections for parallel processing
- Evidence type requirements per section
- Section-specific research questions

**Output**: `ResearchPlan` stored in `research_plan` state key

### Stage 2: Parallel Evidence Collection (Map)

Multiple collector agents run in parallel, each responsible for a specific section:
- Each collector reads the research plan
- Focuses on their assigned section's requirements
- Retrieves evidence from PubMed, clinical trials, guidelines, etc.
- Outputs section-specific evidence

**Output**: Multiple `CollectorResponse` objects stored in `evidence_store_section_{section_name}` state keys

**Default Sections**:
- `epidemiology`
- `biomarkers`
- `mechanisms`
- `trials`
- `competitive_landscape`

### Stage 3: Aggregation (Reduce)

The aggregator merges all section-specific evidence stores:
- Combines evidence items from all collectors
- Performs deduplication using content hashing
- Builds indexes: `by_section`, `by_source`, `hash_index`
- Ensures proper section assignment

**Output**: Single `EvidenceStore` stored in `evidence_store` state key

### Stage 4: Writing

The writer generates the final structured output:
- Reads aggregated evidence store and research plan
- Uses section organization for coherent narrative
- Generates complete markdown report with:
  - Indication profile
  - Mechanistic rationales
  - Competitive landscape
  - IL-2 specific trials
  - Evidence citations

**Output**: `MarkdownReport` stored in `deep_research_output` state key

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
    drug_generic_name="Aldesleukin"
)

# Access final output
output = shared_state.deep_research_output
```

## CLI Usage

```bash
dod-deep-research \
  --indication "cancer" \
  --drug-name "IL-2" \
  --drug-form "low-dose IL-2" \
  --drug-generic-name "Aldesleukin" \
  --output results.json
```

## Project Structure

```
dod_deep_research/
├── agents/
│   ├── planner/          # Meta-planner agent
│   ├── collector/        # Parallel evidence collectors
│   ├── aggregator/       # Evidence aggregator
│   ├── writer/           # Final report writer
│   ├── evidence_store.py # Evidence store utilities
│   └── sequential_agent.py  # Pipeline definition
├── schemas.py            # Data models
└── deep_research.py      # Entry point
```

## State Keys

The pipeline uses the following state keys for inter-agent communication:

- `research_plan`: `ResearchPlan` (Meta-planner output)
- `evidence_store_section_{section_name}`: `CollectorResponse` (Collector outputs)
- `evidence_store`: `EvidenceStore` (Aggregator output)
- `deep_research_output`: `MarkdownReport` (Writer output)
