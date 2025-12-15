#!/usr/bin/env python3
"""
Scout Voice Server - WebSocket server for voice interactions.

Uses direct Bedrock Nova Sonic streaming with AgentCore Gateway tools.
Based on S2sSessionManager pattern for reliable bidirectional audio.

Usage:
    cd agent
    source .venv/Scripts/activate
    python voice_server.py --port 8080
"""
import asyncio
import websockets
import json
import logging
import argparse
import os
import base64
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient, InvokeModelWithBidirectionalStreamOperationInput
from aws_sdk_bedrock_runtime.models import InvokeModelWithBidirectionalStreamInputChunk, BidirectionalInputPayloadPart
from aws_sdk_bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
from smithy_core.shapes import ShapeID

from scout_config import (
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
)
from gateway_client import create_mcp_client, load_gateway_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("VoiceServer")

# Global MCP client for tool execution
_mcp_client = None
_tools = None


async def get_tools():
    """Get or initialize Gateway tools."""
    global _mcp_client, _tools
    
    if _tools is None:
        logger.info("Loading Gateway tools...")
        _mcp_client = create_mcp_client()
        _tools = await load_gateway_tools(_mcp_client)
        logger.info(f"Loaded {len(_tools)} tools from Gateway")
    
    return _tools


def create_bedrock_client():
    """Create a Bedrock client for Nova Sonic streaming."""
    config = Config(
        endpoint_uri=f"https://bedrock-runtime.{REGION}.amazonaws.com",
        region=REGION,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        auth_scheme_resolver=HTTPAuthSchemeResolver(),
        auth_schemes={ShapeID("aws.auth#sigv4"): SigV4AuthScheme(service="bedrock")}
    )
    return BedrockRuntimeClient(config=config)


