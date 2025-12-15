#!/usr/bin/env python3
"""
Scout Voice Agent - Strands BidiAgent WebSocket Server

Uses Strands BidiAgent with custom WebSocket I/O handlers.
The BidiAgent manages the Nova Sonic protocol, tool calling, and conversation flow internally.
"""
import asyncio
import websockets
import json
import logging
import base64
import os
from pathlib import Path
from typing import TYPE_CHECKING

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel
from strands.experimental.bidi.types.events import (
    BidiAudioInputEvent,
    BidiAudioStreamEvent,
    BidiTranscriptStreamEvent,
    BidiInterruptionEvent,
    BidiOutputEvent,
)
from strands.experimental.bidi.types.io import BidiInput, BidiOutput

from scout_config import (
    NOVA_MODEL_ID,
    REGION,
    VOICE_ID,
    SYSTEM_PROMPT,
)
from gateway_client import create_mcp_client, load_gateway_tools

if TYPE_CHECKING:
    from strands.experimental.bidi.agent.agent import BidiAgent as BidiAgentType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("ScoutBidiServer")


class WebSocketInput(BidiInput):
    """
    Custom BidiInput that receives audio from WebSocket.
    
    The frontend sends Nova Sonic protocol events with audioInput.
    We extract the base64 audio and convert to BidiAudioInputEvent.
    """
    
    def __init__(self, websocket, input_queue: asyncio.Queue):
        self.websocket = websocket
        self.input_queue = input_queue
        self.is_active = True
        self._channels = 1
        self._format = "pcm"
        self._rate = 16000
    
    async def start(self, agent: "BidiAgentType") -> None:
        """Called when BidiAgent starts - get audio config from agent."""
        logger.info("WebSocketInput started")
        # Get audio config from agent model
        audio_config = agent.model.config.get("audio", {})
        self._channels = audio_config.get("channels", 1)
        self._format = audio_config.get("format", "pcm")
        self._rate = audio_config.get("input_rate", 16000)
    
    async def stop(self) -> None:
        """Called when BidiAgent stops."""
        logger.info("WebSocketInput stopped")
        self.is_active = False
    
    async def __call__(self) -> BidiAudioInputEvent:
        """
        Called repeatedly by BidiAgent to get audio input.
        Blocks until audio is available from the WebSocket.
        """
        while self.is_active:
            try:
                # Wait for audio from the queue (with timeout to check is_active)
                audio_base64 = await asyncio.wait_for(
                    self.input_queue.get(),
                    timeout=0.5
                )
                
                if audio_base64 is None:
                    # End signal - return empty event to signal graceful shutdown
                    logger.info("Input stream ended - signaling BidiAgent to stop")
                    self.is_active = False
                    # Return an empty audio event to trigger clean shutdown
                    return BidiAudioInputEvent(
                        audio="",
                        channels=self._channels,
                        format=self._format,
                        sample_rate=self._rate,
                    )
                
                # Return as BidiAudioInputEvent
                return BidiAudioInputEvent(
                    audio=audio_base64,
                    channels=self._channels,
                    format=self._format,
                    sample_rate=self._rate,
                )
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Input cancelled")
                self.is_active = False
                return BidiAudioInputEvent(
                    audio="",
                    channels=self._channels,
                    format=self._format,
                    sample_rate=self._rate,
                )
        
        # Return empty event when stopped
        return BidiAudioInputEvent(
            audio="",
            channels=self._channels,
            format=self._format,
            sample_rate=self._rate,
        )


