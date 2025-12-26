#!/usr/bin/env python3
"""
Scout Voice Agent - LOCAL TESTING VERSION

Simplified server for local development and testing.
- No IMDS credential refresh
- No pre-signed URL generation
- Direct WebSocket connection
- Simple CORS for React frontend

For AgentCore deployment, use server.py instead.
"""
import logging
import uvicorn
import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

from scout_config import (
    AGENT_NAME,
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
)
from gateway_client import create_mcp_client, load_gateway_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_mcp_client = None
_tools = None


async def get_tools():
    """Load Gateway tools once and cache them."""
    global _mcp_client, _tools
    
    if _tools is None:
        logger.info("Loading Gateway tools...")
        _mcp_client = await create_mcp_client()
        _tools = await load_gateway_tools(_mcp_client)
        logger.info(f"Loaded {len(_tools)} tools from Gateway")
        for tool in _tools:
            logger.info(f"  Tool: {tool.name}")
    
    return _tools


# Create FastAPI app
app = FastAPI(title="Scout Voice Agent - Local Test")

# CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("=" * 70)
    logger.info("Scout Voice Agent - LOCAL TEST VERSION")
    logger.info("=" * 70)
    logger.info(f"Region: {REGION}")
    logger.info(f"Model: {NOVA_MODEL_ID}")
    logger.info(f"Voice: {VOICE_ID}")
    logger.info("=" * 70)
    logger.info("Pre-loading Gateway tools...")
    await get_tools()
    logger.info("=" * 70)
    logger.info("Server ready!")
    logger.info("=" * 70)


@app.get("/ping")
async def ping():
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "agent": AGENT_NAME})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "agent": AGENT_NAME,
        "region": REGION,
        "model": NOVA_MODEL_ID,
        "environment": "local"
    })


@app.get("/get-websocket-url")
async def get_websocket_url(voice_id: str = "matthew"):
    """
    Return local WebSocket URL for testing.
    This endpoint exists for compatibility with the frontend,
    but always returns the local URL.
    """
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8080"))
    local_url = f"ws://{host}:{port}/ws?voice_id={voice_id}"
    
    return JSONResponse({
        "websocket_url": local_url,
        "expires_in": None,
        "environment": "local"
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for bi-directional Nova Sonic streaming.
    Simplified version for local testing.
    """
    await websocket.accept()

    # Get voice_id from query params
    voice_id = websocket.query_params.get("voice_id", VOICE_ID)
    logger.info(f"New connection from {websocket.client}, voice: {voice_id}")

    try:
        # Load Gateway tools
        tools = await get_tools()
        
        # Create Nova Sonic model
        model = BidiNovaSonicModel(
            region=REGION,
            model_id=NOVA_MODEL_ID,
            provider_config={
                "audio": {
                    "input_sample_rate": 16000,
                    "output_sample_rate": 16000,
                    "voice": voice_id,
                }
            },
        )

        # Create BidiAgent with Scout configuration
        agent = BidiAgent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        
        logger.info(f"BidiAgent created for {AGENT_NAME}")
        logger.info(f"Tools: {len(tools)} loaded from Gateway")
        logger.info("Starting bi-directional streaming...")

        # Log all events for debugging
        async def receive_wrapper():
            message = await websocket.receive_json()
            return message

        async def send_wrapper(message):
            # Log outgoing events
            if message.get("type") == "bidi_response_start":
                logger.info("➡️  bidi_response_start")
            elif message.get("type") == "bidi_transcript_event":
                role = message.get("role", "unknown")
                text = message.get("transcript", "")
                logger.info(f"➡️  {role.upper()}: {text}")
            
            await websocket.send_json(message)

        # Run the agent with WebSocket handlers
        await agent.run(
            receive_json=receive_wrapper,
            send_json=send_wrapper,
        )

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        logger.info("Connection closed")


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    logger.info("")
    logger.info("=" * 70)
    logger.info("LOCAL TEST SERVER")
    logger.info("=" * 70)
    logger.info(f"Starting server: python test_agent.py")
    logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    logger.info(f"React frontend should connect to: http://localhost:3000")
    logger.info("=" * 70)
    logger.info("")

    uvicorn.run(app, host=host, port=port)

