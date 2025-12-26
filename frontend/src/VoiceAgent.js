import React from 'react';
import './VoiceAgent.css';
import { 
    Alert, 
    Button, 
    SpaceBetween, 
    Container, 
    ColumnLayout, 
    Header, 
    FormField, 
    Select, 
    Checkbox,
    Grid
} from '@cloudscape-design/components';
import BidiEvent from './helper/bidiEvents';
import EventDisplay from './components/EventDisplay';
import { base64ToFloat32Array } from './helper/audioHelper';
import AudioPlayer from './helper/audioPlayer';

class VoiceAgent extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            sessionStarted: false,
            showEventJson: false,
            showConfig: false,
            selectedEvent: null,

            chatMessages: {},
            events: [],
            audioChunks: [],
            audioPlayPromise: null,
            includeChatHistory: false,

            // Removed promptName, textContentName, audioContentName - not needed for BidiAgent

            // BidiAgent config items
            configVoiceIdOption: { label: "Matthew (en-US)", value: "matthew" },
            websocketUrl: process.env.REACT_APP_WS_URL || "ws://localhost:8080/ws"
        };
        
        // Audio processing limits for security
        this.MAX_AUDIO_CHUNK_SIZE = 128 * 1024; // 128KB max per chunk
        this.MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024; // 10MB max total buffer (allows ~5 minutes of audio)
        this.audioBufferSize = 0;
        
        this.socket = null;
        this.mediaRecorder = null;
        this.chatMessagesEndRef = React.createRef();
        this.chatAreaRef = React.createRef();
        this.stateRef = React.createRef();
        this.eventDisplayRef = React.createRef();
        this.audioPlayer = new AudioPlayer();
        
        // Track current response and role to group transcripts (prevents duplicates)
        this.currentResponseId = null;
        this.lastMessageRole = null;
        this.lastMessageId = null;
        
        // Throttle event logging to reduce spam (UI only - processing happens in real-time)
        this.lastAudioEventLogTime = 0;
        this.audioEventLogInterval = 10000; // Log audio events every 10 seconds max
        this.audioChunkCount = 0;
        this.lastTranscriptEventLogTime = 0;
        this.transcriptEventLogInterval = 5000; // Log transcript events every 5 seconds max
    }

    componentDidMount() {
        this.stateRef.current = this.state;
        // Initialize audio player early
        this.audioPlayer.start().catch(err => {
            console.error("Failed to initialize audio player:", err);
        });
        
        // Set status to loaded for localhost development
        this.setState({ status: "loaded" });
    }

    componentWillUnmount() {
        this.audioPlayer.stop();
    }

    componentDidUpdate(prevProps, prevState) {
        this.stateRef.current = this.state;

        // Auto-scroll when messages change (new message or content update)
        const prevMessageCount = Object.keys(prevState.chatMessages).length;
        const currentMessageCount = Object.keys(this.state.chatMessages).length;
        const messageCountChanged = prevMessageCount !== currentMessageCount;
        
        // Also check if any message content changed (for streaming updates)
        let contentChanged = false;
        if (!messageCountChanged) {
            // Same number of messages - check if content changed
            for (const [key, message] of Object.entries(this.state.chatMessages)) {
                const prevMessage = prevState.chatMessages[key];
                if (!prevMessage || prevMessage.content !== message.content) {
                    contentChanged = true;
                    break;
                }
            }
        }
        
        // Scroll if new message added or content updated
        if (messageCountChanged || contentChanged) {
            // Use setTimeout to ensure DOM has updated
            setTimeout(() => {
                // Scroll the chat area container to bottom
                if (this.chatAreaRef.current) {
                    this.chatAreaRef.current.scrollTop = this.chatAreaRef.current.scrollHeight;
                }
            }, 50);
        }
    }

    sendEvent(event) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(event));
            event.timestamp = Date.now();

            // Don't log audio input events to event display - too noisy
            // Only log meaningful events
            const eventType = event.type;
            const shouldLog = eventType !== "bidi_audio_input";
            
            if (shouldLog && this.eventDisplayRef.current) {
                this.eventDisplayRef.current.displayEvent(event, "out");
            }
        }
    }

    cancelAudio() {
        this.audioPlayer.bargeIn();
        this.setState({ isPlaying: false });
    }

    handleIncomingMessage(message) {
        // BidiAgent uses flat event structure with "type" field
        const eventType = message?.type;
        var chatMessages = this.state.chatMessages;

        switch(eventType) {
            case "bidi_response_start":
                // New response starting - update the current response ID only if it changed
                const newResponseId = message.response_id || `response-${Date.now()}`;
                if (newResponseId !== this.currentResponseId) {
                    this.currentResponseId = newResponseId;
                    console.log(`New response started: ${this.currentResponseId}`);
                }
                
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_transcript_stream":
                // Handle text transcript (user or assistant)
                const role = message.role?.toUpperCase() || "ASSISTANT";
                const text = message.text || message.transcript || "";
                
                if (!text) break;
                
                // Use contentId from message if provided
                let contentId = message.contentId;
                
                if (!contentId) {
                    // Check if role changed from last message - if so, create new message
                    if (role !== this.lastMessageRole) {
                        // Role changed - create new message
                        contentId = `${role}-${Date.now()}`;
                        this.lastMessageRole = role;
                        this.lastMessageId = contentId;
                        console.log(`New message card: ${role}`);
                    } else {
                        // Same role - keep updating the SAME message
                        contentId = this.lastMessageId || `${role}-${Date.now()}`;
                        this.lastMessageId = contentId;
                    }
                }
                
                // Create or update the message
                if (!chatMessages[contentId]) {
                    chatMessages[contentId] = {
                        content: "",
                        role: role,
                        raw: [],
                        timestamp: Date.now()
                    };
                }
                
                // APPEND text chunks to grow the message box
                const existingContent = chatMessages[contentId].content.trim();
                
                if (!existingContent) {
                    // First chunk
                    chatMessages[contentId].content = text;
                } else if (text.length > existingContent.length && text.includes(existingContent)) {
                    // Nova Sonic sent a longer version of the same text - replace
                    chatMessages[contentId].content = text;
                } else if (!existingContent.includes(text)) {
                    // New different text - APPEND to grow the box
                    chatMessages[contentId].content = existingContent + " " + text;
                }
                // If text already in existingContent, skip duplicate
                
                chatMessages[contentId].raw.push(message);
                this.setState({chatMessages: chatMessages});
                
                // Log transcript events to event display (useful for debugging)
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_audio_stream":
                // Handle audio output from agent
                try {
                    const base64Data = message.audio;
                    
                    if (!base64Data) break;
                    
                    // Validate audio chunk size for security
                    const chunkSize = base64Data.length;
                    if (chunkSize > this.MAX_AUDIO_CHUNK_SIZE) {
                        console.warn(`Audio chunk size (${chunkSize}) exceeds maximum allowed (${this.MAX_AUDIO_CHUNK_SIZE}). Skipping chunk.`);
                        break;
                    }
                    
                    // Track buffer size for current response
                    this.audioBufferSize += chunkSize;
                    this.audioChunkCount++;
                    
                    // Convert and play audio immediately (worklet handles buffering)
                    const audioData = base64ToFloat32Array(base64Data);
                    this.audioPlayer.playAudio(audioData);
                    
                    // Log progress periodically (every 100 chunks to reduce console spam)
                    if (this.audioChunkCount % 100 === 0) {
                        const bufferMB = (this.audioBufferSize / (1024 * 1024)).toFixed(2);
                        console.log(`[Audio Progress] Chunk #${this.audioChunkCount}, Buffer: ${bufferMB}MB`);
                    }
                    
                    // Don't log individual audio stream events - too noisy
                } catch (error) {
                    console.error("Error processing audio chunk:", error);
                }
                break;
                
            case "bidi_interruption":
                // User interrupted the agent - cancel audio playback
                console.log(`[Interruption] Reason: ${message.reason}, clearing audio buffer`);
                this.cancelAudio();
                
                // Reset counters for interrupted response
                this.audioBufferSize = 0;
                this.audioChunkCount = 0;
                break;
                
            case "tool_use_stream":
                // Tool is being called
                const toolName = message.current_tool_use?.name || message.tool_name || "unknown";
                console.log("Tool use:", toolName);
                
                // Log tool calls to event display (useful!)
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "tool_result":
                // Tool execution result
                const result = message.tool_result;
                console.log("Tool result:", result);
                
                // Log tool results to event display (useful!)
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_response_complete":
                // Response finished - log final stats and reset counters
                const finalBufferMB = (this.audioBufferSize / (1024 * 1024)).toFixed(2);
                const durationSec = (this.audioChunkCount * 640 / 16000).toFixed(1); // Estimate: ~640 samples per chunk at 16kHz
                console.log(`[Response Complete] Total: ${this.audioChunkCount} chunks, ${finalBufferMB}MB, ~${durationSec}s audio`);
                
                this.audioBufferSize = 0; // Reset buffer counter for next response
                this.audioChunkCount = 0; // Reset chunk counter
                
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_connection_start":
                // Connection established
                console.log("Connection started");
                this.setState({status: "connected"});
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_connection_close":
                // Connection closed
                console.log("Connection closed");
                this.setState({status: "disconnected"});
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "error":
                // Error from server
                this.setState({
                    alert: {
                        type: "error",
                        message: message.message || "An error occurred",
                        dismissible: true
                    }
                });
                if (this.eventDisplayRef.current) {
                    this.eventDisplayRef.current.displayEvent(message, "in");
                }
                break;
                
            case "bidi_usage":
                // Usage/billing information - ignore silently
                // This is metadata from Nova Sonic about token/audio usage
                break;
                
            default:
                // Log unknown event types for debugging (but don't display in event log)
                console.log("Unknown event type:", eventType, message);
                break;
        }
    }

    handleSessionChange = e => {
        if (this.state.sessionStarted) {
            // End session
            this.endSession();
            this.cancelAudio();
            this.audioPlayer.start(); 
        } else {
            // Start session
            this.setState({
                chatMessages: {}, 
                events: [], 
            });
            if (this.eventDisplayRef.current) this.eventDisplayRef.current.cleanup();
            
            // Resume audio player on user click (fixes first-session audio issue)
            this.audioPlayer.start();
            
            // Init S2sSessionManager
            try {
                if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
                    this.connectWebSocket();
                }

                // Start microphone 
                this.startMicrophone();
            } catch (error) {
                console.error('Error accessing microphone: ', error);
                this.setState({alert: `Error accessing microphone: ${error.message}`});
            }
        }
        this.setState({sessionStarted: !this.state.sessionStarted});
    }

    async connectWebSocket() {
        // Connect to the BidiAgent WebSocket server
        if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
            try {
                // Get the WebSocket URL from the backend (handles SigV4 signing for AgentCore)
                const baseUrl = process.env.REACT_APP_API_URL || "http://localhost:8080";
                
                console.log("Using API URL:", baseUrl);
                
                const response = await fetch(`${baseUrl}/get-websocket-url?voice_id=${this.state.configVoiceIdOption.value}`);
                
                if (!response.ok) {
                    throw new Error(`Failed to get WebSocket URL: ${response.statusText}`);
                }
                
                const data = await response.json();
                const wsUrl = data.websocket_url;
                
                console.log(`Connecting to ${data.environment} WebSocket...`);

                this.socket = new WebSocket(wsUrl);
                
                this.socket.onopen = () => {
                    console.log("WebSocket connected to BidiAgent!");
                    this.setState({status: "connected"});
                    // BidiAgent handles session initialization automatically
                    // No need to send sessionStart, promptStart, etc.
                };

                // Handle incoming messages
                this.socket.onmessage = (message) => {
                    const event = JSON.parse(message.data);
                    this.handleIncomingMessage(event);
                };

                // Handle errors
                this.socket.onerror = (error) => {
                    console.error("WebSocket Error: ", error);
                this.setState({
                    status: "disconnected",
                    alert: {
                        type: "error",
                        message: "WebSocket connection error. Please restart your conversation.",
                        dismissible: true,
                        showRestart: true
                    }
                });
                
                // End session on WebSocket error
                if (this.state.sessionStarted) {
                    this.endSession();
                    this.setState({ sessionStarted: false });
                }
            };

            // Handle connection close
            this.socket.onclose = (event) => {
                console.log("WebSocket Disconnected", event.code, event.reason);
                this.setState({status: "disconnected"});
                
                // Show appropriate message based on close code
                if (event.code === 1005) {
                    // No status code - likely a connection drop
                    this.setState({
                        alert: {
                            type: "warning",
                            message: "Connection lost unexpectedly. Please restart your conversation.",
                            dismissible: true,
                            showRestart: true
                        }
                    });
                } else if (event.code !== 1000) {
                    // Abnormal closure
                    this.setState({
                        alert: {
                            type: "error",
                            message: `Connection closed unexpectedly (${event.code}). Please restart your conversation.`,
                            dismissible: true,
                            showRestart: true
                        }
                    });
                }
                
                // End session on WebSocket close
                if (this.state.sessionStarted) {
                    this.endSession();
                    this.setState({ sessionStarted: false });
                }
            };
            
            } catch (error) {
                console.error("Error connecting to WebSocket:", error);
                this.setState({
                    status: "disconnected",
                    alert: {
                        type: "error",
                        message: `Failed to connect: ${error.message}`,
                        dismissible: true,
                        showRestart: true
                    }
                });
            }
        }
    }

    async startMicrophone() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            const audioContext = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: 'interactive'
            });

            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(512, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            const targetSampleRate = 16000;

            processor.onaudioprocess = async (e) => {
                if (this.state.sessionStarted) {
                    const inputBuffer = e.inputBuffer;

                    // Create an offline context for resampling
                    const offlineContext = new OfflineAudioContext({
                        numberOfChannels: 1,
                        length: Math.ceil(inputBuffer.duration * targetSampleRate),
                        sampleRate: targetSampleRate
                    });

                    // Copy and resample the audio data
                    const offlineBuffer = offlineContext.createBuffer(1, offlineContext.length, targetSampleRate);
                    const inputData = inputBuffer.getChannelData(0);
                    const outputData = offlineBuffer.getChannelData(0);

                    // Simple resampling
                    const ratio = inputBuffer.sampleRate / targetSampleRate;
                    for (let i = 0; i < outputData.length; i++) {
                        const srcIndex = Math.floor(i * ratio);
                        if (srcIndex < inputData.length) {
                            outputData[i] = inputData[srcIndex];
                        }
                    }

                    // Convert to base64
                    const pcmData = new Int16Array(outputData.length);
                    for (let i = 0; i < outputData.length; i++) {
                        pcmData[i] = Math.max(-32768, Math.min(32767, outputData[i] * 32768));
                    }

                    const base64Data = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));

                    // Validate input audio chunk size for security
                    if (base64Data.length > this.MAX_AUDIO_CHUNK_SIZE) {
                        console.warn(`Input audio chunk size (${base64Data.length}) exceeds maximum allowed (${this.MAX_AUDIO_CHUNK_SIZE}). Skipping chunk.`);
                        return;
                    }

                    // Send audio data using BidiAgent protocol
                    this.sendEvent(BidiEvent.audioInput(base64Data, 16000));
                }
            };

            this.mediaRecorder = { processor, stream };
        } catch (error) {
            console.error('Error accessing microphone:', error);
            throw error;
        }
    }

    endSession() {
        // Stop microphone first
        if (this.mediaRecorder) {
            if (this.mediaRecorder.processor) {
                this.mediaRecorder.processor.disconnect();
            }
            if (this.mediaRecorder.stream) {
                this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
            this.mediaRecorder = null;
        }

        // Close WebSocket if it's open and connected
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            // BidiAgent handles session cleanup automatically
            // Just close the socket
            this.socket.close();
        }

        // Clean up socket reference
        this.socket = null;
        
        // Reset audio buffer size for security
        this.audioBufferSize = 0;
        
        // Reset event throttling
        this.lastAudioEventLogTime = 0;
        this.audioChunkCount = 0;
        this.lastTranscriptEventLogTime = 0;
        
        // Reset message tracking
        this.currentResponseId = null;
        this.lastMessageRole = null;
        this.lastMessageId = null;
        
        // Update state
        this.setState({ 
            sessionStarted: false, 
            status: "disconnected"
        });
        
        console.log('Session ended and cleaned up');
    }

    renderChatMessages() {
        const messages = Object.values(this.state.chatMessages).sort((a, b) => {
            return (a.raw[0]?.timestamp || 0) - (b.raw[0]?.timestamp || 0);
        });

        return messages.map((message, index) => {
            const isUser = message.role === "USER";
            const isAssistant = message.role === "ASSISTANT";
            
            if (!isUser && !isAssistant) return null;

            return (
                <div key={index} className={`chat-item ${isUser ? 'user' : 'bot'}`}>
                    <div className={`message-bubble ${isUser ? 'user-message' : 'bot-message'}`}>
                        {message.content || (isAssistant && message.generationStage ? 
                            <div className="loading-bubble">
                                <div className="loading-dots">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div> : ''
                        )}
                    </div>
                </div>
            );
        });
    }

    render() {
        const voiceOptions = [
            { label: "Matthew (en-US)", value: "matthew" },
            { label: "Joanna (en-US)", value: "joanna" },
            { label: "Amy (en-GB)", value: "amy" }
        ];

        return (
            <div className="voice-agent">
                {this.state.alert && (
                    <Alert
                        type={this.state.alert.type || "error"}
                        dismissible={this.state.alert.dismissible !== false}
                        onDismiss={() => this.setState({alert: null})}
                        action={this.state.alert.showRestart ? (
                            <Button
                                variant="primary"
                                onClick={() => {
                                    this.setState({alert: null});
                                    // Auto-start conversation if not already started
                                    if (!this.state.sessionStarted) {
                                        this.handleSessionChange();
                                    }
                                }}
                            >
                                Restart Conversation
                            </Button>
                        ) : null}
                    >
                        {this.state.alert.message || this.state.alert}
                    </Alert>
                )}

                <Container>
                    <Header variant="h2">Scout Voice Agent</Header>
                    
                    <SpaceBetween direction="vertical" size="l">
                        {/* Configuration Panel */}
                        <Container>
                            <Header variant="h3">Configuration</Header>
                            <ColumnLayout columns={3} variant="text-grid">
                                <FormField label="WebSocket URL">
                                    <input
                                        type="text"
                                        value={this.state.websocketUrl}
                                        onChange={(e) => this.setState({websocketUrl: e.target.value})}
                                        disabled={this.state.sessionStarted}
                                        style={{width: '100%', padding: '8px'}}
                                    />
                                </FormField>
                                
                                <FormField label="Voice">
                                    <Select
                                        selectedOption={this.state.configVoiceIdOption}
                                        onChange={({detail}) => this.setState({configVoiceIdOption: detail.selectedOption})}
                                        options={voiceOptions}
                                        disabled={this.state.sessionStarted}
                                    />
                                </FormField>

                                <div className="session-controls">
                                    <FormField label="Session Control">
                                        <Button
                                            variant={this.state.sessionStarted ? "normal" : "primary"}
                                            onClick={this.handleSessionChange}
                                        >
                                            {this.state.sessionStarted ? "End Conversation" : "Start Conversation"}
                                        </Button>
                                    </FormField>
                                    <div className="chat-history-option">
                                        <Checkbox
                                            checked={this.state.includeChatHistory}
                                            onChange={({detail}) => this.setState({includeChatHistory: detail.checked})}
                                            disabled={this.state.sessionStarted}
                                        >
                                            Include chat history
                                        </Checkbox>
                                        <div className="desc">Maintain conversation context across sessions</div>
                                    </div>
                                </div>
                            </ColumnLayout>
                        </Container>

                        {/* Main Content Area */}
                        <Grid gridDefinition={[{colspan: 6}, {colspan: 6}]}>
                            {/* Chat Area */}
                            <Container>
                                <Header variant="h3">Conversation</Header>
                                <div ref={this.chatAreaRef} className="chat-area">
                                    {this.renderChatMessages()}
                                    <div ref={this.chatMessagesEndRef} className="end-marker" />
                                </div>
                            </Container>

                            {/* Events Area */}
                            <Container>
                                <Header variant="h3">Events</Header>
                                <div className="events-area">
                                    <EventDisplay ref={this.eventDisplayRef} />
                                </div>
                            </Container>
                        </Grid>
                    </SpaceBetween>
                </Container>
            </div>
        );
    }
}

export default VoiceAgent;