async def send_to_bedrock(stream, event_data):
    """Send an event to the Bedrock stream."""
    try:
        event_json = json.dumps(event_data)
        event = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=event_json.encode('utf-8'))
        )
        await stream.input_stream.send(event)
    except Exception as e:
        logger.error(f"Error sending to Bedrock: {e}")
        raise


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool via Gateway and return the result."""
    global _tools
    
    try:
        logger.info(f"Executing tool: {tool_name}")
        logger.info(f"Tool input: {json.dumps(tool_input)[:200]}...")
        
        # Find the tool by name from loaded tools
        if not _tools:
            return json.dumps({"error": "Tools not loaded"})
        
        # Find matching tool
        tool = None
        for t in _tools:
            # Tools have a 'name' attribute or similar
            t_name = getattr(t, 'name', None) or getattr(t, 'tool_name', None)
            if t_name == tool_name:
                tool = t
                break
        
        if not tool:
            logger.error(f"Tool '{tool_name}' not found. Available: {[getattr(t, 'name', str(t)) for t in _tools]}")
            return json.dumps({"error": f"Tool '{tool_name}' not found"})
        
        # Call the tool - Strands tools are callable
        # They may be sync or async depending on the tool
        if asyncio.iscoroutinefunction(tool):
            result = await tool(**tool_input)
        else:
            # Check if it's a Strands Tool wrapper
            if hasattr(tool, 'invoke'):
                result = await tool.invoke(tool_input)
            elif hasattr(tool, '__call__'):
                result = tool(**tool_input)
            else:
                result = tool(tool_input)
        
        logger.info(f"Tool result received: {str(result)[:200]}...")
        
        if isinstance(result, dict):
            return json.dumps(result)
        elif isinstance(result, str):
            return result
        else:
            return str(result)
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({"error": str(e)})


async def handle_websocket(websocket):
    """Handle WebSocket connections from the frontend."""
    logger.info("New WebSocket connection from frontend")
    
    # Initialize tools
    await get_tools()
    
    # Create Bedrock client and stream
    client = create_bedrock_client()
    
    try:
        logger.info(f"Connecting to Nova Sonic: {NOVA_MODEL_ID}")
        stream = await client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=NOVA_MODEL_ID)
        )
        logger.info("Bedrock stream established")
        
        is_active = True
        
        # Track session state for tool handling
        current_tool_use_id = None
        current_tool_name = None
        current_tool_input = ""
        current_prompt_name = None  # Track for tool results
        tool_content_counter = 0  # For unique content names

        # Task 1: Forward WebSocket messages to Bedrock
        async def ws_to_bedrock():
            nonlocal is_active
            try:
                async for message in websocket:
                    if not is_active:
                        break
                    try:
                        data = json.loads(message)
                        
                        # Log non-audio events
                        if 'event' in data:
                            event_type = list(data['event'].keys())[0] if data['event'] else None
                            if event_type != 'audioInput':
                                logger.info(f"-> Frontend: {event_type}")
                            
                            # Intercept promptStart to inject real Gateway tools
                            if event_type == 'promptStart' and _tools:
                                # Build tool configuration from loaded Gateway tools
                                tool_specs = []
                                for tool in _tools:
                                    try:
                                        # MCPAgentTool wraps everything in tool_spec attribute
                                        spec = getattr(tool, 'tool_spec', {})
                                        
                                        # Extract input schema - it's wrapped in {"json": {...}}
                                        input_schema_wrapper = spec.get('inputSchema', {})
                                        if isinstance(input_schema_wrapper, dict) and 'json' in input_schema_wrapper:
                                            input_schema = input_schema_wrapper['json']
                                        else:
                                            input_schema = input_schema_wrapper
                                        
                                        # Nova Sonic format (no toolSpec wrapper)
                                        tool_spec = {
                                            "name": spec.get('name', getattr(tool, 'tool_name', 'unknown')),
                                            "description": spec.get('description', 'No description'),
                                            "inputSchema": input_schema  # Direct JSON object
                                        }
                                        tool_specs.append(tool_spec)
                                        logger.info(f"   Tool: {tool_spec['name']}")
                                    except Exception as e:
                                        logger.error(f"Failed to serialize tool {tool}: {e}")
                                
                                if tool_specs:
                                    data['event']['promptStart']['toolConfiguration'] = {
                                        "tools": tool_specs
                                    }
                                    data['event']['promptStart']['toolUseOutputConfiguration'] = {
                                        "mediaType": "application/json"
                                    }
                                    logger.info(f"-> Injected {len(tool_specs)} Gateway tools")
                                    # Debug: Log full tool configuration
                                    import json as json_module
                                    logger.debug(f"Tool config: {json_module.dumps(tool_specs, indent=2)}")
                            
                            # Intercept textInput to inject Scout system prompt
                            if event_type == 'textInput':
                                data['event']['textInput']['content'] = SYSTEM_PROMPT
                                logger.info("-> Injected Scout system prompt")
                        
                        # Forward to Bedrock
                        await send_to_bedrock(stream, data)
                        
                        # Check for session end
                        if 'event' in data and 'sessionEnd' in data['event']:
                            logger.info("Session end received from frontend")
                            is_active = False
                            break
                            
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON from WebSocket")
                    except Exception as e:
                        logger.error(f"Error forwarding to Bedrock: {e}")
                        break
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket closed")
            finally:
                is_active = False
        
        # Task 2: Forward Bedrock responses to WebSocket
        async def bedrock_to_ws():
            nonlocal is_active, current_tool_use_id, current_tool_name, current_tool_input
            nonlocal current_prompt_name, tool_content_counter
            
            try:
                while is_active:
                    try:
                        output = await stream.await_output()
                        result = await output[1].receive()
                        
                        if result.value and result.value.bytes_:
                            response_data = result.value.bytes_.decode('utf-8')
                            event = json.loads(response_data)
                            
                            # Log non-audio events
                            if 'event' in event:
                                event_type = list(event['event'].keys())[0] if event['event'] else None
                                if event_type != 'audioOutput':
                                    logger.info(f"<- Bedrock: {event_type}")
                                
                                # Track promptName from completionStart
                                if event_type == 'completionStart':
                                    comp_data = event['event']['completionStart']
                                    current_prompt_name = comp_data.get('promptName')
                                    logger.info(f"Prompt name: {current_prompt_name}")
                                
                                # Handle tool use events
                                if event_type == 'toolUse':
                                    tool_data = event['event']['toolUse']
                                    current_tool_use_id = tool_data.get('toolUseId')
                                    current_tool_name = tool_data.get('toolName')
                                    current_tool_input = tool_data.get('content', '')
                                    logger.info(f"Tool use started: {current_tool_name}")
                                
                                elif event_type == 'contentEnd' and current_tool_use_id:
                                    # Tool use content ended, execute the tool
                                    logger.info(f"Executing tool: {current_tool_name}")
                                    try:
                                        tool_input = json.loads(current_tool_input) if current_tool_input else {}
                                        tool_result = await execute_tool(current_tool_name, tool_input)
                                        
                                        # Generate unique content name for tool result
                                        tool_content_counter += 1
                                        content_name = f"tool-result-{tool_content_counter}"
                                        
                                        # Send tool result sequence (Nova Sonic format)
                                        # 1. contentStart for tool result
                                        content_start = {
                                            "event": {
                                                "contentStart": {
                                                    "promptName": current_prompt_name,
                                                    "contentName": content_name,
                                                    "interactive": True,
                                                    "type": "TOOL",
                                                    "role": "TOOL",
                                                    "toolResultInputConfiguration": {
                                                        "toolUseId": current_tool_use_id,
                                                        "type": "TEXT",
                                                        "textInputConfiguration": {"mediaType": "text/plain"},
                                                    },
                                                }
                                            }
                                        }
                                        await send_to_bedrock(stream, content_start)
                                        
                                        # 2. toolResult with content
                                        tool_result_event = {
                                            "event": {
                                                "toolResult": {
                                                    "promptName": current_prompt_name,
                                                    "contentName": content_name,
                                                    "content": tool_result,
                                                }
                                            }
                                        }
                                        await send_to_bedrock(stream, tool_result_event)
                                        
                                        # 3. contentEnd
                                        content_end = {
                                            "event": {
                                                "contentEnd": {
                                                    "promptName": current_prompt_name,
                                                    "contentName": content_name
                                                }
                                            }
                                        }
                                        await send_to_bedrock(stream, content_end)
                                        
                                        logger.info("Tool result sent to Bedrock")
                                        
                                    except Exception as e:
                                        logger.error(f"Tool execution failed: {e}")
                                        import traceback
                                        traceback.print_exc()
                                    finally:
                                        current_tool_use_id = None
                                        current_tool_name = None
                                        current_tool_input = ""
                            
                            # Forward event to frontend
                            await websocket.send(json.dumps(event))
                            
                    except StopAsyncIteration:
                        logger.info("Bedrock stream ended")
                        break
                    except Exception as e:
                        if "ValidationException" in str(e):
                            logger.error(f"Validation error: {e}")
                        else:
                            logger.error(f"Error from Bedrock: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Bedrock receiver error: {e}")
            finally:
                is_active = False
        
        # Run both tasks
        ws_task = asyncio.create_task(ws_to_bedrock())
        bedrock_task = asyncio.create_task(bedrock_to_ws())
        
        # Wait for either task to complete
        done, pending = await asyncio.wait(
            [ws_task, bedrock_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Close the stream
        try:
            await stream.input_stream.close()
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Session error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("Connection cleanup complete")


async def start_server(host: str = "localhost", port: int = 8080):
    """Start the WebSocket server."""
    logger.info("=" * 60)
    logger.info("Scout Voice Server")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Model: {NOVA_MODEL_ID}")
    logger.info(f"Region: {REGION}")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"WebSocket server starting at: ws://{host}:{port}")
    logger.info("Frontend should connect to this endpoint")
    logger.info("")
    logger.info("=" * 60)
    
    async with websockets.serve(handle_websocket, host, port):
        logger.info("Server ready - waiting for connections...")
        await asyncio.Future()  # Run forever


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scout Voice WebSocket Server")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    
    args = parser.parse_args()
    
    # Check credentials
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    if not access_key:
        logger.error("AWS credentials not found!")
        logger.error("Create agent/.env with your AWS credentials")
        return
    
    try:
        asyncio.run(start_server(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
