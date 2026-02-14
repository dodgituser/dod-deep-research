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
    assert mcp_toolsets.create_ols_toolset().tool_filter is None


def test_mcp_toolset_factories_honor_env_urls(monkeypatch) -> None:
    """Ensures connector URLs are sourced from environment variables."""
    monkeypatch.setenv("PUBMED_MCP_URL", "https://pubmed.example/mcp")
    monkeypatch.setenv("CLINICAL_TRIALS_MCP_URL", "https://ct.example/mcp")
    monkeypatch.setenv("EXA_MCP_URL", "https://exa.example/mcp")
    monkeypatch.setenv("NEO4J_MCP_URL", "https://neo4j.example/api/mcp/")
    monkeypatch.setenv("OLS_MCP_URL", "https://www.ebi.ac.uk/ols4/api/mcp")

    pubmed = mcp_toolsets.create_pubmed_toolset()
    clinical = mcp_toolsets.create_clinical_trials_toolset()
    exa = mcp_toolsets.create_exa_toolset()
    neo4j = mcp_toolsets.create_neo4j_toolset()
    ols = mcp_toolsets.create_ols_toolset()

    assert pubmed.__dict__["_connection_params"].url == "https://pubmed.example/mcp"
    assert clinical.__dict__["_connection_params"].url == "https://ct.example/mcp"
    assert exa.__dict__["_connection_params"].url == "https://exa.example/mcp"
    assert neo4j.__dict__["_connection_params"].url == "https://neo4j.example/api/mcp/"
    assert ols.__dict__["_connection_params"].url == "https://www.ebi.ac.uk/ols4/api/mcp"
    assert "Authorization" not in pubmed.__dict__["_connection_params"].headers


def test_mcp_toolset_factories_add_id_token_for_cloud_run_urls(monkeypatch) -> None:
    """Ensures Cloud Run MCP URLs include an OIDC Authorization header."""
    monkeypatch.setenv("PUBMED_MCP_URL", "https://pubmed-abc-uw.a.run.app/mcp")
    monkeypatch.setenv("NEO4J_MCP_URL", "https://neo4j-abc-uw.a.run.app/api/mcp/")
    monkeypatch.setenv("OLS_MCP_URL", "https://ols-abc-uw.a.run.app/ols4/api/mcp")

    audiences: list[str] = []

    def _fake_fetch(audience: str) -> str:
        audiences.append(audience)
        return "test-token"

    monkeypatch.setattr(mcp_toolsets, "_fetch_identity_token", _fake_fetch)

    pubmed = mcp_toolsets.create_pubmed_toolset()
    neo4j = mcp_toolsets.create_neo4j_toolset()
    ols = mcp_toolsets.create_ols_toolset()

    pubmed_headers = pubmed.__dict__["_connection_params"].headers
    neo4j_headers = neo4j.__dict__["_connection_params"].headers
    ols_headers = ols.__dict__["_connection_params"].headers
    assert pubmed_headers["Authorization"] == "Bearer test-token"
    assert neo4j_headers["Authorization"] == "Bearer test-token"
    assert ols_headers["Authorization"] == "Bearer test-token"
    assert audiences == [
        "https://pubmed-abc-uw.a.run.app",
        "https://neo4j-abc-uw.a.run.app",
        "https://ols-abc-uw.a.run.app",
    ]


def test_root_agent_exposes_pipeline_tool_only() -> None:
    """Validates root agent tool list only exposes pipeline execution."""
    from dod_deep_research import agent

    reloaded = importlib.reload(agent)
    tools = reloaded.root_agent.tools

    assert any(getattr(tool, "__name__", "") == "run_deep_research_pipeline" for tool in tools)
    assert len(tools) == 1