class WebSocketOutput(BidiOutput):
    """
    Custom BidiOutput that sends audio to WebSocket.
    
    Receives various BidiOutputEvent types from BidiAgent
    and forwards appropriate ones to the frontend.
    """
    
    def __init__(self, websocket, output_queue: asyncio.Queue):
        self.websocket = websocket
        self.output_queue = output_queue
        self.is_active = True
        self.content_counter = 0  # For generating contentIds
        self.active_content_id = None  # Track current content
        self.tool_error_count = {}  # Track errors per tool
        self.MAX_TOOL_RETRIES = 3  # Stop after 3 consecutive failures
    
    async def start(self, agent: "BidiAgentType") -> None:
        """Called when BidiAgent starts."""
        logger.info("WebSocketOutput started")
    
    async def stop(self) -> None:
        """Called when BidiAgent stops."""
        logger.info("WebSocketOutput stopped")
        self.is_active = False
        await self.output_queue.put(None)  # Signal sender to stop
    
    async def __call__(self, event: BidiOutputEvent) -> None:
        """
        Called by BidiAgent with output events.
        Forward relevant events to the WebSocket.
        """
        if not self.is_active:
            return
        
        # Get event type for routing
        event_type = None
        if hasattr(event, "get"):
            event_type = event.get("type", "")
        
        # Log all non-audio events for debugging
        if event_type and event_type != "bidi_audio_stream":
            logger.info(f"<- BidiAgent: {event_type}")
        
        # Handle audio stream events
        if event_type == "bidi_audio_stream":
            audio_data = event.get("audio", "")
            if audio_data:
                await self.output_queue.put({
                    "event": {
                        "audioOutput": {
                            "content": audio_data
                        }
                    }
                })
        
        # Handle transcript events
        elif event_type == "bidi_transcript_stream":
            # Debug: log full event to see structure
            logger.info(f"TRANSCRIPT EVENT: {event}")
            
            # Try multiple possible field names
            role = event.get("role", "ASSISTANT").upper()
            text = event.get("transcript") or event.get("text") or event.get("content") or ""
            is_final = event.get("is_final", False)
            
            if text:
                # For each new transcript, send contentStart -> textOutput -> contentEnd
                self.content_counter += 1
                content_id = f"content-{self.content_counter}"
                
                # 1. contentStart
                await self.output_queue.put({
                    "event": {
                        "contentStart": {
                            "role": role,
                            "contentId": content_id,
                            "type": "TEXT"
                        }
                    }
                })
                
                # 2. textOutput
                await self.output_queue.put({
                    "event": {
                        "textOutput": {
                            "role": role,
                            "content": text,
                            "contentId": content_id
                        }
                    }
                })
                
                # 3. contentEnd (only if final)
                if is_final:
                    await self.output_queue.put({
                        "event": {
                            "contentEnd": {
                                "contentId": content_id,
                                "type": "TEXT"
                            }
                        }
                    })
                
                logger.info(f"Transcript [{role}]: {text[:80]}...")
        
        # Handle interruption
        elif event_type == "bidi_interruption":
            logger.info(f"Interruption: {event.get('reason', 'unknown')}")
        
        # Handle tool use
        elif event_type == "tool_use_stream":
            # Debug: log full event to see structure
            logger.info(f"TOOL USE EVENT: {event}")
            
            # Try multiple possible field names for tool name
            tool_name = event.get("name") or event.get("tool_name") or event.get("toolName") or "unknown"
            tool_id = event.get("id") or event.get("tool_use_id") or event.get("toolUseId") or ""
            
            logger.info(f"Tool called: {tool_name}")
            await self.output_queue.put({
                "event": {
                    "toolUse": {
                        "toolName": tool_name,
                        "toolUseId": tool_id,
                        "status": "executing"
                    }
                }
            })
        
        # Handle tool result
        elif event_type == "tool_result":
            logger.info(f"TOOL RESULT EVENT: {event}")
            
            # Track tool errors to prevent infinite retry loops
            tool_result = event.get("tool_result", {})
            status = tool_result.get("status", "unknown")
            content = tool_result.get("content", [])
            
            # Check if this is an error result
            if content and len(content) > 0:
                result_text = content[0].get("text", "")
                if "error" in result_text.lower() or status == "error":
                    tool_use_id = tool_result.get("toolUseId", "unknown")
                    
                    # Increment error count
                    self.tool_error_count[tool_use_id] = self.tool_error_count.get(tool_use_id, 0) + 1
                    error_count = self.tool_error_count[tool_use_id]
                    
                    logger.warning(f"Tool error ({error_count}/{self.MAX_TOOL_RETRIES}): {result_text[:100]}")
                    
                    # If we've hit the retry limit, stop the agent
                    if error_count >= self.MAX_TOOL_RETRIES:
                        logger.error(f"Tool failed {error_count} times - stopping agent to prevent infinite loop")
                        self.is_active = False
                        raise Exception(f"Tool retry limit exceeded ({self.MAX_TOOL_RETRIES} failures)")
        
        # Handle response complete
        elif event_type == "bidi_response_complete":
            logger.info("Response complete")
        
        # Handle connection events
        elif event_type in ["bidi_connection_start", "bidi_connection_close"]:
            logger.info(f"Connection: {event_type}")
        
        # Handle usage events
        elif event_type == "bidi_usage":
            pass  # Skip logging usage events
        
        # Log unknown event types
        elif event_type:
            logger.debug(f"Unknown output event: {event_type}")


