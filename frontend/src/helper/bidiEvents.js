/**
 * BidiAgent Protocol Event Helpers
 * 
 * The BidiAgent protocol uses a flat event structure with a "type" field,
 * unlike Nova Sonic which uses nested "event" objects.
 */

class BidiEvent {
  /**
   * Create a bidi_audio_input event
   * @param {string} base64Audio - Base64 encoded PCM audio data
   * @param {number} sampleRate - Audio sample rate (default: 16000)
   * @returns {object} BidiAgent audio input event
   */
  static audioInput(base64Audio, sampleRate = 16000) {
    return {
      type: "bidi_audio_input",
      audio: base64Audio,
      format: "pcm",
      sample_rate: sampleRate,
      channels: 1
    };
  }

  /**
   * Handle incoming BidiAgent events
   * Event types:
   * - bidi_audio_stream: Audio output from agent
   * - bidi_transcript_stream: Text transcript (user or assistant)
   * - bidi_interruption: User interrupted the agent
   * - tool_use_stream: Tool is being called
   * - tool_result: Tool execution result
   * - bidi_response_complete: Response finished
   * - bidi_connection_start: Connection established
   * - bidi_connection_close: Connection closed
   */
  static isAudioStream(event) {
    return event.type === "bidi_audio_stream";
  }

  static isTranscriptStream(event) {
    return event.type === "bidi_transcript_stream";
  }

  static isInterruption(event) {
    return event.type === "bidi_interruption";
  }

  static isToolUse(event) {
    return event.type === "tool_use_stream";
  }

  static isToolResult(event) {
    return event.type === "tool_result";
  }

  static isResponseComplete(event) {
    return event.type === "bidi_response_complete";
  }

  static isConnectionStart(event) {
    return event.type === "bidi_connection_start";
  }

  static isConnectionClose(event) {
    return event.type === "bidi_connection_close";
  }

  static isError(event) {
    return event.type === "error";
  }
}

export default BidiEvent;

