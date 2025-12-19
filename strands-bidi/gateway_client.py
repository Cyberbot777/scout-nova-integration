"""
Gateway Client - MCP client setup for AgentCore Gateway.
Handles AWS SigV4 authentication for secure Gateway access.

"""
import boto3
from mcp.client.streamable_http import streamablehttp_client
from httpx_auth_awssigv4 import SigV4Auth
from strands.tools.mcp import MCPClient

from scout_config import GATEWAY_URL, REGION, SERVICE


def get_sigv4_auth() -> SigV4Auth:
    """Get AWS SigV4 auth for httpx requests."""
    session = boto3.Session()
    credentials = session.get_credentials()
    frozen_credentials = credentials.get_frozen_credentials()
    
    return SigV4Auth(
        access_key=frozen_credentials.access_key,
        secret_key=frozen_credentials.secret_key,
        service=SERVICE,
        region=REGION,
        token=frozen_credentials.token
    )


def create_mcp_transport():
    """Create the MCP transport for connecting to AgentCore Gateway."""
    return streamablehttp_client(
        url=GATEWAY_URL,
        auth=get_sigv4_auth()
    )


def create_mcp_client() -> MCPClient:
    """Create an MCP client for Gateway tools."""
    return MCPClient(create_mcp_transport)


async def load_gateway_tools(mcp_client: MCPClient) -> list:
    """Load tools from the AgentCore Gateway.
    
    Returns:
        List of tools available from the Gateway
    """
    tools = await mcp_client.load_tools()
    return tools

