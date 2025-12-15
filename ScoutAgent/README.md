# Scout Agent

Enterprise AI agent providing intelligent broker briefings and loan pipeline insights through the Kind Lending Kwikie portal. Built on AWS Bedrock AgentCore with Strands SDK.

## Purpose

Scout Agent delivers personalized, data-driven briefings to loan brokers through an interactive chat interface. The agent synthesizes real-time loan pipeline data, performance metrics, and time-sensitive alerts into actionable insights, enabling brokers to prioritize critical tasks and track performance effectively.

## Architecture

```
Portal UI --> API Gateway (WebSocket) --> InvokeWebSocketAgentLambda
                                                    |
                                              Scout Agent (AgentCore)
                                                    |
                                       AgentCore Gateway (MCP)
                                                    |
                                        ┌───────────┴──────────┐
                                  HydraQueryLambda    SnowflakeQueryLambda
                                        |                      |
                                    Hydra API            Snowflake (BS DB)
```

**Model**: Claude Sonnet 4 with Bedrock Guardrails  
**Region**: us-east-1 (all resources)

### Components

This repository contains three main component types:

**Agent** (`/Agents/ScoutAgent/`)
- Production agent runtime with briefing logic
- AgentCore deployment configuration

**Invocation Endpoints** (`/Endpoints/`)
- Lambda functions that invoke the AgentCore agent
- Support both REST (synchronous) and WebSocket (streaming) invocation patterns

**Tool Functions** (`/Tools/`)
- Lambda functions providing data access via MCP protocol
- Connected to agent through AgentCore Gateway

## Prerequisites

- Python 3.11+
- AWS credentials with access to:
  - Amazon Bedrock (Claude model access)
  - AWS Bedrock AgentCore
- [uv](https://github.com/astral-sh/uv) package manager

## Local Development

### Setup

1. Navigate to agent directory:
   ```bash
   cd Agents/ScoutAgent
   ```

2. Create and activate virtual environment:
   ```bash
   uv venv
   .venv\Scripts\activate     # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   uv pip install strands-agents strands-agents-tools mcp httpx-auth-awssigv4 boto3 bedrock-agentcore
   ```

## Agent Implementation

Scout Agent is implemented as a production-ready AWS Bedrock AgentCore agent in `kwikie_agent.py`:

- **Deployment**: AWS Bedrock AgentCore runtime
- **Streaming**: Real-time response streaming via async/yield pattern
- **Tools**: Connects to AgentCore Gateway for MCP-based tool access
- **Observability**: OpenTelemetry instrumentation and CloudWatch integration
- **Authentication**: SigV4 authentication for Gateway communication

### Payload Requirements

The agent requires the following parameters in the invocation payload:

- **`prompt`** (required): User's question or request
- **`sysUserId`** (required): System user ID for broker identification (used by SnowflakeQuery tool)
- **`conversationHistory`** (optional): Array of previous messages for multi-turn conversations

## Production Deployment

### Configuration

- **Agent Name**: `kwikieagent`
- **Region**: `us-east-1`
- **Agent ARN**: `arn:aws:bedrock-agentcore:us-east-1:025066260073:runtime/kwikieagent-9XPLfP2pzl`
- **Model**: Claude Sonnet 4 (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
- **Guardrail**: `6gwv3he4u3dx` (version 1)
- **Platform**: linux/arm64

### Deploy/Update

1. Install AgentCore toolkit:
   ```bash
   uv pip install bedrock-agentcore-starter-toolkit
   ```

2. Deploy to AgentCore:
   ```bash
   agentcore launch
   ```

3. Test deployment:
   ```bash
   agentcore invoke '{"prompt": "Generate my daily briefing", "sysUserId": "12956"}'
   ```

Configuration is managed in `.bedrock_agentcore.yaml`.

## Available Tools

The agent accesses tools through AgentCore Gateway (MCP protocol):

| Tool | Lambda Function | Purpose |
|------|----------------|---------|
| **GetLoanDetails** | HydraQueryLambda | Retrieves loan details from Hydra GraphQL API (borrower names, documents, eligibility)<br>Parameters: `loanId`, `queryName` ("scoutBrokerBrief") |
| **SnowflakeQuery** | SnowflakeQueryLambda | Queries loan pipeline and funded loan data<br>Parameters: `sys_user_id` (string), `query_type` ("active_pipeline" or "funded_loans") |

## Project Structure

```
Agents/ScoutAgent/
├── kwikie_agent.py              # Production AgentCore entrypoint
├── Dockerfile                   # Container build (linux/arm64)
├── .bedrock_agentcore.yaml      # AgentCore deployment config
├── pyproject.toml               # Python dependencies
└── README.md                    # This file

Endpoints/
├── InvokeAgentLambda/           # REST invocation endpoint
└── InvokeWebSocketAgentLambda/  # WebSocket streaming endpoint

Tools/
├── HydraQueryLambda/            # Hydra GraphQL integration
└── SnowflakeQueryLambda/        # Snowflake data queries
```

## Invocation Patterns

### Via AgentCore CLI
```bash
agentcore invoke '{"prompt": "Generate my daily briefing", "sysUserId": "12956"}''
```

### Via Lambda (REST)
Invoke `InvokeAgentLambda` with payload:
```json
{
  "prompt": "Generate my daily briefing",
  "sysUserId": "12956"
}
```

### Via WebSocket
Connect to WebSocket API endpoint and send messages through `InvokeWebSocketAgentLambda` for streaming responses.


## Observability

- **CloudWatch Logs**: Agent execution logs and errors
- **X-Ray Tracing**: Distributed tracing enabled
- **Metrics**: Invocation counts, latency, error rates

View logs:
```bash
agentcore logs --follow
```

## Dependencies

- `strands-agents` (>=1.18.0) - AI agent framework
- `bedrock-agentcore` (>=1.0.0) - AgentCore runtime
- `mcp` (>=1.0.0) - Model Context Protocol
- `httpx-auth-awssigv4` - AWS SigV4 authentication
- `boto3` - AWS SDK
- `aws-opentelemetry-distro` (0.12.2) - Observability

## Security

- **Guardrails**: Bedrock Guardrails enforce content safety
- **IAM**: Least-privilege execution roles
- **Network**: Public network mode (configurable in `.bedrock_agentcore.yaml`)
- **Secrets**: Managed via AWS Secrets Manager
- **Authentication**: SigV4 signing for Gateway communication

## Troubleshooting

**Agent deployment issues:**
```bash
agentcore logs --follow
```

**Verify AWS credentials:**
```bash
aws sts get-caller-identity
```

**Test deployed agent:**
```bash
agentcore invoke '{"prompt": "Show me my active pipeline", "sysUserId": "12956"}'
```

## Related Documentation

- Root [README.md](../../README.md) - Overall project architecture

## License

Internal use only - Kind Lending proprietary software.
