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
            websocketUrl: "ws://localhost:8080/ws"
        };
        
        // Audio processing limits for security
        this.MAX_AUDIO_CHUNK_SIZE = 64 * 1024; // 64KB max per chunk
        this.MAX_AUDIO_BUFFER_SIZE = 1024 * 1024; // 1MB max total buffer
        this.audioBufferSize = 0;
        
        this.socket = null;
        this.mediaRecorder = null;
        this.chatMessagesEndRef = React.createRef();
        this.stateRef = React.createRef();
        this.eventDisplayRef = React.createRef();
        this.audioPlayer = new AudioPlayer();
        
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

        if (Object.keys(prevState.chatMessages).length !== Object.keys(this.state.chatMessages).length) {
            this.chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }

    sendEvent(event) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(event));
            event.timestamp = Date.now();

            if (this.eventDisplayRef.current) {
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
            case "bidi_transcript_stream":
                // Handle text transcript (user or assistant)
                const role = message.role?.toUpperCase() || "ASSISTANT";
                const text = message.text || message.transcript || "";
                const contentId = message.contentId || `msg-${Date.now()}-${Math.random()}`;
                
                if (text) {
                    if (!chatMessages[contentId]) {
                        chatMessages[contentId] = {
                            content: "",
                            role: role,
                            raw: []
                        };
                    }
                    chatMessages[contentId].content = text;
                    chatMessages[contentId].raw.push(message);
                    this.setState({chatMessages: chatMessages});
                    
                    // Throttle transcript event logging
                    const now = Date.now();
                    const shouldLogTranscript = (now - this.lastTranscriptEventLogTime) >= this.transcriptEventLogInterval;
                    
                    if (shouldLogTranscript && this.eventDisplayRef.current) {
                        this.eventDisplayRef.current.displayEvent(message, "in");
                        this.lastTranscriptEventLogTime = now;
                    }
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
                    
                    // Check total buffer size
                    this.audioBufferSize += chunkSize;
                    if (this.audioBufferSize > this.MAX_AUDIO_BUFFER_SIZE) {
                        console.warn(`Total audio buffer size (${this.audioBufferSize}) exceeds maximum allowed (${this.MAX_AUDIO_BUFFER_SIZE}). Resetting buffer.`);
                        this.audioBufferSize = chunkSize; // Reset to current chunk size
                    }
                    
                    const audioData = base64ToFloat32Array(base64Data);
                    this.audioPlayer.playAudio(audioData);
                    
                    // Throttle event logging - only log every N chunks or every 2 seconds
                    this.audioChunkCount++;
                    const now = Date.now();
                    const shouldLog = (now - this.lastAudioEventLogTime) >= this.audioEventLogInterval;
                    
                    if (shouldLog && this.eventDisplayRef.current) {
                        // Create a summary event with chunk count
                        const summaryEvent = {
                            ...message,
                            chunkCount: this.audioChunkCount
                        };
                        this.eventDisplayRef.current.displayEvent(summaryEvent, "in");
                        this.lastAudioEventLogTime = now;
                        this.audioChunkCount = 0;
                    }
                } catch (error) {
                    console.error("Error processing audio chunk:", error);
                }
                break;
                
            case "bidi_interruption":
                // User interrupted the agent
                console.log("Interruption detected:", message.reason);
                this.cancelAudio();
                break;
                
            case "tool_use_stream":
                // Tool is being called
                const toolName = message.current_tool_use?.name || message.tool_name || "unknown";
                console.log("Tool use:", toolName);
                // Could add tool use indicator to UI here
                break;
                
            case "tool_result":
                // Tool execution result
                const result = message.tool_result;
                console.log("Tool result:", result);
                // Could display tool results in UI here
                break;
                
            case "bidi_response_complete":
                // Response finished
                console.log("Response complete");
                break;
                
            case "bidi_connection_start":
                // Connection established
                console.log("Connection started");
                this.setState({status: "connected"});
                break;
                
            case "bidi_connection_close":
                // Connection closed
                console.log("Connection closed");
                this.setState({status: "disconnected"});
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
                break;
                
            default:
                console.log("Unknown event type:", eventType, message);
                break;
        }

        if (this.eventDisplayRef.current) {
            this.eventDisplayRef.current.displayEvent(message, "in");
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

    connectWebSocket() {
        // Connect to the BidiAgent WebSocket server
        if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
            // Build WebSocket URL with voice_id query param
            const url = new URL(this.state.websocketUrl);
            url.searchParams.set('voice_id', this.state.configVoiceIdOption.value);
            const wsUrl = url.toString();

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
                                <div className="chat-area">
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
