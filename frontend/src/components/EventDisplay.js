import React from 'react';

class EventDisplay extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            audioInputIndex: 0,
            eventsByContentName: [],
            selectedEvent: null,
            showEventJson: false,
        };
    }

    cleanup() {
        this.setState({
            eventsByContentName: [], 
            audioInputIndex: 0,
            selectedEvent: null,
            showEventJson: false
        });
    }
    
    displayEvent(event, type) {
        if (!event) return;
        
        let eventName = null;
        let key = null;
        let ts = Date.now();
        let interrupted = false;
        let displayEvent = { ...event };
        
        // Handle BidiAgent protocol (flat structure with "type" field)
        if (event.type) {
            eventName = event.type;
            
            // Truncate audio data for display
            if ((eventName === "bidi_audio_input" || eventName === "bidi_audio_stream") && event.audio) {
                displayEvent.audio = event.audio.substring(0, 20) + "... [truncated]";
            }
            
            // Generate unique key for this event
            if (eventName === "bidi_audio_input") {
                key = `${eventName}-${this.state.audioInputIndex}-${ts}`;
                this.setState({audioInputIndex: this.state.audioInputIndex + 1});
            } else if (eventName === "bidi_audio_stream") {
                // Group audio stream events by second to reduce spam
                const timeBucket = Math.floor(ts / 1000);
                key = `${eventName}-${timeBucket}`;
            } else if (eventName === "bidi_transcript_stream") {
                const contentId = event.contentId || `transcript-${ts}`;
                key = `${eventName}-${contentId}`;
            } else if (eventName === "bidi_interruption") {
                interrupted = true;
                key = `${eventName}-${ts}`;
            } else {
                key = `${eventName}-${ts}`;
            }
        }
        // Fallback: Handle old Nova Sonic protocol format (for backward compatibility)
        else if (event.event) {
            eventName = Object.keys(event.event)[0];
            const contentType = event.event[eventName]?.type;
            const contentName = event.event[eventName]?.contentName;
            const contentId = event.event[eventName]?.contentId;

            if (eventName === "audioOutput") {
                key = `${eventName}-${contentId}`;
                if (event.event.audioOutput?.content) {
                    displayEvent.event.audioOutput.content = event.event.audioOutput.content.substr(0,10) + "...";
                }
            }
            else if (eventName === "audioInput") {
                key = `${eventName}-${contentName}-${this.state.audioInputIndex}`;
                this.setState({audioInputIndex: this.state.audioInputIndex + 1});
            }
            else if (eventName === "contentStart" || eventName === "textInput" || eventName === "contentEnd") {
                key = `${eventName}-${contentName}-${contentType}`;
                if (type === "in" && event.event[eventName]?.type === "AUDIO") {
                    this.setState({audioInputIndex: this.state.audioInputIndex + 1});
                }
                else if(type === "out") {
                    key = `${eventName}-${contentName}-${contentType}-${ts}`;
                }
            }
            else if(eventName === "textOutput") {
                const role = event.event[eventName]?.role;
                const content = event.event[eventName]?.content;
                if (role === "ASSISTANT" && content && content.startsWith("{")) {
                    try {
                        const evt = JSON.parse(content);
                        interrupted = evt.interrupted === true;
                    } catch (e) {
                        // Not JSON, continue normally
                    }
                }
                key = `${eventName}-${ts}`;
            }
            else if (eventName === "toolUse") {
                key = `${eventName}-${ts}`;
            }
            else {
                key = `${eventName}-${ts}`;
            }
        } else {
            // Unknown format, skip
            return;
        }

        let eventsByContentName = this.state.eventsByContentName || [];

        // Group events by key and type (update existing or create new)
        let exists = false;
        for(let i = 0; i < eventsByContentName.length; i++) {
            const item = eventsByContentName[i];
            if (item.key === key && item.type === type) {
                item.events.push(displayEvent);
                item.interrupted = interrupted;
                exists = true;
                break;
            }
        }
        
        if (!exists) {
            eventsByContentName.unshift({
                key: key, 
                name: eventName, 
                type: type, 
                events: [displayEvent], 
                ts: ts,
                interrupted: interrupted
            });
        }
        
        this.setState({eventsByContentName: eventsByContentName});
    }

    handleEventClick = (event) => {
        this.setState({
            selectedEvent: event,
            showEventJson: !this.state.showEventJson
        });
    }

    getEventClassName(event) {
        let className = "";
        
        if (event.type === "in") {
            // BidiAgent event types
            if (event.name === "tool_use_stream" || event.name === "tool_result") {
                className = "event-tool";
            } else if (event.name === "bidi_interruption") {
                className = "event-int";
            } else {
                className = "event-in";
            }
        } else {
            className = "event-out";
        }
        
        // Old Nova Sonic event types (backward compatibility)
        if (event.name === "toolUse") {
            className = "event-tool";
        }
        
        if (event.interrupted) {
            className = "event-int";
        }
        
        return className;
    }

    render() {
        return (
            <div className="events-display">
                {this.state.eventsByContentName.map((event, index) => (
                    <div 
                        key={index}
                        className={this.getEventClassName(event)}
                        onClick={() => this.handleEventClick(event)}
                        title="Click to view details"
                    >
                        <div>
                            {event.type === "in" ? "← " : "→ "}{event.name}
                            {event.events.length > 1 ? ` (${event.events.length})` : ""}
                            {event.events[0]?.chunkCount ? ` [${event.events[0].chunkCount} chunks]` : ""}
                        </div>
                        
                        {this.state.selectedEvent === event && this.state.showEventJson && (
                            <div className="tooltip" style={{display: 'block'}}>
                                <pre>{JSON.stringify(event.events[event.events.length - 1], null, 2)}</pre>
                            </div>
                        )}
                    </div>
                ))}
                
                {this.state.eventsByContentName.length === 0 && (
                    <div style={{color: '#666', fontStyle: 'italic', padding: '20px', textAlign: 'center'}}>
                        No events yet. Start a conversation to see events here.
                    </div>
                )}
            </div>
        );
    }
}

export default EventDisplay;
