# Scout Nova Voice Integration

Voice-enabled broker assistant using Amazon Nova Sonic for speech-to-speech conversation with Scout's loan pipeline tools.

## Current Status

**Working:** Voice conversation with Scout system prompt and Gateway tool integration  
**Architecture:** Direct Bedrock API (temporary)  
**Next:** Refactor to Strands BidiAgent (proper SDK approach)

See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for detailed status and roadmap.

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
source .venv/Scripts/activate
python voice_server.py --port 8080
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
4. Speak: "Hello, what can you help me with?"
5. Agent responds with voice!

---

## Architecture

### Current (Working)

```
Frontend → WebSocket → voice_server.py → Bedrock Nova Sonic
                              ↓
                        Gateway Tools (MCP)
```

### Target (Strands SDK)

```
Frontend → WebSocket → scout_voice_agent.py → BidiAgent → Nova Sonic
                              ↓
                        Gateway Tools (built-in)
```

---

## Configuration

| File | Purpose |
|------|---------|
| `agent/scout_config.py` | System prompt + constants |
| `agent/gateway_client.py` | MCP client + AWS SigV4 auth |
| `agent/.env` | AWS credentials (create from `.env.example`) |

**Scout System Prompt** is defined in `scout_config.py` and includes:
- Tool descriptions (SnowflakeQuery, GetLoanDetails)
- Briefing structure
- Response formatting rules

---

## Available Tools

Accessed via AgentCore Gateway (MCP):

| Tool | Lambda | Purpose |
|------|--------|---------|
| `supervisorAgent` | HydraQueryLambda | Query loan details from Hydra GraphQL |
| `SnowflakeQuery` | SnowflakeQueryAsyncLambda | Query loan pipeline data |

**Note:** `sysUserId` parameter required for Snowflake queries.

---

## Files

```
scout-nova-integration/
├── agent/
│   ├── voice_server.py          # Current: Working server (direct Bedrock)
│   ├── scout_voice_agent.py     # Target: Strands BidiAgent version
│   ├── scout_config.py          # System prompt + config
│   ├── gateway_client.py        # MCP + SigV4 auth
│   ├── test_nova_basic.py       # Test: Nova Sonic only
│   └── test_nova_with_tools.py  # Test: Nova + tools
│
├── frontend/                    # React voice UI
│   └── src/VoiceAgent.js        # Voice capture/playback
│
├── ScoutAgent/                  # Reference: Production text agent
│   └── kwikie_agent.py          # MCP + tool patterns
│
└── PROJECT_STATUS.md            # Detailed status + roadmap
```

---

## Testing

### Test 1: Basic Nova Sonic
```bash
cd agent
python test_nova_basic.py
# CLI voice test without tools
```

### Test 2: Nova + Tools
```bash
cd agent
python test_nova_with_tools.py
# Verifies Gateway tools load
```

### Test 3: Full Voice UI
```bash
# Terminal 1
cd agent && python voice_server.py --port 8080

# Terminal 2
cd frontend && npm start

# Browser: http://localhost:3000
```

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

## Next Steps

See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for:
- Refactoring to Strands BidiAgent
- Making the integration modular
- Tool execution improvements
- Production deployment

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
