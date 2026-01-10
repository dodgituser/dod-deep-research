import pytest
import os
import json
import socket
import httpx

from dod_deep_research.tools.tooling import reflect_step


# Helper to check if MCP services are running
def is_port_open(host, port):
    """Check if a TCP port is open on a given host."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError):
        return False


PUBMED_URL = os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp")
CLINICAL_TRIALS_URL = os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp")

# Extract host and port for checking
pubmed_host, pubmed_port = PUBMED_URL.split("//")[1].split("/")[0].split(":")
clinical_trials_host, clinical_trials_port = (
    CLINICAL_TRIALS_URL.split("//")[1].split("/")[0].split(":")
)

# Pytest markers to skip tests if services are not running
requires_pubmed_mcp = pytest.mark.skipif(
    not is_port_open(pubmed_host, int(pubmed_port)),
    reason="PubMed MCP service is not running",
)
requires_clinical_trials_mcp = pytest.mark.skipif(
    not is_port_open(clinical_trials_host, int(clinical_trials_port)),
    reason="ClinicalTrials MCP service is not running",
)


async def post_to_mcp(client, url, tool_name, args):
    """Helper to send a request to an MCP endpoint and get the response."""
    # The payload should mimic the structure of a FunctionCall part.
    payload = {"function_call": {"name": tool_name, "args": args}}
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    full_response_content = ""
    async with client.stream(
        "POST", url, json=payload, headers=headers, timeout=30
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                full_response_content += line[len("data: ") :]
    # The response from the MCP server seems to be a JSON object representing a Part.
    response_part = json.loads(full_response_content)
    # The actual tool output is inside the 'content' field of the 'function_response'.
    return json.loads(response_part["function_response"]["response"]["content"])


@pytest.mark.asyncio
@requires_pubmed_mcp
async def test_direct_pubmed_endpoint():
    """Test the PubMed MCP endpoint directly using httpx."""
    async with httpx.AsyncClient() as client:
        print("\nCalling PubMed MCP for pubmed_search_articles...")
        search_content = await post_to_mcp(
            client, PUBMED_URL, "pubmed_search_articles", {"query": "cancer IL-2"}
        )

        assert "articles" in search_content
        assert len(search_content["articles"]) > 0
        article_id = search_content["articles"][0].get("id")
        print(f"PubMed MCP found {len(search_content['articles'])} articles.")
        assert article_id is not None, "First article should have an ID"

        print(
            f"\nCalling PubMed MCP for pubmed_fetch_contents (article: {article_id})..."
        )
        fetch_content = await post_to_mcp(
            client, PUBMED_URL, "pubmed_fetch_contents", {"article_id": article_id}
        )

        assert "content" in fetch_content
        assert len(fetch_content["content"]) > 0
        print(
            f"pubmed_fetch_contents response (truncated): {json.dumps(fetch_content)[:200]}..."
        )


@pytest.mark.asyncio
@requires_clinical_trials_mcp
async def test_direct_clinicaltrials_endpoint():
    """Test the ClinicalTrials.gov MCP endpoint directly using httpx."""
    async with httpx.AsyncClient() as client:
        print("\nCalling ClinicalTrials MCP for clinicaltrials_search_studies...")
        search_content = await post_to_mcp(
            client,
            CLINICAL_TRIALS_URL,
            "clinicaltrials_search_studies",
            {"query": "IL-2 cancer"},
        )

        assert "studies" in search_content
        assert len(search_content["studies"]) > 0
        nct_id = search_content["studies"][0].get("nct_id")
        print(f"ClinicalTrials MCP found {len(search_content['studies'])} studies.")
        assert nct_id is not None, "First study should have an NCT ID"

        print(
            f"\nCalling ClinicalTrials MCP for clinicaltrials_get_study (NCT ID: {nct_id})..."
        )
        get_study_content = await post_to_mcp(
            client, CLINICAL_TRIALS_URL, "clinicaltrials_get_study", {"nct_id": nct_id}
        )

        assert "study" in get_study_content
        assert get_study_content["study"]["nct_id"] == nct_id
        print(
            f"clinicaltrials_get_study response (truncated): {json.dumps(get_study_content)[:200]}..."
        )


def test_direct_reflect_step_call():
    """Test direct invocation of reflect_step function with a simple message."""
    message = "This is a reflection step for testing."

    print("\nCalling reflect_step...")
    result = reflect_step(message)

    assert result == f"Reflection recorded: {message}", (
        "reflect_step should return the formatted reflection string"
    )
    print("reflect_step called successfully.")
