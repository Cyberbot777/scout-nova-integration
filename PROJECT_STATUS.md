# Scout Nova Voice Integration - Status

**Last Updated:** December 15, 2025  
**Current State:** Working prototype with direct Bedrock API  
**Goal:** Refactor to use Strands BidiAgent (proper SDK approach)

---

## Current Architecture

```
Frontend (React)
    ├─ Captures microphone audio
    ├─ Sends Nova Sonic protocol events
    └─ WebSocket → ws://localhost:8080
           │
           ▼
    voice_server.py (Python)
    ├─ Direct Bedrock Nova Sonic API ⚠️ (not using Strands SDK)
    ├─ Injects Scout system prompt from scout_config.py
    ├─ Manual tool execution via gateway_client.py
    └─ Forwards responses back to frontend
           │
           ├─► Bedrock Nova Sonic (amazon.nova-sonic-v1:0)
           └─► AgentCore Gateway (MCP)
                  ├─ supervisorAgent
                  └─ SnowflakeQuery
```

### What Works ✅
- Voice input/output streaming
- Scout system prompt injection
- Tool discovery (2 Gateway tools loaded)
- Manual tool execution (basic - needs fixing)
- Full conversation flow

### Problem ⚠️
**Not using Strands SDK** - We're using direct Bedrock API instead of `BidiAgent`. This violates team "Strands SDK first" standards.

---

## Target Architecture (Strands SDK)

```
Frontend (React)
    ├─ Sends RAW AUDIO BYTES (not Nova Sonic events)
    └─ WebSocket → ws://localhost:8080
           │
           ▼
    scout_voice_agent.py (Python)
    ├─ Strands BidiAgent ✓
    │   ├─ Manages Nova Sonic protocol internally
    │   ├─ Built-in tool handling
    │   └─ Automatic response streaming
    ├─ Custom WebSocket I/O handler
    ├─ Uses scout_config.py (system prompt)
    └─ Uses gateway_client.py (MCP tools)
```

### Why This Is Better
- **Strands SDK maintains the Nova Sonic protocol** (not us)
- **Tool execution built-in** (no manual handling)
- **Cleaner code** (abstracts complexity)
- **Aligns with team standards** (same pattern as kwikie_agent.py)
- **Future-proof** (automatic updates from Strands)

---

## File Structure

```
scout-nova-integration/
├── agent/
│   ├── .venv/                       # Python virtual environment
│   ├── .env                         # AWS credentials (create from .env.example)
│   ├── pyproject.toml               # Dependencies
│   ├── scout_config.py              # System prompt + constants
│   ├── gateway_client.py            # MCP client + SigV4 auth
│   ├── voice_server.py              # Current working server (direct Bedrock)
│   └── scout_voice_agent.py         # Target: Strands BidiAgent version
│
├── frontend/                        # React voice UI
│   └── src/VoiceAgent.js            # Voice capture/playback
│
└── ScoutAgent/                      # Reference: Production text agent
    └── kwikie_agent.py              # Shows proper MCP + tools pattern
```

---

## Next Steps

### 1. Research BidiAgent Custom I/O (30 min)
- Investigate how `BidiAudioIO` works internally
- Determine if we can create custom I/O handler for WebSocket
- Check Strands docs for WebSocket examples

### 2. Update Frontend (15 min)
**Change:** Send raw PCM audio bytes instead of Nova Sonic events
- Frontend currently wraps audio in Nova Sonic protocol
- BidiAgent manages protocol internally - just needs raw audio
- Simpler frontend code

### 3. Implement scout_voice_agent.py (60 min)
```python
# Proper Strands SDK approach
from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel

# Custom WebSocket I/O that feeds raw audio to BidiAgent
class WebSocketAudioIO:
    async def input(self):
        # Yield raw audio bytes from WebSocket
        
    async def output(self, audio_chunk):
        # Send audio bytes to WebSocket

agent = BidiAgent(
    model=BidiNovaSonicModel(...),
    tools=gateway_tools,
    system_prompt=SYSTEM_PROMPT
)

await agent.run(
    inputs=[websocket_audio_io.input()],
    outputs=[websocket_audio_io.output()]
)
```

### 4. Test Tool Execution
- Fix tool calling (current implementation has bugs)
- Verify `sysUserId` is passed correctly
- Test end-to-end: voice → tool call → voice response

### 5. Make It Modular
- Extract agent config to separate file
- Make voice_server accept any agent configuration
- Document how to add voice to any Strands agent

---

## Testing Commands

```bash
# Start backend
cd agent
source .venv/Scripts/activate
python voice_server.py --port 8080

# Start frontend (separate terminal)
cd frontend
npm start
# Opens http://localhost:3000
```

---

## Key Decisions Needed

1. **Proceed with Strands refactor?** (Recommended: Yes)
2. **Keep voice_server.py as fallback?** (Recommended: Yes, until Strands version works)
3. **Timeline?** Can have working Strands version in ~2 hours

---

## Dependencies

All installed in `agent/.venv`:
- `strands-agents[bidi-all]>=1.18.0` - BidiAgent + Nova Sonic
- `websockets` - WebSocket server
- `boto3` - AWS SDK
- `mcp>=1.0.0` - Model Context Protocol
- `httpx-auth-awssigv4` - Gateway authentication

---

**Priority:** Implement proper Strands BidiAgent approach to align with team standards and reduce maintenance burden.

