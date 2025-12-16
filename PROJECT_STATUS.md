# Scout Nova Voice Integration - Status

**Last Updated:** December 15, 2025  
**Current State:** Production-ready with Strands BidiAgent  
**Status:** Fully functional voice agent with real-time tool integration

---

## Architecture

```
Frontend (React)
    ├─ Captures microphone audio (raw PCM)
    ├─ Sends Nova Sonic protocol events via WebSocket
    └─ ws://localhost:8080
           │
           ▼
    bidi_websocket_server.py (Python)
    ├─ Strands BidiAgent (manages Nova Sonic internally)
    ├─ Custom WebSocketInput/WebSocketOutput handlers
    ├─ Bridges raw WebSocket audio to BidiAgent
    ├─ System prompt from scout_config.py
    └─ MCP tools from gateway_client.py
           │
           ├─► Bedrock Nova Sonic (amazon.nova-sonic-v1:0)
           │    ├─ Speech-to-speech streaming
           │    ├─ Automatic interruption handling
           │    └─ Tool calling via BidiAgent
           │
           └─► AgentCore Gateway (MCP)
                  ├─ GetLoanDetails (Hydra queries)
                  └─ SnowflakeQuery (pipeline data)
```

### What Works
- Real-time voice input/output streaming
- Nova Sonic interruption (barge-in) feature
- Strands BidiAgent tool integration
- Scout system prompt and personality
- Gateway tool discovery and execution
- Modular agent configuration (AGENT_NAME parameter)
- Conversation continuity after interruptions
- Text transcript display in UI

### Key Features
- **Strands SDK First:** Uses BidiAgent with experimental Nova Sonic support
- **Custom I/O Handlers:** WebSocketInput/WebSocketOutput bridge raw audio
- **Tool Integration:** Automatic tool calling via MCP Gateway
- **Modular Design:** Agent identity configurable via scout_config.py
- **Production Ready:** Follows team standards for AgentCore deployment

---

## File Structure

```
scout-nova-integration/
├── agent/
│   ├── .venv/                       # Python virtual environment
│   ├── .env                         # AWS credentials (create from .env.example)
│   ├── .env.example                 # Template for credentials
│   ├── pyproject.toml               # Python dependencies (uv-managed)
│   ├── bidi_websocket_server.py     # Main: Strands BidiAgent WebSocket server
│   ├── scout_config.py              # Agent config: AGENT_NAME, SYSTEM_PROMPT, etc.
│   ├── gateway_client.py            # MCP client + AWS SigV4 auth
│   ├── scout_voice_agent.py         # AgentCore deployable version
│   ├── test_agent.py                # Local CLI test agent
│   └── voice_server.py              # Legacy: Direct Bedrock (kept for reference)
│
├── frontend/                        # React voice UI
│   ├── src/
│   │   ├── VoiceAgent.js            # Voice capture/playback/UI
│   │   └── helper/audioPlayer.js    # Audio worklet processor
│   ├── package.json                 # npm dependencies
│   └── public/                      # Static assets
│
├── ScoutAgent/                      # Reference: Production text agent
│   ├── kwikie_agent.py              # Shows AgentCore deployment pattern
│   └── test_agent.py                # Local testing pattern
│
└── PROJECT_STATUS.md                # This file
```

---

## Modular Design

The agent is now fully modular and can be adapted for any Strands agent:

### Configuration File (scout_config.py)
```python
AGENT_NAME = "Scout"  # Used throughout logs and UI
SYSTEM_PROMPT = """You are Scout, a helpful voice assistant..."""
GATEWAY_URL = "https://..."
REGION = "us-east-1"
VOICE_ID = "matthew"
```

### To Create a New Voice Agent
1. Copy `scout_config.py` to `my_agent_config.py`
2. Update `AGENT_NAME`, `SYSTEM_PROMPT`, `GATEWAY_URL`
3. Update import in `bidi_websocket_server.py`:
   ```python
   from my_agent_config import AGENT_NAME, SYSTEM_PROMPT, ...
   ```
4. Restart server - that's it!

The WebSocket server, I/O handlers, and BidiAgent logic are completely generic.

---

## Running the Agent

### Development (Local Testing)
```bash
# Terminal 1: Start WebSocket server
cd agent
source .venv/Scripts/activate  # or .venv\Scripts\activate on Windows
python bidi_websocket_server.py --port 8080

# Terminal 2: Start frontend
cd frontend
npm start
# Opens http://localhost:3000
```

### Test Without UI
```bash
cd agent
source .venv/Scripts/activate
python test_agent.py  # CLI text chat to test tools
```

---

## Recent Improvements

1. **Interruption Handling** - Nova Sonic barge-in working flawlessly
2. **Tool Execution** - GetLoanDetails and SnowflakeQuery fully functional
3. **Modular Config** - AGENT_NAME parameter for easy agent swapping
4. **Error Recovery** - Graceful handling of tool errors and session cleanup
5. **UI Text Display** - Streaming transcript with proper content management

---

## Dependencies

All managed via `pyproject.toml` and installed in `agent/.venv`:
- `strands-agents[bidi-all]>=1.18.0` - BidiAgent + Nova Sonic support
- `websockets>=13.0` - WebSocket server
- `boto3` - AWS SDK
- `mcp>=1.1.2` - Model Context Protocol client
- `httpx-auth-awssigv4` - AWS SigV4 authentication for Gateway
- `python-dotenv` - Environment variable management

Install with:
```bash
cd agent
pip install -e .
```

---

## Known Issues

1. **GetLoanDetails requires queries array** - Lambda only accepts batch format. System prompt updated to enforce this.
2. **Tool names show as "unknown"** - Frontend doesn't extract tool name from `tool_use_stream` events. Tools work correctly, just display issue.
3. **Session cleanup traceback** - Harmless `InvalidStateError` on session end due to aggressive cancellation. Does not affect functionality.

---

**Status:** Production-ready Strands BidiAgent implementation. Follows team standards and ready for AgentCore deployment.

