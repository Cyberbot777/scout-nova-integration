# Scout Voice Agent - AgentCore Runtime with Bi-directional Streaming

Production-ready voice agent using **AWS official Strands BidiAgent pattern** with Amazon Nova Sonic.

## Architecture

```
Frontend (HTML/JS)
    |
    | WebSocket (BidiAgent protocol)
    v
server.py (FastAPI)
    |
    |--> /ping (health check)
    |--> /ws (bi-directional streaming)
    |
    v
BidiAgent (Strands SDK)
    |
    |--> BidiNovaSonicModel (Nova Sonic)
    |--> Gateway Tools (MCP)
    |--> System Prompt (scout_config.py)
```

## Key Features

- **Simplified AWS Pattern**: Direct WebSocket pass-through to BidiAgent (no custom I/O handlers)
- **Clean Interruptions**: Native Nova Sonic interruption support
- **AgentCore Ready**: Deployable to AgentCore Runtime with bi-directional streaming
- **Modular Configuration**: Easy to adapt for any agent via config file
- **Production Features**: IMDS credential refresh, health checks, observability

## Quick Start

### Two Server Files

This project has **two server files**:

1. **`test_agent.py`** - For local development and testing
   - Simplified setup, no IMDS, no credential refresh
   - Direct WebSocket connection
   - Use this for local testing with React frontend

2. **`server.py`** - For AgentCore production deployment
   - Full production features (IMDS, credential refresh, pre-signed URLs)
   - Optimized for AgentCore Runtime
   - Use this for deploying to AWS

### Local Development

```bash
cd strands-bidi

# Create virtual environment
uv venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate     # Mac/Linux

# Install dependencies
uv pip install -e .

# Run the LOCAL TEST server
python test_agent.py
```

The server will be available at `ws://localhost:8080/ws`. Use the React frontend in `../frontend` to connect.

## File Structure

```
strands-bidi/
├── server.py                 # Main server (FastAPI + BidiAgent)
├── client.py                 # Client launcher (generates pre-signed URLs)
├── client.html               # Voice interface (HTML/JS)
├── websocket_helpers.py      # SigV4 URL signing
├── scout_config.py           # Scout-specific configuration
├── config.example.py         # Template for other agents
├── gateway_client.py         # MCP Gateway integration
├── pyproject.toml            # Dependencies
├── Dockerfile                # AgentCore deployment
├── env.example               # Environment template
└── README.md                 # This file
```

## Adapting for Your Agent

### 1. Create Your Config File

```bash
cp config.example.py my_agent_config.py
```

Edit `my_agent_config.py`:

```python
AGENT_NAME = "MyAgent"
SYSTEM_PROMPT = """Your custom system prompt here..."""
GATEWAY_URL = "your-gateway-url"
VOICE_ID = "matthew"  # or joanna, etc.
```

### 2. Update Server Import

In `server.py`, line 24:

```python
# Change this:
from scout_config import (
    AGENT_NAME,
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
)

# To this:
from my_agent_config import (
    AGENT_NAME,
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
)
```

### 3. Update Gateway Client (if needed)

If your agent uses different tools, modify `gateway_client.py` to load your tools.

### 4. Deploy

That's it! The entire voice infrastructure is reusable. Just swap the config file.

## How It Works

### The AWS Official Pattern

This implementation follows the **AWS official Strands BidiAgent pattern** from:
https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/01-AgentCore-runtime/06-bi-directional-streaming/strands

**Key simplification**: BidiAgent accepts WebSocket methods directly!

```python
# NO custom I/O handlers needed
agent = BidiAgent(
    model=BidiNovaSonicModel(...),
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)

# Direct WebSocket pass-through
await agent.run(
    inputs=[websocket.receive_json],
    outputs=[websocket.send_json]
)
```

### Protocol: BidiAgent Events

The frontend and backend communicate using **BidiAgent protocol** (not Nova Sonic protocol):

**Input Events** (Frontend -> Server):
```javascript
{
  "type": "bidi_audio_input",
  "audio": "base64_pcm_audio...",
  "format": "pcm",
  "sample_rate": 16000,
  "channels": 1
}
```

**Output Events** (Server -> Frontend):
```javascript
// Audio output
{
  "type": "bidi_audio_stream",
  "audio": "base64_pcm_audio..."
}

// Transcript
{
  "type": "bidi_transcript_stream",
  "role": "assistant",
  "text": "Hello, how can I help you?"
}

// Interruption
{
  "type": "bidi_interruption",
  "reason": "user_spoke"
}

// Tool use
{
  "type": "tool_use_stream",
  "current_tool_use": {
    "name": "GetLoanDetails",
    "input": {...}
  }
}
```

### Interruption Support

Clean interruptions work because:
- BidiAgent internally handles `bidi_interruption` events
- Nova Sonic detects when user speaks during assistant response
- Audio playback is automatically cleared
- Conversation continues naturally

This is all handled by the Strands SDK - no custom code needed!

## Configuration Options

### Environment Variables

```bash
# AWS Credentials (for local development)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Server Configuration
HOST=0.0.0.0
PORT=8080
```

### Nova Sonic Voices

Available voice IDs:
- `matthew` (male, US English)
- `joanna` (female, US English)
- `amy` (female, UK English)

Specify in config or via URL query param: `?voice_id=matthew`

## Deployment

### Local Testing

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Start client (opens browser)
python client.py --ws-url ws://localhost:8080/ws
```

### AgentCore Deployment

**Use `server.py` for production AgentCore deployment:**

```bash
cd strands-bidi

# Configure AgentCore (interactive)
agentcore configure

# Deploy to AgentCore
agentcore launch

# Check status
agentcore invoke '{"prompt": "test"}'

# View logs
agentcore logs --follow
```

**The production server runs on port 8080 with:**
- `GET /ping` - Health check (AgentCore requirement)
- `GET /health` - Extended health check
- `GET /get-websocket-url` - Generates pre-signed WebSocket URLs with SigV4 auth
- `WS /ws` - Bi-directional streaming endpoint

**Frontend configuration for deployed agent:**

Update `frontend/.env`:
```bash
REACT_APP_API_URL=https://runtime.bedrock-agentcore.us-east-1.amazonaws.com/agents/YOUR-AGENT-ID
```

The React frontend will call `/get-websocket-url` to get an authenticated WebSocket URL, then connect to it.

**AgentCore handles:**
- Automatic scaling
- Health monitoring
- Observability and metrics
- Infrastructure management

## Troubleshooting

### "Failed to connect"
- Check AWS credentials are configured
- Verify Gateway URL is accessible
- Check runtime ARN is correct
- Ensure pre-signed URL hasn't expired

### "Microphone access denied"
- Browser needs HTTPS or localhost
- Grant microphone permissions in browser

### "No audio output"
- Check browser audio isn't muted
- Verify Nova Sonic model is available in your region
- Check network console for WebSocket errors

### "Tools not working"
- Verify Gateway URL in config
- Check MCP client can connect to Gateway
- Review server logs for tool execution errors
