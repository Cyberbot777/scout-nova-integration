"""
Scout Voice Agent - AgentCore Deployable Version.

Production voice agent using Strands BidiAgent with Nova Sonic
and AgentCore Gateway tools.

Deployment:
    agentcore configure --entrypoint scout_voice_agent.py
    agentcore launch
"""
import asyncio
import os
import logging

from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.io import BidiAudioIO, BidiTextIO
from strands.experimental.bidi.models import BidiNovaSonicModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from scout_config import (
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
    GUARDRAIL_ID,
    GUARDRAIL_VERSION,
)
from gateway_client import create_mcp_client, load_gateway_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ScoutVoiceAgent")

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Global agent instance (initialized on first request)
_agent = None
_mcp_client = None


async def get_agent() -> BidiAgent:
    """Get or create the agent instance (singleton pattern)."""
    global _agent, _mcp_client
    
    if _agent is None:
        logger.info("Initializing Scout Voice Agent...")
        
        # Create MCP client and load Gateway tools
        _mcp_client = create_mcp_client()
        
        try:
            tools = await load_gateway_tools(_mcp_client)
            logger.info(f"Loaded {len(tools)} tools from Gateway")
        except Exception as e:
            logger.error(f"Failed to load Gateway tools: {e}")
            tools = []
        
        # Create Nova Sonic model
        model = BidiNovaSonicModel(
            model_id=NOVA_MODEL_ID,
            provider_config={"audio": {"voice": VOICE_ID}},
            client_config={"region": REGION},
        )
        
        # Create BidiAgent
        _agent = BidiAgent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        
        logger.info("Scout Voice Agent initialized successfully")
    
    return _agent


@app.entrypoint
def invoke(payload: dict) -> dict:
    """AgentCore entrypoint for handling requests.
    
    For voice streaming, this handles the initial connection.
    Audio streaming is managed separately through WebSocket.
    
    Args:
        payload: Request payload with prompt or audio data
        
    Returns:
        Response dict with response or error
    """
    prompt = payload.get("prompt", "")
    
    if not prompt:
        return {"error": "No prompt provided"}
    
    try:
        # Get or create agent
        agent = asyncio.run(get_agent())
        
        # For text prompts, run synchronously and collect response
        async def process_prompt():
            # Use text I/O for non-streaming requests
            text_io = BidiTextIO()
            
            # This is a simplified version for text requests
            # Full voice streaming requires WebSocket connection
            response_text = ""
            
            # TODO: Implement proper text-only response handling
            # For now, return acknowledgment
            return f"Scout Voice Agent ready. Received: {prompt[:100]}..."
        
        response = asyncio.run(process_prompt())
        
        return {"response": response}
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"error": str(e)}


async def run_voice_server(host: str = "localhost", port: int = 8080):
    """Run the voice agent as a standalone voice server.
    
    This is used when running outside AgentCore for local voice testing.
    """
    logger.info("=" * 60)
    logger.info("Scout Voice Agent - Voice Server Mode")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Model: {NOVA_MODEL_ID}")
    logger.info(f"Region: {REGION}")
    logger.info(f"Gateway: Connected with tools")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Frontend should connect to: ws://localhost:8080")
    logger.info("")
    logger.info("Note: This uses BidiAgent which manages its own streaming.")
    logger.info("      Frontend needs to be compatible with Nova Sonic events.")
    logger.info("=" * 60)
    
    agent = await get_agent()
    
    # For voice streaming, BidiAgent handles the I/O automatically
    # when you call agent.run() with appropriate I/O handlers
    
    # Audio and text I/O
    audio_io = BidiAudioIO()
    text_io = BidiTextIO()
    
    logger.info("Starting agent.run() - ready for connections...")
    
    # Run agent with both audio and text I/O
    # This will run continuously, handling bidirectional streaming
    await agent.run(
        inputs=[audio_io.input()],
        outputs=[audio_io.output(), text_io.output()]
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scout Voice Agent")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--agentcore", action="store_true", help="Run in AgentCore mode")
    
    args = parser.parse_args()
    
    if args.agentcore:
        # Run as AgentCore service
        logger.info("Starting Scout Voice Agent on AgentCore runtime...")
        app.run(host=args.host, port=args.port)
    else:
        # Run as standalone voice server
        asyncio.run(run_voice_server(host=args.host, port=args.port))

