#!/usr/bin/env python3
"""
Scout Voice Agent - PRODUCTION AGENTCORE DEPLOYMENT

This is the PRODUCTION server for AWS AgentCore deployment.

Features:
- HTTP /ping endpoint for health checks
- WebSocket /ws endpoint for bi-directional voice streaming
- Pre-signed URL generation with AWS SigV4 authentication
- IMDS credential refresh for production EC2/Fargate deployment
- Scout system prompt and Gateway tools integration

For local testing, use test_agent.py instead.
"""
import logging
import uvicorn
import os
import asyncio
import requests
from datetime import datetime
from contextlib import asynccontextmanager
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
from websocket_helpers import create_presigned_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_credential_refresh_task = None
_mcp_client = None
_tools = None


def get_imdsv2_token():
    """Get IMDSv2 token for secure metadata access."""
    try:
        response = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2,
        )
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None


def get_credentials_from_imds():
    """Retrieve IAM role credentials from EC2 IMDS (tries IMDSv2 first, falls back to IMDSv1)."""
    result = {
        "success": False,
        "credentials": None,
        "role_name": None,
        "method_used": None,
        "error": None,
    }

    try:
        token = get_imdsv2_token()
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        result["method_used"] = "IMDSv2" if token else "IMDSv1"

        role_response = requests.get(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            headers=headers,
            timeout=2,
        )

        if role_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve IAM role: HTTP {role_response.status_code}"
            )
            return result

        role_name = role_response.text.strip()
        result["role_name"] = role_name

        creds_response = requests.get(
            f"http://169.254.169.254/latest/meta-data/iam/security-credentials/{role_name}",
            headers=headers,
            timeout=2,
        )

        if creds_response.status_code != 200:
            result["error"] = (
                f"Failed to retrieve credentials: HTTP {creds_response.status_code}"
            )
            return result

        credentials = creds_response.json()
        result["success"] = True
        result["credentials"] = {
            "AccessKeyId": credentials.get("AccessKeyId"),
            "SecretAccessKey": credentials.get("SecretAccessKey"),
            "Token": credentials.get("Token"),
            "Expiration": credentials.get("Expiration"),
        }

    except Exception as e:
        result["error"] = str(e)

    return result


async def refresh_credentials_from_imds():
    """Background task to refresh credentials from IMDS."""
    logger.info("Starting credential refresh task")

    while True:
        try:
            imds_result = get_credentials_from_imds()

            if imds_result["success"]:
                creds = imds_result["credentials"]

                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

                logger.info(f"✅ Credentials refreshed ({imds_result['method_used']})")

                try:
                    expiration = datetime.fromisoformat(
                        creds["Expiration"].replace("Z", "+00:00")
                    )
                    now = datetime.now(expiration.tzinfo)
                    time_until_expiration = (expiration - now).total_seconds()
                    refresh_interval = min(max(time_until_expiration - 300, 60), 3600)
                    logger.info(f"   Next refresh in {refresh_interval:.0f}s")
                except Exception:
                    refresh_interval = 3600

                await asyncio.sleep(refresh_interval)
            else:
                logger.error(f"Failed to refresh credentials: {imds_result['error']}")
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Credential refresh task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in credential refresh: {e}")
            await asyncio.sleep(300)


async def get_tools():
    """Get or initialize Gateway tools (singleton pattern)."""
    global _mcp_client, _tools
    
    if _tools is None:
        logger.info("Loading Gateway tools...")
        _mcp_client = create_mcp_client()
        _tools = await load_gateway_tools(_mcp_client)
        logger.info(f"Loaded {len(_tools)} tools from Gateway")
        for tool in _tools:
            spec = getattr(tool, 'tool_spec', {})
            logger.info(f"  Tool: {spec.get('name', 'unknown')}")
    
    return _tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global _credential_refresh_task

    # Startup
    logger.info("=" * 70)
    logger.info(f"{AGENT_NAME} Voice Agent - Starting...")
    logger.info("=" * 70)
    logger.info(f"Region: {REGION}")
    logger.info(f"Model: {NOVA_MODEL_ID}")
    logger.info(f"Voice: {VOICE_ID}")
    logger.info("=" * 70)

    # Check for credentials
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.info("Using credentials from environment (local mode)")
    else:
        logger.info("Fetching credentials from EC2 IMDS...")
        imds_result = get_credentials_from_imds()

        if imds_result["success"]:
            creds = imds_result["credentials"]
            os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
            os.environ["AWS_SESSION_TOKEN"] = creds["Token"]

            logger.info(f"Credentials loaded ({imds_result['method_used']})")

            _credential_refresh_task = asyncio.create_task(
                refresh_credentials_from_imds()
            )
            logger.info("Credential refresh task started")
        else:
            logger.error(f"Failed to fetch credentials: {imds_result['error']}")
    
    # Pre-load tools at startup
    try:
        await get_tools()
    except Exception as e:
        logger.error(f"Failed to load tools at startup: {e}")

    logger.info("=" * 70)
    logger.info("Server ready!")
    logger.info("=" * 70)

    yield

    # Shutdown
    logger.info("Shutting down...")

    if _credential_refresh_task and not _credential_refresh_task.done():
        _credential_refresh_task.cancel()
        try:
            await _credential_refresh_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=f"{AGENT_NAME} Voice Agent - Strands BidiAgent",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping():
    """Health check endpoint required by AgentCore Runtime."""
    return JSONResponse({"status": "ok", "agent": AGENT_NAME})


