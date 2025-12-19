# Scout Voice Agent - React Frontend

Production-ready React frontend for the Scout voice agent using BidiAgent protocol.

## Features

- **Cloudscape Design System** - Professional AWS-style UI components
- **Real-time Voice Streaming** - Low-latency audio capture and playback
- **Conversation History** - Chat transcript with user and assistant messages
- **Event Logging** - Debug panel showing all WebSocket events
- **Interruption Support** - Clean barge-in handling
- **Tool Integration** - Visual indicators for tool calls and results
- **Responsive Design** - Works on desktop and mobile

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm start

# Opens http://localhost:3000
```

## Configuration

The frontend connects to the backend WebSocket server. Default URL: `ws://localhost:8080/ws`

You can change the WebSocket URL in the Configuration panel before starting a conversation.

## Architecture

### Components

- **VoiceAgent.js** - Main component handling WebSocket, audio, and UI
- **bidiEvents.js** - BidiAgent protocol event helpers
- **audioHelper.js** - Audio format conversion utilities
- **audioPlayer.js** - Audio playback with interruption support
- **EventDisplay.js** - Event log viewer component

### Protocol

The frontend uses **BidiAgent protocol** (not Nova Sonic protocol):

**Sending Audio:**
```javascript
{
  type: "bidi_audio_input",
  audio: "base64_pcm_audio...",
  format: "pcm",
  sample_rate: 16000,
  channels: 1
}
```

**Receiving Events:**
- `bidi_audio_stream` - Audio output from agent
- `bidi_transcript_stream` - Text transcript (user/assistant)
- `bidi_interruption` - User interrupted agent
- `tool_use_stream` - Tool being called
- `tool_result` - Tool execution result

## Key Differences from Old Implementation

### Old (Nova Sonic Protocol)
- Required session initialization (`sessionStart`, `promptStart`)
- Nested event structure: `{event: {audioInput: {...}}}`
- Manual content management (`contentStart`, `contentEnd`)

### New (BidiAgent Protocol)
- No session initialization needed - BidiAgent handles it
- Flat event structure: `{type: "bidi_audio_input", audio: "..."}`
- Automatic content management

## Development

### Adding Features

1. **New Event Types**: Add handlers in `VoiceAgent.js` `handleIncomingMessage()`
2. **UI Components**: Use Cloudscape Design System components
3. **Audio Processing**: Extend `audioHelper.js` or `audioPlayer.js`

### Testing

```bash
# Run tests
npm test

# Build for production
npm run build
```

## Production Deployment

The React frontend can be:
- Built and served as static files
- Integrated into a larger React application
- Deployed to S3 + CloudFront
- Embedded in your production web app

The backend (`strands-bidi/server.py`) runs independently on AgentCore Runtime.

## Troubleshooting

### "WebSocket connection failed"
- Check backend is running: `python strands-bidi/server.py`
- Verify WebSocket URL includes `/ws` path
- Check browser console for CORS errors

### "Microphone access denied"
- Grant microphone permissions in browser
- Use HTTPS or localhost (required for getUserMedia)

### "No audio output"
- Check browser audio isn't muted
- Verify audio context is initialized
- Check EventDisplay for `bidi_audio_stream` events

## Dependencies

- React 18.2.0
- Cloudscape Design Components 3.0.498
- React Scripts 5.0.1

See `package.json` for complete list.
