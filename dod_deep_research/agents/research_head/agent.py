"""Research Head agent for gap analysis and targeted retrieval."""

import logging

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.research_head.prompt import RESEARCH_HEAD_AGENT_PROMPT
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.models import GeminiModels
from dod_deep_research.utils.evidence import SECTION_MIN_EVIDENCE

logger = logging.getLogger(__name__)

# Pre-render a simple table for min evidence targets
section_min_evidence_table = "\n".join(
    f"- {section.value}: {count}" for section, count in SECTION_MIN_EVIDENCE.items()
)


research_head_agent = Agent(
    name="research_head_agent",
    instruction=RESEARCH_HEAD_AGENT_PROMPT.format(
        section_min_evidence_table=section_min_evidence_table
    ),
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    include_contents="none",
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
    output_key="research_head_plan",
    output_schema=ResearchHeadPlan,
)
