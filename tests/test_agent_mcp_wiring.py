"""Tests for MCP connector wiring in the ADK root agent."""

import importlib

from dod_deep_research.agents import mcp_toolsets


def test_mcp_toolset_factories_use_expected_filters() -> None:
    """Builds each toolset and verifies expected MCP tool filters."""
    assert mcp_toolsets.create_pubmed_toolset().tool_filter == [
        "pubmed_search_articles",
        "pubmed_fetch_contents",
    ]
    assert mcp_toolsets.create_clinical_trials_toolset().tool_filter == [
        "clinicaltrials_search_studies",
        "clinicaltrials_get_study",
    ]
    assert mcp_toolsets.create_exa_toolset().tool_filter == [
        "web_search_exa",
        "crawling_exa",
        "company_research_exa",
    ]
    assert mcp_toolsets.create_neo4j_toolset().tool_filter == ["get_neo4j_schema"]


def test_mcp_toolset_factories_honor_env_urls(monkeypatch) -> None:
    """Ensures connector URLs are sourced from environment variables."""
    monkeypatch.setenv("PUBMED_MCP_URL", "https://pubmed.example/mcp")
    monkeypatch.setenv("CLINICAL_TRIALS_MCP_URL", "https://ct.example/mcp")
    monkeypatch.setenv("EXA_MCP_URL", "https://exa.example/mcp")
    monkeypatch.setenv("NEO4J_MCP_URL", "https://neo4j.example/api/mcp/")

    pubmed = mcp_toolsets.create_pubmed_toolset()
    clinical = mcp_toolsets.create_clinical_trials_toolset()
    exa = mcp_toolsets.create_exa_toolset()
    neo4j = mcp_toolsets.create_neo4j_toolset()

    assert pubmed.__dict__["_connection_params"].url == "https://pubmed.example/mcp"
    assert clinical.__dict__["_connection_params"].url == "https://ct.example/mcp"
    assert exa.__dict__["_connection_params"].url == "https://exa.example/mcp"
    assert neo4j.__dict__["_connection_params"].url == "https://neo4j.example/api/mcp/"


def test_root_agent_includes_pipeline_and_mcp_tools() -> None:
    """Validates root agent tool list includes pipeline + MCP connectors."""
    from dod_deep_research import agent

    reloaded = importlib.reload(agent)
    tools = reloaded.root_agent.tools

    assert any(getattr(tool, "__name__", "") == "run_deep_research_pipeline" for tool in tools)
    mcp_toolsets_in_root = [
        tool for tool in tools if isinstance(tool, mcp_toolsets.CachedMcpToolset)
    ]
    assert len(mcp_toolsets_in_root) == 4
