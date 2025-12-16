# Scout Nova Voice Agent - Direct Bedrock Implementation

This implementation uses the **direct Bedrock Nova Sonic API** without the Strands SDK abstraction layer.

## Key Characteristics

- **Lower latency** - Direct byte streaming without SDK overhead
- **Smoother speech** - Minimal processing between frontend and Nova Sonic  
- **Faster interruptions** - Native Nova Sonic protocol events
- **Manual tool handling** - Requires custom code for tool execution and prompt injection

## Architecture

```
Frontend → WebSocket → scout_nova_agent.py → Direct Bedrock Nova Sonic API
                       ├─ Manual tool execution (MCP Gateway)
                       └─ Manual system prompt injection
```

## Running Locally

```bash
cd direct-bedrock
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
- Best user experience (smoothest speech, fastest interruptions)
- Direct control over Nova Sonic protocol
- Lower latency

**Cons:**
- More manual code (tool handling, prompt injection)
- Not using team's Strands SDK standard
- Protocol changes require manual updates

## Comparison

See `../COMPARISON.md` for side-by-side comparison with Strands BidiAgent approach.

