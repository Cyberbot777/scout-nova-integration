# Nova Voice Agent - Frontend

React frontend for the Nova Sonic bidirectional streaming voice agent.

## Quick Start

**1. Install dependencies:**
```bash
cd frontend
npm install
```

**2. Start the frontend:**
```bash
npm start
```

Opens at http://localhost:3000

## Requirements

- Make sure the backend is running at `ws://localhost:8080`
- See `agent/README.md` for backend instructions

## Configuration

The WebSocket URL can be changed in the UI settings panel.

Default: `ws://localhost:8080`

## Architecture

```
Browser
├── Microphone Input (16kHz PCM)
├── Audio Output (24kHz PCM)
└── WebSocket (ws://localhost:8080)
        │
        └── Nova Voice Backend (Python)
                │
                └── Amazon Nova Sonic (Bedrock)
```

## Features

- [x] Real-time audio recording
- [x] Audio playback of Nova responses
- [x] WebSocket connection to backend
- [x] Chat message display
- [x] Session management
- [x] Configurable voice settings

