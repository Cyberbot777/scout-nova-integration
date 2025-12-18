# Migration Guide: Old to New Implementation

## What Changed

Your implementation has been rewritten to follow the **AWS official Strands BidiAgent pattern**.

## File Changes

### New Files (Use These)
- `server.py` - Simplified server (200 lines vs old 580 lines)
- `client.py` - Client launcher with pre-signed URL support
- `client.html` - Frontend using BidiAgent protocol
- `websocket_helpers.py` - SigV4 URL signing
- `config.example.py` - Template for other agents
- `.bedrock_agentcore.yaml.example` - AgentCore deployment config

### Old Files (Deprecated)
- `scout_nova_agent.old.py` - Old implementation with custom I/O handlers

## Key Improvements

### 1. Removed Custom I/O Handlers

**Old Way** (580 lines):
```python
class WebSocketInput(BidiInput):
    # 90 lines of custom input handling
    def __init__(self, websocket, input_queue):
        self.websocket = websocket
        self.input_queue = input_queue
        # ... complex queue management

class WebSocketOutput(BidiOutput):
    # 180 lines of custom output handling
    def __init__(self, websocket, output_queue):
        self.websocket = websocket
        self.output_queue = output_queue
        # ... complex event parsing

# Manual receiver/sender tasks
async def websocket_receiver(...):
    # ... 40 lines

async def websocket_sender(...):
    # ... 40 lines
```

**New Way** (20 lines):
```python
# No custom classes needed!
agent = BidiAgent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)

# Direct WebSocket pass-through
await agent.run(
    inputs=[websocket.receive_json],
    outputs=[websocket.send_json]
)
```

### 2. Simplified Server Architecture

**Old**: Custom WebSocket server with manual event routing  
**New**: FastAPI with direct BidiAgent integration

### 3. Protocol Change

**Old**: Nova Sonic protocol (nested events)
```javascript
{
  "event": {
    "audioInput": {
      "content": "base64audio..."
    }
  }
}
```

**New**: BidiAgent protocol (flat structure)
```javascript
{
  "type": "bidi_audio_input",
  "audio": "base64audio...",
  "format": "pcm",
  "sample_rate": 16000,
  "channels": 1
}
```

### 4. Added AgentCore Production Features

- Health check endpoints (`/ping`, `/health`)
- IMDS credential refresh for EC2 deployment
- Pre-signed URL support for authentication
- OpenTelemetry instrumentation
- Proper Docker multi-stage build

## Code Reduction

| Component | Old Lines | New Lines | Reduction |
|-----------|-----------|-----------|-----------|
| Server Logic | 580 | 200 | 65% |
| Custom I/O | 310 | 0 | 100% |
| Event Handling | 150 | 0 | 100% |
| **Total** | **580** | **200** | **65%** |

## Modularity Improvements

### Old Approach
Configuration was mixed into the code. To adapt for another agent, you'd need to:
1. Clone the entire file
2. Find and replace Scout-specific code
3. Update multiple sections manually

### New Approach
Configuration is isolated in `scout_config.py`. To adapt for another agent:
1. Copy `config.example.py` to `my_agent_config.py`
2. Update one import line in `server.py`
3. Done!

## Testing the New Implementation

### Local Development

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Start client
python client.py --ws-url ws://localhost:8080/ws
```

### AgentCore Deployment

```bash
# Build and deploy
docker build -t scout-voice-agent .
docker push YOUR_ECR_REPO/scout-voice-agent:latest
bedrock-agentcore deploy

# Connect with pre-signed URL
python client.py --runtime-arn YOUR_RUNTIME_ARN
```

## Interruption Support

Both implementations support clean interruptions, but the new one is simpler:

**Old**: Custom interruption handling with manual audio buffer clearing  
**New**: BidiAgent handles interruptions automatically via `bidi_interruption` events

## What Works the Same

- Gateway tool integration
- Scout system prompt and personality
- Voice quality and latency
- Interruption detection
- Audio streaming

## Migration Checklist

- [x] Server rewritten with FastAPI + direct BidiAgent
- [x] Frontend updated to BidiAgent protocol
- [x] Client launcher with pre-signed URL support
- [x] Configuration modularized
- [x] Dockerfile updated for AgentCore
- [x] Documentation updated
- [x] Old implementation archived

## Questions?

Review the new `README.md` for complete documentation on:
- How to run locally
- How to deploy to AgentCore
- How to adapt for other agents
- Protocol specification
- Troubleshooting

The new implementation is simpler, follows AWS standards, and is ready for production deployment!

