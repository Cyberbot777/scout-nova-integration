# AgentCore Deployment Strategy for Nova Voice Agent

## Overview

This document outlines the deployment strategy for the Scout Nova Voice Agent to AWS Bedrock AgentCore. The voice agent uses Nova Sonic bidirectional streaming, which presents unique challenges compared to standard HTTP-based agents.

---

## The Core Challenge

### Standard AgentCore Pattern (HTTP)

The `kwikie_agent.py` uses `BedrockAgentCoreApp` with the HTTP request/response pattern:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload: dict):
    # Receive request -> Process -> Yield responses
    prompt = payload.get("prompt", "")
    # ... agent logic ...
    yield {"response": "..."}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

**Characteristics:**
- Synchronous request/response cycle
- Client sends payload, agent yields streaming responses
- Connection closes after response completes
- `server_protocol: HTTP` in `.bedrock_agentcore.yaml`

### Voice Agent Pattern (WebSocket)

The `scout_nova_agent.py` uses persistent WebSocket connections:

```python
import websockets

async def websocket_handler(websocket):
    # Persistent bidirectional connection
    # Real-time audio streaming both directions
    async for message in websocket:
        # Process audio, send responses
        pass

async def main():
    async with websockets.serve(websocket_handler, "0.0.0.0", 8080):
        await asyncio.Future()  # Run forever
```

**Characteristics:**
- Persistent bidirectional connection
- Real-time audio streaming (input AND output simultaneously)
- Connection stays open for entire conversation
- Requires `server_protocol: WEBSOCKET` (if supported)

---

## Deployment Options

### Option 1: Native AgentCore WebSocket Support

**Try this first** - AgentCore may support WebSocket protocol natively.

**Steps:**
```bash
cd strands-bidi
agentcore configure
```

**What to look for:**
- If AgentCore detects `websockets.serve()` and offers `WEBSOCKET` protocol
- Check generated `.bedrock_agentcore.yaml` for `server_protocol: WEBSOCKET`

**If successful:**
```bash
agentcore launch
```

**Pros:**
- Full AgentCore integration (observability, scaling, management)
- Consistent with team standards

**Cons:**
- May not be supported yet

---

### Option 2: Hybrid Approach (HTTP + WebSocket)

Run both HTTP (for AgentCore) and WebSocket (for voice) in the same container.

**Modified `scout_nova_agent.py`:**

```python
#!/usr/bin/env python3
"""
Scout Nova Voice Agent - Hybrid AgentCore + WebSocket Deployment

Exposes:
- HTTP port 9000: AgentCore management endpoint
- WebSocket port 8080: Voice streaming
"""
import asyncio
import threading
import websockets
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# AgentCore HTTP app
app = BedrockAgentCoreApp()

# Import existing voice agent logic
from scout_config import AGENT_NAME, SYSTEM_PROMPT, REGION
from gateway_client import create_mcp_client, load_gateway_tools

# Global state
_ws_server = None
_agent = None
_mcp_client = None


@app.entrypoint
async def invoke(payload: dict):
    """
    HTTP endpoint for AgentCore.
    Used for health checks, status, and control commands.
    Voice streaming happens over WebSocket on port 8080.
    """
    command = payload.get("command", "status")
    
    if command == "status":
        return {
            "status": "running",
            "agent_name": AGENT_NAME,
            "websocket_port": 8080,
            "voice_endpoint": "ws://<host>:8080"
        }
    elif command == "health":
        return {"healthy": True}
    else:
        return {"error": f"Unknown command: {command}"}


async def websocket_handler(websocket):
    """
    Handle WebSocket voice connections.
    This is the main voice streaming logic.
    """
    global _agent, _mcp_client
    
    # Initialize agent if needed
    if _agent is None:
        _mcp_client = await create_mcp_client()
        tools = await load_gateway_tools(_mcp_client)
        # ... BidiAgent initialization ...
    
    # ... existing BidiAgent WebSocket logic ...
    # (Copy from current scout_nova_agent.py)


async def start_websocket_server():
    """Start the WebSocket server for voice streaming."""
    global _ws_server
    print(f"Starting WebSocket server on port 8080...")
    _ws_server = await websockets.serve(
        websocket_handler,
        "0.0.0.0",
        8080,
        ping_interval=30,
        ping_timeout=10
    )
    print("WebSocket server running on ws://0.0.0.0:8080")
    await _ws_server.wait_closed()


def run_websocket_in_thread():
    """Run WebSocket server in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_websocket_server())


if __name__ == "__main__":
    # Start WebSocket server in background thread
    ws_thread = threading.Thread(
        target=run_websocket_in_thread,
        daemon=True
    )
    ws_thread.start()
    print("WebSocket thread started")
    
    # Start AgentCore HTTP server (blocking)
    print("Starting AgentCore HTTP server on port 9000...")
    app.run(host="0.0.0.0", port=9000)
```