async def websocket_receiver(websocket, input_queue: asyncio.Queue, is_active: asyncio.Event):
    """
    Receive messages from WebSocket and extract audio for BidiAgent.
    """
    try:
        async for message in websocket:
            if not is_active.is_set():
                break
            
            try:
                data = json.loads(message)
                
                if 'event' in data:
                    event_type = list(data['event'].keys())[0] if data['event'] else None
                    
                    # Log non-audio events
                    if event_type != 'audioInput':
                        logger.info(f"-> Frontend: {event_type}")
                    
                    # Extract audio from audioInput events
                    if event_type == 'audioInput':
                        audio_base64 = data['event']['audioInput'].get('content', '')
                        if audio_base64:
                            await input_queue.put(audio_base64)
                    
                    # Handle session end
                    elif event_type == 'sessionEnd':
                        logger.info("Session end from frontend")
                        await input_queue.put(None)  # Signal end
                        is_active.clear()
                        break
                        
            except json.JSONDecodeError:
                logger.error("Invalid JSON from WebSocket")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket closed by frontend")
    except Exception as e:
        logger.error(f"Receiver error: {e}")
    finally:
        is_active.clear()
        await input_queue.put(None)


async def websocket_sender(websocket, output_queue: asyncio.Queue, is_active: asyncio.Event):
    """
    Send messages from BidiAgent to WebSocket.
    """
    try:
        while is_active.is_set():
            try:
                event = await asyncio.wait_for(output_queue.get(), timeout=0.5)
                
                if event is None:
                    break
                
                await websocket.send(json.dumps(event))
                
            except asyncio.TimeoutError:
                continue
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket closed during send")
    except Exception as e:
        logger.error(f"Sender error: {e}")
    finally:
        is_active.clear()


async def handle_websocket(websocket):
    """Handle a single WebSocket connection."""
    logger.info("New WebSocket connection")
    
    # Create queues for communication
    input_queue = asyncio.Queue()
    output_queue = asyncio.Queue()
    is_active = asyncio.Event()
    is_active.set()
    
    try:
        # Load Gateway tools
        logger.info("Loading Gateway tools...")
        mcp_client = create_mcp_client()
        tools = await load_gateway_tools(mcp_client)
        logger.info(f"Loaded {len(tools)} tools from Gateway")
        for tool in tools:
            spec = getattr(tool, 'tool_spec', {})
            logger.info(f"  Tool: {spec.get('name', 'unknown')}")
        
        # Create Nova Sonic model with proper config
        model = BidiNovaSonicModel(
            model_id=NOVA_MODEL_ID,
            provider_config={
                "audio": {
                    "voice": VOICE_ID,
                    "input_rate": 16000,
                    "output_rate": 24000,
                },
            },
            client_config={"region": REGION},
        )
        
        # Create BidiAgent with tools and system prompt
        agent = BidiAgent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        logger.info("BidiAgent created with Scout system prompt")
        
        # Create custom I/O handlers
        ws_input = WebSocketInput(websocket, input_queue)
        ws_output = WebSocketOutput(websocket, output_queue)
        
        # Start WebSocket receiver and sender tasks
        receiver_task = asyncio.create_task(
            websocket_receiver(websocket, input_queue, is_active)
        )
        sender_task = asyncio.create_task(
            websocket_sender(websocket, output_queue, is_active)
        )
        
        # Send initial connection event to frontend
        await output_queue.put({
            "event": {
                "connectionStart": {
                    "status": "connected",
                    "agent": "Scout"
                }
            }
        })
        
        logger.info("Starting BidiAgent.run()...")
        
        # Run the agent in a task so we can cancel it
        agent_task = asyncio.create_task(
            agent.run(inputs=[ws_input], outputs=[ws_output])
        )
        
        # Wait for either agent completion or receiver task to signal stop
        try:
            done, pending = await asyncio.wait(
                [agent_task, receiver_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # If receiver finished first (sessionEnd), cancel the agent
            if receiver_task in done:
                logger.info("Session ended - cancelling agent")
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    logger.info("Agent cancelled successfully")
            else:
                logger.info("BidiAgent.run() completed normally")
                
        except Exception as e:
            logger.error(f"BidiAgent error: {e}")
            import traceback
            traceback.print_exc()
        
        # Clean up
        is_active.clear()
        await input_queue.put(None)
        await output_queue.put(None)
        
        # Wait for sender task to finish
        await asyncio.gather(sender_task, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"Session error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("Connection cleanup complete")


async def start_server(host: str = "localhost", port: int = 8080):
    """Start the WebSocket server."""
    logger.info("=" * 60)
    logger.info("Scout Voice Agent - Strands BidiAgent Server")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Model: {NOVA_MODEL_ID}")
    logger.info(f"Region: {REGION}")
    logger.info(f"Voice: {VOICE_ID}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Using Strands BidiAgent (manages Nova Sonic internally)")
    logger.info("Tools loaded from AgentCore Gateway")
    logger.info("")
    logger.info(f"WebSocket server: ws://{host}:{port}")
    logger.info("=" * 60)
    
    async with websockets.serve(handle_websocket, host, port):
        logger.info("Server ready - waiting for connections...")
        await asyncio.Future()  # Run forever


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scout Voice Agent - Strands BidiAgent Server")
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
