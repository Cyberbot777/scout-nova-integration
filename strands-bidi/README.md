# Scout Nova Voice Agent - Strands BidiAgent Implementation

This implementation uses the **Strands SDK's experimental BidiAgent** with Nova Sonic support.

## Key Characteristics

- **Team standard** - Follows "Strands SDK first" approach
- **Built-in tool handling** - Automatic tool execution via SDK
- **Abstraction layer** - SDK manages Nova Sonic protocol internally
- **Experimental status** - Nova Sonic support is in beta

## Architecture

```
Frontend → WebSocket → scout_nova_agent.py → Strands BidiAgent → Nova Sonic
                       ├─ Custom I/O handlers (WebSocketInput/WebSocketOutput)
                       ├─ Automatic tool execution (MCP Gateway)
                       └─ SDK-managed system prompt
```

## Running Locally

```bash
cd strands-bidi
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Configure credentials
cp env.example .env
# Edit .env with your AWS credentials

# Start server
python scout_nova_agent.py --port 8080
```

Then start the frontend from the parent directory:
```bash
cd ../frontend
npm start
```

## Files

- `scout_nova_agent.py` - Voice agent (WebSocket server, local + production)
- `cli_test_agent.py` - CLI testing tool (text-based, no voice)
- `scout_config.py` - System prompt and configuration
- `gateway_client.py` - MCP client for AgentCore Gateway

## Trade-offs

**Pros:**
- Follows team SDK standards
- Automatic tool handling (no manual code)
- SDK updates handle protocol changes
- Cleaner architecture

**Cons:**
- Slight latency overhead from SDK layer
- Experimental Nova Sonic support
- Less control over protocol details
- Slightly slower interruptions

## Comparison

See `../COMPARISON.md` for side-by-side comparison with Direct Bedrock approach.

