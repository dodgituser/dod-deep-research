import asyncio
import http.client
import json
import os
import socket
from urllib.parse import urlsplit

import httpx
import pytest


# Helper to check if MCP services are running
def is_port_open(host, port):
    """Check if a TCP port is open on a given host."""
    socket_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_connection.settimeout(1)
    try:
        socket_connection.connect((host, port))
        socket_connection.close()
        return True
    except (socket.timeout, ConnectionRefusedError, PermissionError):
        return False


PUBMED_URL = os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp")
CLINICAL_TRIALS_URL = os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp")


def split_host_port(url):
    """Extract host and port from a URL for connectivity checks."""
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port is not None:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 80


pubmed_host, pubmed_port = split_host_port(PUBMED_URL)
clinical_trials_host, clinical_trials_port = split_host_port(CLINICAL_TRIALS_URL)
VERBOSE_OUTPUT = os.getenv("MCP_TEST_VERBOSE", "").lower() in {"1", "true", "yes"}
INVOKE_TOOLS = os.getenv("MCP_TEST_INVOKE", "").lower() in {"1", "true", "yes"}

# Pytest markers to skip tests if services are not running
requires_pubmed_mcp = pytest.mark.skipif(
    not is_port_open(pubmed_host, int(pubmed_port)),
    reason="PubMed MCP service is not running",
)
requires_clinical_trials_mcp = pytest.mark.skipif(
    not is_port_open(clinical_trials_host, int(clinical_trials_port)),
    reason="ClinicalTrials MCP service is not running",
)


async def parse_mcp_response(response):
    """Parse JSON-RPC responses, including event-stream payloads."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return response.json()

    last_payload = None
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            continue
        last_payload = payload
    if last_payload is None:
        raise AssertionError("No MCP payload received from event stream response.")
    return json.loads(last_payload)


async def mcp_request(client, url, method, params=None, request_id=1):
    """Send a JSON-RPC MCP request and return the parsed response."""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    try:
        async with client.stream(
            "POST", url, json=payload, headers=headers, timeout=30
        ) as response:
            response.raise_for_status()
            parsed = await parse_mcp_response(response)
    except httpx.RemoteProtocolError:
        parsed = await asyncio.to_thread(sync_mcp_request, url, payload, headers)
    if "error" in parsed:
        raise AssertionError(f"MCP error response: {parsed['error']}")
    return parsed.get("result", parsed)


def sync_mcp_request(url, payload, headers):
    """Fallback MCP request using stdlib HTTP to tolerate strict header parsing."""
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    connection_cls = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_cls(host, port, timeout=30)
    body = json.dumps(payload)
    try:
        connection.request("POST", parsed.path or "/mcp", body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read().decode("utf-8", errors="replace")
    finally:
        connection.close()
    if response.status >= 400:
        raise AssertionError(f"MCP HTTP {response.status}: {response_body}")
    if "text/event-stream" in (response.getheader("Content-Type") or ""):
        last_payload = None
        for line in response_body.splitlines():
            if line.startswith("data:"):
                payload_line = line[len("data:") :].strip()
                if payload_line and payload_line != "[DONE]":
                    last_payload = payload_line
        if last_payload is None:
            raise AssertionError("No MCP payload received from event stream response.")
        return json.loads(last_payload)
    return json.loads(response_body)


async def assert_tools_list(client, url, expected_tool):
    """Validate MCP tools/list as a basic health check."""
    await mcp_request(
        client,
        url,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "dod-deep-research-tests", "version": "0.0.0"},
            "capabilities": {},
        },
    )
    result = await mcp_request(client, url, "tools/list")
    tools = result.get("tools", [])
    assert tools, "Expected MCP tools/list to return at least one tool."
    tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    if VERBOSE_OUTPUT:
        sample = sorted(name for name in tool_names if name)[:10]
        print(f"MCP tools/list returned {len(tool_names)} tool(s); sample={sample}")
    assert expected_tool in tool_names, (
        f"Expected tool '{expected_tool}' not found in MCP tool list."
    )


async def maybe_invoke_tool(client, url, tool_name, arguments):
    """Optionally call a tool for smoke validation."""
    if not INVOKE_TOOLS:
        return
    result = await mcp_request(
        client,
        url,
        "tools/call",
        {"name": tool_name, "arguments": arguments},
    )
    if VERBOSE_OUTPUT:
        preview = json.dumps(result)[:500]
        print(f"tools/call {tool_name} result preview: {preview}...")
    assert result, f"Expected non-empty result from tools/call {tool_name}"


@pytest.mark.asyncio
@requires_pubmed_mcp
async def test_direct_pubmed_endpoint():
    """Health check the PubMed MCP endpoint via tools/list."""
    async with httpx.AsyncClient() as client:
        await assert_tools_list(client, PUBMED_URL, "pubmed_search_articles")
        await maybe_invoke_tool(
            client,
            PUBMED_URL,
            "pubmed_search_articles",
            {"query": "IL-2 cancer"},
        )


@pytest.mark.asyncio
@requires_clinical_trials_mcp
async def test_direct_clinicaltrials_endpoint():
    """Health check the ClinicalTrials.gov MCP endpoint via tools/list."""
    async with httpx.AsyncClient() as client:
        await assert_tools_list(
            client, CLINICAL_TRIALS_URL, "clinicaltrials_search_studies"
        )
        await maybe_invoke_tool(
            client,
            CLINICAL_TRIALS_URL,
            "clinicaltrials_search_studies",
            {"query": "IL-2 cancer"},
        )
