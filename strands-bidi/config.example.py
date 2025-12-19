"""
Configuration template for voice agents.
Copy this to your_agent_config.py and customize for your agent.
"""

# Agent Identity
AGENT_NAME = "MyAgent"

# Nova Sonic Configuration
NOVA_MODEL_ID = "amazon.nova-sonic-v1:0"
REGION = "us-east-1"
VOICE_ID = "matthew"  # Options: matthew, joanna, etc.

# Gateway Configuration (for MCP tools)
GATEWAY_URL = "https://your-gateway-url.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
SERVICE = "bedrock-agentcore"

# System Prompt
SYSTEM_PROMPT = """You are a helpful AI assistant.

AVAILABLE TOOLS:
- List your tools and how to use them

INSTRUCTIONS:
- Add specific instructions for your agent behavior
- Format guidelines
- Tone and personality
"""

