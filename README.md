# Scout Nova Voice Integration

Two Nova Sonic voice agent implementations for A/B testing and comparison.

## Current Status

**Status:** Both implementations functional and ready for testing  
**Purpose:** Compare Direct Bedrock vs Strands BidiAgent approaches  
**Goal:** Determine optimal implementation based on user experience metrics

See [COMPARISON.md](./COMPARISON.md) for detailed comparison and testing framework.

---

## Quick Start

### 1. Install Dependencies

**Backend (Python):**
```bash
cd agent
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac
pip install -e .
```

**Frontend (React):**
```bash
cd frontend
npm install
```

### 2. Configure AWS Credentials

```bash
cd agent
cp env.example .env
# Edit .env with your AWS credentials:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_SESSION_TOKEN=...  (if using SSO)
```

### 3. Start Services

**Backend (Terminal 1):**
```bash
cd agent
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
python bidi_websocket_server.py --port 8080
```

**Frontend (Terminal 2):**
```bash
cd frontend
npm start
# Opens http://localhost:3000
```

### 4. Test Voice

1. Open http://localhost:3000
2. Click "Start Conversation"
3. Allow microphone access
4. Speak: "Hello Scout, show me my pipeline for user 12673"
5. Scout responds with voice and executes tools
6. Try interrupting - barge-in works seamlessly!

---

## Architecture

### System Overview

```
Frontend (React)
    ├─ Microphone capture (16kHz PCM)
    ├─ Audio playback (24kHz PCM)
    └─ WebSocket → ws://localhost:8080
           │
           ▼
    bidi_websocket_server.py
    ├─ Custom WebSocketInput/WebSocketOutput handlers
    ├─ Bridges raw audio to BidiAgent
    └─ Strands BidiAgent
           ├─ Manages Nova Sonic protocol internally
           ├─ Real-time interruption handling
           ├─ Automatic tool calling
           └─ System prompt from scout_config.py
           │
           ├─► Amazon Nova Sonic (amazon.nova-sonic-v1:0)
           │    └─ Speech-to-speech streaming
           │
           └─► AgentCore Gateway (MCP)
                  ├─ GetLoanDetails (Hydra queries)
                  └─ SnowflakeQuery (pipeline data)
```

### Key Components

- **Strands BidiAgent:** Experimental Nova Sonic support with built-in tool handling
- **Custom I/O Handlers:** WebSocketInput/WebSocketOutput bridge WebSocket to BidiAgent
- **Modular Config:** AGENT_NAME parameter makes it easy to adapt to other agents
- **MCP Gateway:** Secure access to backend Lambda functions via AgentCore

---

## Configuration

| File | Purpose |
|------|---------|
| `agent/scout_config.py` | Agent identity (AGENT_NAME), system prompt, Gateway URL, model config |
| `agent/gateway_client.py` | MCP client + AWS SigV4 auth for AgentCore Gateway |
| `agent/.env` | AWS credentials (create from `.env.example`) |

### Modular Agent Design

The agent identity is controlled by `AGENT_NAME` in `scout_config.py`:

```python
AGENT_NAME = "Scout"  # Used in logs, UI, and session metadata
SYSTEM_PROMPT = """You are Scout, a helpful voice assistant..."""
```

To create a new voice agent, simply copy `scout_config.py`, update these values, and change the import in `bidi_websocket_server.py`. All WebSocket and audio handling logic is agent-agnostic.

---

## Available Tools

Accessed via AgentCore Gateway (MCP):

| Tool | Lambda | Purpose | Required Parameters |
|------|--------|---------|---------------------|
| `GetLoanDetails` | HydraQueryLambda | Get loan details from Hydra | `queries` array with `loanId` + `queryName` |
| `SnowflakeQuery` | SnowflakeQueryAsyncLambda | Query broker pipeline data | `sys_user_id` + `query_type` or `query_types` |

**Important Notes:**
- GetLoanDetails requires `queries` array format (even for single loans)
- SnowflakeQuery requires `sys_user_id` for broker identification
- Tools are automatically discovered and integrated via MCP Gateway

---

## Files

```
scout-nova-integration/
├── agent/
│   ├── bidi_websocket_server.py # Main: WebSocket server with Strands BidiAgent
│   ├── scout_config.py          # Agent config: AGENT_NAME, SYSTEM_PROMPT, etc.
│   ├── gateway_client.py        # MCP client + AWS SigV4 authentication
│   ├── scout_voice_agent.py     # AgentCore deployable version (future)
│   ├── test_agent.py            # Local CLI test (text-based)
│   ├── voice_server.py          # Legacy: Direct Bedrock (kept for reference)
│   ├── pyproject.toml           # Python dependencies
│   └── .env.example             # Template for AWS credentials
│
├── frontend/                    # React voice UI
│   ├── src/
│   │   ├── VoiceAgent.js        # Main voice UI component
│   │   └── helper/              # Audio processing helpers
│   └── package.json             # npm dependencies
│
├── ScoutAgent/                  # Reference: Production text agent
│   ├── kwikie_agent.py          # AgentCore deployment pattern
│   └── test_agent.py            # Local testing pattern
│
├── README.md                    # This file
└── PROJECT_STATUS.md            # Detailed architecture and status
```

---

## Testing

### Test 1: CLI Text Agent (No Voice)
```bash
cd agent
source .venv/Scripts/activate
python test_agent.py
# Test tools via text chat - no voice required
```

### Test 2: Full Voice UI
```bash
# Terminal 1: Start backend
cd agent
source .venv/Scripts/activate
python bidi_websocket_server.py --port 8080

# Terminal 2: Start frontend
cd frontend
npm start

# Browser: http://localhost:3000
```

### Test Scenarios

1. **Basic conversation:** "Hello Scout, what can you help me with?"
2. **Pipeline query:** "Show me my active pipeline for user 12673"
3. **Loan details:** "Get details on loan number 41490"
4. **Interruption:** Start talking while Scout is speaking (barge-in)

---

## Troubleshooting

### "AWS credentials not found"
- Check `agent/.env` exists and has valid credentials
- Verify credentials with: `aws sts get-caller-identity`

### "Connection lost unexpectedly"
- Check voice_server.py is running
- Frontend should connect to `ws://localhost:8080`
- Check browser console for WebSocket errors

### "Tool execution error"
- Verify Gateway URL in `scout_config.py`
- Check AWS credentials have AgentCore permissions
- See logs in voice_server.py output

---

## Features

- **Real-time Voice Streaming:** Low-latency speech-to-speech via Nova Sonic
- **Interruption Support:** Natural barge-in allows users to interrupt Scout
- **Tool Integration:** Automatic tool calling via Strands BidiAgent
- **Modular Design:** Easy to adapt to other agents via config file
- **Production Ready:** Follows team standards for AgentCore deployment
- **Text Transcript:** UI displays streaming conversation text
- **Error Recovery:** Graceful handling of tool failures and session cleanup

---

## Resources

- **Strands SDK:** https://strandsagents.com/latest/documentation/docs/
- **Nova Sonic:** Amazon Bedrock speech-to-speech model
- **AgentCore Gateway:** MCP-based tool access
- **Scout Agent:** See `ScoutAgent/` folder for production text agent

---

**Region:** us-east-1 (all resources)  
**Model:** amazon.nova-sonic-v1:0  
**Voice:** Matthew (en-US)