**Dockerfile for Hybrid:**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1

COPY . .

RUN uv pip install \
    boto3>=1.41.0 \
    strands-agents[bidi-all]>=1.18.0 \
    mcp>=1.0.0 \
    httpx-auth-awssigv4>=0.1.0 \
    websockets>=12.0 \
    python-dotenv>=1.0.0 \
    bedrock-agentcore>=1.0.0 \
    aws-opentelemetry-distro==0.12.2

RUN useradd -m -u 1000 bedrock_agentcore && \
    chown -R bedrock_agentcore:bedrock_agentcore /app
USER bedrock_agentcore

# Expose both ports
EXPOSE 9000
EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "scout_nova_agent.py"]
```

**Pros:**
- Works within AgentCore ecosystem
- AgentCore handles HTTP endpoint (health, status)
- WebSocket runs alongside for voice

**Cons:**
- More complex architecture
- Two protocols in one container

---

### Option 3: Standard Container Deployment (No AgentCore)

If AgentCore doesn't support WebSocket, deploy as a standard container.

**Dockerfile (WebSocket Only):**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1

COPY . .

RUN uv pip install \
    boto3>=1.41.0 \
    strands-agents[bidi-all]>=1.18.0 \
    mcp>=1.0.0 \
    httpx-auth-awssigv4>=0.1.0 \
    websockets>=12.0 \
    python-dotenv>=1.0.0

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["python", "scout_nova_agent.py"]
```

**Deployment Targets:**

| Service | WebSocket Support | Notes |
|---------|-------------------|-------|
| AWS ECS/Fargate + ALB | Yes | ALB supports WebSocket natively |
| AWS App Runner | Yes | Simpler than ECS |
| AWS EC2 | Yes | Full control |
| AWS API Gateway | Yes | WebSocket API type |

**ECS Task Definition Example:**

```json
{
  "family": "scout-nova-voice",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "scout-nova-agent",
      "image": "025066260073.dkr.ecr.us-east-1.amazonaws.com/scout-nova-voice:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "AWS_REGION", "value": "us-east-1"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/scout-nova-voice",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::025066260073:role/ecsTaskExecutionRole"
}
```

**ALB Configuration:**
- Target Group: Protocol = HTTP, Health check path = /health (add HTTP health endpoint)
- Listener: Port 80/443 -> Target Group
- ALB automatically upgrades HTTP to WebSocket when client requests it

**Pros:**
- Full control over deployment
- WebSocket works natively with ALB
- Standard AWS patterns

**Cons:**
- No AgentCore features (observability, scaling policies)
- Manual infrastructure management

---

## Recommended Path

### Step 1: Try AgentCore Native

```bash
cd strands-bidi
agentcore configure
```

Check if WebSocket is supported.

### Step 2: If Not Supported, Use Hybrid (Option 2)

Modify `scout_nova_agent.py` to include both HTTP and WebSocket.

### Step 3: If Hybrid Fails, Use Standard Container (Option 3)

Deploy to ECS/Fargate with ALB.

---

## Frontend Considerations

Regardless of deployment option, the frontend WebSocket URL needs to change:

| Environment | WebSocket URL |
|-------------|---------------|
| Local Development | `ws://localhost:8080` |
| AgentCore (if supported) | `wss://<agentcore-endpoint>:8080` |
| ECS/Fargate + ALB | `wss://<alb-dns-name>/ws` |

Update `frontend/src/VoiceAgent.js`:

```javascript
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8080';
```

---

## Security Considerations

### For Production Deployment

1. **TLS/SSL**: Always use `wss://` (WebSocket Secure) in production
2. **Authentication**: Add token-based auth to WebSocket handshake
3. **CORS**: Configure allowed origins
4. **Rate Limiting**: Prevent abuse of voice connections
5. **IAM Roles**: Use task roles for AWS service access

### WebSocket Authentication Example

```python
async def websocket_handler(websocket):
    # Check auth header during handshake
    auth_token = websocket.request_headers.get("Authorization")
    if not validate_token(auth_token):
        await websocket.close(4001, "Unauthorized")
        return
    
    # Proceed with voice session
    # ...
```

---

## Next Steps

1. [ ] Try `agentcore configure` to check WebSocket support
2. [ ] If not supported, implement Hybrid approach
3. [ ] Create Dockerfile for chosen approach
4. [ ] Test locally with Docker
5. [ ] Deploy to staging environment
6. [ ] Update frontend WebSocket URL
7. [ ] Production deployment

---

## References

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [AWS ECS with ALB WebSocket](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html)
- [Strands BidiAgent Documentation](https://strandsagents.com/latest/documentation/docs/)
- Scout Agent Reference: `ScoutAgent/kwikie_agent.py`

