#!/usr/bin/env python3
"""
Test Agent - Local testing for Scout Voice Agent.

This runs the BidiAgent in interactive mode for local development and testing.
Uses console I/O for testing without the full voice UI.

Usage:
    cd agent
    python test_agent.py

For voice testing, use the full frontend/backend setup.
"""
import asyncio
import os
import sys
import logging
from pathlib import Path

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded credentials from {env_path}")
except ImportError:
    pass

from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.io import BidiTextIO
from strands.experimental.bidi.models import BidiNovaSonicModel

from scout_config import (
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
    INFERENCE_CONFIG,
)
from gateway_client import create_mcp_client, load_gateway_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TestAgent")


def check_credentials() -> bool:
    """Check if AWS credentials are configured."""
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'us-east-1'))
    
    if not access_key or not secret_key:
        logger.error("AWS credentials not found!")
        logger.error("")
        logger.error("Option 1: Create agent/.env file:")
        logger.error("  cp env.example .env")
        logger.error("  # Edit .env with your credentials")
        logger.error("")
        logger.error("Option 2: Set environment variables")
        return False
    
    logger.info(f"AWS credentials found: {access_key[:8]}...")
    logger.info(f"AWS region: {region}")
    return True


async def run_test_agent():
    """Run the test agent with text I/O."""
    print("=" * 60)
    print("Scout Voice Agent - Test Mode")
    print("=" * 60)
    print()
    print("This is TEXT mode for testing without voice.")
    print("For full voice testing, run the frontend + backend.")
    print()
    
    # Check credentials
    if not check_credentials():
        sys.exit(1)
    
    # Create MCP client and load Gateway tools
    print("Connecting to AgentCore Gateway...")
    mcp_client = create_mcp_client()
    
    try:
        tools = await load_gateway_tools(mcp_client)
        print(f"Connected! Found {len(tools)} tool(s):")
        for tool in tools:
            print(f"  - {tool.tool_name}")
    except Exception as e:
        logger.error(f"Failed to connect to Gateway: {e}")
        print("\nRunning without tools (Gateway unavailable)")
        tools = []
    
    print()
    print("=" * 60)
    
    # Create Nova Sonic model
    model = BidiNovaSonicModel(
        model_id=NOVA_MODEL_ID,
        provider_config={"audio": {"voice": VOICE_ID}},
        client_config={"region": REGION},
    )
    
    # Create BidiAgent with tools
    agent = BidiAgent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    
    print("Agent ready! Type your message (or 'quit' to exit)")
    print("=" * 60)
    print()
    
    # Text I/O for testing
    text_io = BidiTextIO()
    
    try:
        # Run agent with text I/O only
        await agent.run(
            inputs=[text_io.input()],
            outputs=[text_io.output()]
        )
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    finally:
        # Cleanup MCP client
        try:
            mcp_client.__exit__(None, None, None)
        except Exception:
            pass


def main():
    """Main entry point."""
    try:
        asyncio.run(run_test_agent())
    except KeyboardInterrupt:
        print("\nTest agent stopped.")
    except Exception as e:
        logger.error(f"Test agent failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

