# Scout Voice Agent - Deployment Guide

## Two Server Files

### 📝 test_agent.py - Local Development

**Use for:** Local testing with React frontend

**Features:**
- ✅ Simple setup, no complexity
- ✅ Direct WebSocket connection
- ✅ Fast iteration and debugging
- ✅ No AWS credentials needed for WebSocket (still needs for Bedrock/Gateway)

**How to run:**
```bash
cd strands-bidi
source .venv/Scripts/activate  # Windows
python test_agent.py
```

**Frontend setup:**
```bash
# frontend/.env
REACT_APP_API_URL=http://localhost:8080
```

---

### 🚀 server.py - Production AgentCore

**Use for:** AWS AgentCore deployment

**Features:**
- ✅ IMDS credential refresh for production
- ✅ Pre-signed URL generation with SigV4
- ✅ Production-ready error handling
- ✅ Optimized for AgentCore Runtime

**How to deploy:**
```bash
cd strands-bidi

# Configure AgentCore (interactive)
agentcore configure

# Deploy
agentcore launch

# Test
agentcore invoke '{"prompt": "Hello"}'

# Monitor
agentcore logs --follow
```

**Frontend setup:**
```bash
# frontend/.env
REACT_APP_API_URL=https://runtime.bedrock-agentcore.us-east-1.amazonaws.com/agents/ScoutVoice-BmhNAcH9IQ
```

---

## Complete Workflow

### Local Development & Testing

```bash
# Terminal 1: Backend
cd strands-bidi
python test_agent.py

# Terminal 2: Frontend
cd frontend
npm start

# Browser: http://localhost:3000
# Click "Start Conversation" to test
```

### Deploy to Production

```bash
# 1. Deploy backend to AgentCore
cd strands-bidi
agentcore launch

# 2. Update frontend configuration
# Edit frontend/.env with AgentCore URL

# 3. Test frontend with deployed backend
cd frontend
npm start

# 4. Build frontend for production (optional)
npm run build
# Deploy build/ folder to your hosting (S3, Netlify, etc.)
```

---

## Architecture

### Local (test_agent.py)
```
React Frontend (localhost:3000)
    |
    | HTTP GET /get-websocket-url
    v
test_agent.py (localhost:8080)
    |
    | Returns: ws://localhost:8080/ws
    v
Frontend connects directly to local WebSocket
```

### Production (server.py on AgentCore)
```
React Frontend (hosted)
    |
    | HTTPS GET /get-websocket-url
    v
server.py (AgentCore)
    |
    | Generates pre-signed URL with SigV4
    | Returns: wss://runtime...?X-Amz-Signature=...
    v
Frontend connects to authenticated AgentCore WebSocket
```

---

## Key Differences

| Feature | test_agent.py | server.py |
|---------|--------------|-----------|
| Use Case | Local dev | Production |
| IMDS Credentials | ❌ No | ✅ Yes |
| Pre-signed URLs | ❌ No | ✅ Yes |
| Credential Refresh | ❌ No | ✅ Yes |
| CORS | Local only | Production ready |
| Complexity | Simple | Full-featured |

---

## Troubleshooting

### Local Testing Issues
- **"Cannot connect"**: Is test_agent.py running? Check port 8080
- **"No audio"**: Check browser permissions, verify microphone access
- **"Gateway error"**: Check AWS credentials in ~/.aws/credentials

### Production Issues
- **"403 Forbidden"**: IAM role needs gateway-policy.json permissions
- **"1006 WebSocket error"**: Pre-signed URL expired or invalid
- **"Module not found"**: Rebuild with `agentcore launch` after adding dependencies

### Debugging Commands
```bash
# Check AgentCore status
agentcore status

# View real-time logs
agentcore logs --follow

# Test invocation
agentcore invoke '{"prompt": "test"}'

# Get endpoint info
aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id ScoutVoice-BmhNAcH9IQ --region us-east-1
```

---

## Quick Reference

**Local test command:**
```bash
python test_agent.py
```

**Deploy command:**
```bash
agentcore launch
```

**Frontend API URL:**
- Local: `http://localhost:8080`
- Production: `https://runtime.bedrock-agentcore.{region}.amazonaws.com/agents/{agent-id}`


