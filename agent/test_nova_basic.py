#!/usr/bin/env python3
"""
Minimal test - Just Nova Sonic + Strands BidiAgent.
No tools, no Gateway - validate the core works first.

Usage:
    cd agent
    python test_nova_basic.py
"""
import asyncio
import os
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded credentials from {env_path}")
    else:
        print(f"No .env file found at {env_path}")
        print("Using environment variables...")
except ImportError:
    print("Note: python-dotenv not installed, using environment variables")

from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.io import BidiTextIO
from strands.experimental.bidi.models import BidiNovaSonicModel


async def test_nova_basic():
    """Test BidiAgent with Nova Sonic - text mode, no tools."""
    print()
    print("=" * 60)
    print("TEST: Nova Sonic + Strands BidiAgent")
    print("=" * 60)
    print()
    
    # Check credentials
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'us-east-1'))
    
    if not access_key or not secret_key:
        print("ERROR: AWS credentials not set!")
        print()
        print("Create agent/.env with:")
        print("  AWS_ACCESS_KEY_ID=your_key")
        print("  AWS_SECRET_ACCESS_KEY=your_secret")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return
    
    print(f"AWS credentials: {access_key[:8]}...")
    print(f"Region: {region}")
    print()
    
    try:
        print("Creating BidiNovaSonicModel...")
        model = BidiNovaSonicModel(
            model_id="amazon.nova-sonic-v1:0",
            provider_config={"audio": {"voice": "matthew"}},
            client_config={"region": region},
        )
        print("  Model created successfully!")
    except Exception as e:
        print(f"  ERROR creating model: {e}")
        import traceback
        traceback.print_exc()
        return
    
    try:
        print("Creating BidiAgent (no tools)...")
        agent = BidiAgent(
            model=model,
            tools=[],  # No tools - just test the basics
            system_prompt="You are a helpful assistant. Keep responses brief.",
        )
        print("  Agent created successfully!")
    except Exception as e:
        print(f"  ERROR creating agent: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 60)
    print("SUCCESS! Agent ready.")
    print("Type a message and press Enter (or 'quit' to exit)")
    print("=" * 60)
    print()
    
    # Text I/O for CLI testing
    text_io = BidiTextIO()
    
    try:
        await agent.run(
            inputs=[text_io.input()],
            outputs=[text_io.output()]
        )
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\nERROR during agent run: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest complete!")


if __name__ == "__main__":
    print()
    print("Scout Voice Agent - Nova Sonic Basic Test")
    print("==========================================")
    
    try:
        asyncio.run(test_nova_basic())
    except KeyboardInterrupt:
        print("\nTest stopped.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()