@app.get("/health")
async def health_check():
    """Additional health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "agent": AGENT_NAME,
        "region": REGION,
        "model": NOVA_MODEL_ID
    })


@app.get("/get-websocket-url")
async def get_websocket_url(voice_id: str = "matthew"):
    """
    Generate a pre-signed WebSocket URL for connecting to AgentCore.
    The frontend calls this endpoint to get a valid authenticated URL.
    """
    try:
        # Check if running in AgentCore (production)
        agentcore_runtime_id = os.getenv("AGENTCORE_RUNTIME_ID", "ScoutVoice-BmhNAcH9IQ")
        is_production = os.getenv("DOCKER_CONTAINER") == "1"
        
        if is_production:
            # Production: Return pre-signed AgentCore URL
            base_url = f"wss://runtime.bedrock-agentcore.{REGION}.amazonaws.com/agents/{agentcore_runtime_id}/ws"
            
            # Add voice_id to the base URL
            if "?" in base_url:
                base_url += f"&voice_id={voice_id}"
            else:
                base_url += f"?voice_id={voice_id}"
            
            # Generate pre-signed URL
            signed_url = create_presigned_url(
                base_url=base_url,
                region=REGION,
                service="bedrock-agentcore",
                expires=3600  # 1 hour
            )
            
            return JSONResponse({
                "websocket_url": signed_url,
                "expires_in": 3600,
                "environment": "production"
            })
        else:
            # Local development: Return local URL
            host = os.getenv("HOST", "localhost")
            port = int(os.getenv("PORT", "8080"))
            local_url = f"ws://{host}:{port}/ws?voice_id={voice_id}"
            
            return JSONResponse({
                "websocket_url": local_url,
                "expires_in": None,
                "environment": "local"
            })
            
    except Exception as e:
        logger.error(f"Error generating WebSocket URL: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for bi-directional Nova Sonic streaming.
    This is the endpoint AgentCore Runtime connects to.
    
    Uses the simplified AWS pattern - no custom I/O handlers needed!
    BidiAgent.run() accepts websocket.receive_json and websocket.send_json directly.
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
                    "output_sample_rate": 16000,  # Nova Sonic outputs at 16kHz
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

        # Wrap WebSocket I/O with selective logging (only important events)
        async def logged_receive_json():
            data = await websocket.receive_json()
            event_type = data.get("type", "unknown")
            
            # Only log important events, skip audio chunks
            if event_type not in ["bidi_audio_input"]:
                logger.info(f"⬅️  {event_type}: {str(data)[:150]}")
            
            return data
        
        async def logged_send_json(data):
            event_type = data.get("type", "unknown")
            
            # Only log important events, skip audio chunks
            if event_type == "bidi_transcript_stream":
                text = data.get("text", data.get("transcript", ""))
                role = data.get("role", "assistant").upper()
                logger.info(f"➡️  {role}: {text}")
            elif event_type == "tool_use_stream":
                tool_name = data.get("current_tool_use", {}).get("name", "unknown")
                logger.info(f"🔧 TOOL: {tool_name}")
            elif event_type == "tool_result":
                tool_name = data.get("tool_result", {}).get("name", "unknown")
                logger.info(f"✅ TOOL RESULT: {tool_name}")
            elif event_type in ["bidi_response_start", "bidi_response_complete"]:
                logger.info(f"➡️  {event_type}")
            # Skip bidi_audio_stream - too noisy
            
            await websocket.send_json(data)
        
        # Direct WebSocket pass-through to BidiAgent with logging
        await agent.run(
            inputs=[logged_receive_json],
            outputs=[logged_send_json]
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
    logger.info("For local testing:")
    logger.info(f"   python server.py")
    logger.info(f"   WebSocket endpoint: ws://{host}:{port}/ws")
    logger.info("")
    logger.info("For AgentCore deployment:")
    logger.info(f"   Deploy with Dockerfile, endpoint will be /ws")
    logger.info("")

    uvicorn.run(app, host=host, port=port)

