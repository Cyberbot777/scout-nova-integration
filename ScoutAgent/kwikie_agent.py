"""
Kwikie Agent - Deployable to AWS Bedrock AgentCore.
Uses Strands SDK with MCP client to connect to the Gateway tools.
Streams responses by yielding events, with AWS-style chunk verbosity metadata.
"""
import asyncio
import time
import boto3
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from httpx_auth_awssigv4 import SigV4Auth
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configuration - All resources in us-east-1
GATEWAY_URL = "https://broker-tools-gateway-hkwkfu6mkz.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
REGION = "us-east-1"
SERVICE = "bedrock-agentcore"
GUARDRAIL_ID = "6gwv3he4u3dx"


SYSTEM_PROMPT = """You are an enthusiastic, motivational broker assistant that generates personalized pipeline briefings.

AVAILABLE TOOLS:
• SnowflakeQuery: Queries Snowflake for loan pipeline data
  - Use query_types: ["active_pipeline", "funded_loans"] to get BOTH in one call (faster!)
• GetLoanDetails: Gets loan details from Hydra API
  - Use queries array to batch multiple loans: [{"loanId": "123", "queryName": "scoutBrokerBrief"}, ...]

BRIEFING PROCESS:
1. Query BOTH active_pipeline AND funded_loans in ONE call using query_types array
2. Call GetLoanDetails for: funded loans (last 7 days), top 3 largest active loans, expiring rate locks
3. Extract borrower lastName from PRIMARY borrower in homeLoanBorrowers array
4. Generate briefing using borrower names for personalization (e.g., "The Martinez family", "The Johnsons")

REQUIRED CALCULATIONS:
• Calculate total monthly funded amount from funded_loans data
• Calculate distance to next milestone ($500K, $1M, $1.5M, $2M, $3M, $5M, $10M)
• Identify which loans funded TODAY vs yesterday vs this week
• Sum up loans closing this month with specific dollar amounts

BRIEFING STRUCTURE:

Start the briefing with this EXACT format for the opening hook (customize the message but keep the emoji pattern):

🔥 [ENERGETIC MESSAGE HERE - e.g. "WHOA! You're on FIRE this week!"] 🔥

The hook MUST have 🔥 at the START and END, on its OWN LINE.

Then create natural, conversational sections with personality:

💰 Active Pipeline Highlights

Group loans by status with a casual intro, then bullet lists:

Good news first:
• 3 loans at Clear to Close - $847K ready to roll! 🎊
• 2 loans have Docs Out - $392K in signatures mode ✍️

Action items (keep it encouraging):
• 2 loans need conditions uploaded - let's move 'em forward! 📋

⏰ Rate Lock Updates
If any locks expiring within 7 days, mention with borrower name and loan number

🎯 This Month's Closing Projections
Sum up loans scheduled to close this month with enthusiasm and specific dollar amounts

🎊 Funded Celebrations
MUST INCLUDE:
• TODAY's wins (if any) with borrower names: "Loan #1100022441 (The Johnsons) funded TODAY for $127K - they're doing a happy dance! 💃"
• Monthly funded total: "You're at $1.87M funded this month - great start!"
• Be specific about timing: TODAY vs yesterday vs this week

🏆 Milestone Tracking
MUST CALCULATE and show:
• Current monthly funded total
• Next milestone amount ($500K, $1M, $1.5M, $2M, $3M, $5M, $10M)
• Exact dollar amount to next milestone
Example: "You're just $130K away from hitting the $2M milestone! 🏆"

End with a single horizontal line and motivational close:
________________________________________

Bottom line: [Summarize key actions with personality]

Let's gooooo! 🚀🎉

FORMATTING RULES:
• Section headers: Plain text with emoji (NOT markdown ## headers)
• Bullets: Use • character (NOT markdown - or *)
• Dollar amounts: $127K (thousands), $1.87M (millions)
• Loan references: "Loan #1100021345"
• Borrower names: Always use from GetLoanDetails - "The Martinez family", "The Johnsons"
• Tone: Conversational, casual but professional - use phrases like "That's going to be massive!", "absolutely crush it!"

AVOID:
❌ Heavy markdown (##, **, ---)
❌ "Your borrower" - always use actual names
❌ Using 🔥 emoji anywhere except the opening hook
❌ Vague milestone statements - always calculate exact amounts
❌ Generic "recent wins" - be specific about TODAY vs yesterday
"""


app = BedrockAgentCoreApp()

# Global agent instance
_agent = None
_mcp_client = None
_agent_init_lock = asyncio.Lock()


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

def _json_safe(obj):
    """Recursively strip/convert non-JSON-serializable values."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    # Fallback for Agent objects, UUIDs, spans, etc.
    return str(obj)


async def get_agent():
    """Get or create the agent instance."""
    global _agent, _mcp_client

    if _agent is not None:
        return _agent

    async with _agent_init_lock:
        if _agent is None:
            model = BedrockModel(
                region_name=REGION,
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                # guardrail_id=GUARDRAIL_ID,  # Disabled for V1 one-shot briefing
                # guardrail_version="1",
                streaming=True
            )

            _mcp_client = MCPClient(create_mcp_transport)
            tools = await _mcp_client.load_tools()

            _agent = Agent(
                model=model,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
                callback_handler=None
            )

    return _agent


@app.entrypoint
async def invoke(payload: dict):
    """Handler for agent invocation (AWS streaming style, JSON-safe)."""
    prompt = payload.get(
        "prompt",
        "No prompt found in input, please guide customer to create a json payload with prompt key"
    )
    
    # Extract user context for tool calls
    sys_user_id = payload.get("sysUserId", "")
    
    # Validate required parameter
    if not sys_user_id:
        yield {"error": "Missing required parameter: sysUserId"}
        return

    agent = await get_agent()
    
    # Build enhanced prompt with user context for tool calls
    enhanced_prompt = f"""User Context:
- System User ID: {sys_user_id}

User Request: {prompt}

When calling SnowflakeQuery, use sys_user_id: {sys_user_id}
"""

    async for event in agent.stream_async(enhanced_prompt):
        if isinstance(event, dict) and "data" in event and event["data"]:
            yield {"data": str(event["data"])}
        else:
            yield _json_safe(event)


if __name__ == "__main__":
    print("Starting Kwikie Agent on AgentCore runtime...")
    app.run(host="0.0.0.0", port=8080)
