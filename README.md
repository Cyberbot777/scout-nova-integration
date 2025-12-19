# Scout Nova Voice Integration

Production-ready voice agent using **AWS official Strands BidiAgent pattern** with Amazon Nova Sonic for AgentCore Runtime deployment.

## Current Status

**Status:** Production-ready  
**Implementation:** AWS official pattern with bi-directional streaming  
**Deployment:** AgentCore Runtime ready

---

## Quick Start

### Local Development

**Option 1: React Frontend (Recommended)**
```bash
# Terminal 1: Start backend
cd strands-bidi
python server.py

# Terminal 2: Start React frontend
cd frontend
npm install
npm start
# Opens http://localhost:3000
```

**Option 2: Simple HTML Client (Quick Testing)**
```bash
# Terminal 1: Start backend
cd strands-bidi
python server.py

# Terminal 2: Start HTML client
cd strands-bidi
python client.py --ws-url ws://localhost:8080/ws
# Opens http://localhost:8000
```

Click "Start Conversation" and speak!

### AgentCore Deployment

```bash
cd strands-bidi

# Deploy to AgentCore
docker build -t scout-voice-agent .
docker push YOUR_ECR_REPO/scout-voice-agent:latest
bedrock-agentcore deploy

# Connect to deployed agent
python client.py --runtime-arn YOUR_RUNTIME_ARN
```

See [strands-bidi/README.md](./strands-bidi/README.md) for complete documentation.

---

## Architecture

```
client.html (Browser)
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

- **AWS Official Pattern** - Follows AWS reference implementation
- **Simplified Code** - 65% code reduction vs custom implementation
- **Modular Design** - Easy to adapt for other agents
- **Clean Interruptions** - Native Nova Sonic barge-in support
- **AgentCore Ready** - Zero code changes for deployment
- **Production Features** - Health checks, IMDS credentials, observability

---

## Repository Structure

```
scout-nova-integration/
├── strands-bidi/              # PRODUCTION VOICE AGENT BACKEND
│   ├── server.py              # FastAPI backend with BidiAgent
│   ├── client.py              # HTML client launcher (testing)
│   ├── client.html            # Simple HTML client (testing)
│   ├── websocket_helpers.py   # SigV4 authentication
│   ├── scout_config.py        # Scout configuration
│   ├── config.example.py      # Template for other agents
│   ├── gateway_client.py      # MCP Gateway integration
│   ├── Dockerfile             # Production deployment
│   ├── pyproject.toml         # Dependencies
│   └── README.md              # Complete documentation
│
├── frontend/                  # REACT FRONTEND (Production UI)
│   ├── src/
│   │   ├── VoiceAgent.js      # Main voice agent component
│   │   ├── helper/
│   │   │   ├── bidiEvents.js  # BidiAgent protocol helpers
│   │   │   ├── audioHelper.js # Audio processing
│   │   │   └── audioPlayer.js # Audio playback
│   │   └── components/
│   │       └── EventDisplay.js # Event log component
│   ├── package.json           # React dependencies
│   └── README.md              # Frontend documentation
│
└── ScoutAgent/                # Reference: Text-based agent
    ├── kwikie_agent.py        # Shows AgentCore deployment pattern
    └── test_agent.py          # Local testing
```

---

## Configuration

The agent is configured via `strands-bidi/scout_config.py`:

```python
AGENT_NAME = "Scout"
SYSTEM_PROMPT = """You are Scout, a helpful voice assistant..."""
GATEWAY_URL = "your-gateway-url"
VOICE_ID = "matthew"
```

### Adapting for Other Agents

1. Copy `config.example.py` to `my_agent_config.py`
2. Update AGENT_NAME, SYSTEM_PROMPT, GATEWAY_URL
3. Change import in `server.py` (line 26)
4. Deploy!

95% of the code is reusable - only the config file changes!

---

## Available Tools

Via AgentCore Gateway (MCP):

- **GetLoanDetails** - Get loan details from Hydra API
- **SnowflakeQuery** - Query broker pipeline data

Tools are automatically discovered and integrated via the Gateway.

---

## Testing

### Local Development with React Frontend
```bash
# Terminal 1: Backend
cd strands-bidi
python server.py

# Terminal 2: React Frontend
cd frontend
npm install
npm start
# Opens http://localhost:3000
```

### Local Development with HTML Client (Quick Test)
```bash
# Terminal 1: Backend
cd strands-bidi
python server.py

# Terminal 2: HTML Client
cd strands-bidi
python client.py --ws-url ws://localhost:8080/ws
# Opens http://localhost:8000
```

### AgentCore Local Testing
```bash
cd strands-bidi
bedrock-agentcore launch
python client.py --ws-url ws://localhost:8080/ws
```

### Production Deployment
```bash
cd strands-bidi
bedrock-agentcore deploy
python client.py --runtime-arn YOUR_RUNTIME_ARN
```

---

## Deployment Benefits

With AgentCore Runtime bi-directional streaming:
- Managed WebSocket infrastructure
- Automatic scaling
- AWS SigV4 authentication
- Health monitoring
- OpenTelemetry observability
- Production-grade reliability

**No code changes needed** - the same code runs locally and in production!

---

## Documentation

- [strands-bidi/README.md](./strands-bidi/README.md) - Complete voice agent docs
- [strands-bidi/MIGRATION.md](./strands-bidi/MIGRATION.md) - Old vs new comparison
- [strands-bidi/IMPLEMENTATION_SUMMARY.md](./strands-bidi/IMPLEMENTATION_SUMMARY.md) - What was built
- [PROJECT_STATUS.md](./PROJECT_STATUS.md) - Project history

---

## Technical Details

- **Region:** us-east-1
- **Model:** amazon.nova-sonic-v1:0
- **Voice:** matthew (en-US)
- **Protocol:** BidiAgent (not raw Nova Sonic)
- **Runtime:** AgentCore with bi-directional streaming

---

## Credits

Based on AWS official samples:
- https://aws.amazon.com/blogs/machine-learning/bi-directional-streaming-for-real-time-agent-interactions-now-available-in-amazon-bedrock-agentcore-runtime/
- https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/01-AgentCore-runtime/06-bi-directional-streaming/strands
