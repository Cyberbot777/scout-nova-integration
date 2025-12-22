// Audio sample buffer to minimize reallocations
class ExpandableBuffer {
    constructor() {
        // Start with 2 seconds worth of buffered audio capacity at 16kHz
        this.buffer = new Float32Array(32000);  // 2.0 seconds at 16kHz
        this.readIndex = 0;
        this.writeIndex = 0;
        this.underflowedSamples = 0;
        this.isInitialBuffering = true;
        this.initialBufferLength = 3200;  // 200ms at 16kHz - slightly more initial buffering
        this.lastWriteTime = 0;
        this.maxBufferSize = 4800000; // Max 5 minutes of audio at 16kHz (for long agent responses)
        this.droppedSamplesTotal = 0;
    }

    write(samples) {
        const now = Date.now();
        this.lastWriteTime = now;

        // Calculate space needed
        const currentSamples = this.writeIndex - this.readIndex;
        const spaceNeeded = currentSamples + samples.length;

        if (this.writeIndex + samples.length <= this.buffer.length) {
            // Enough space to append the new samples directly
            this.buffer.set(samples, this.writeIndex);
            this.writeIndex += samples.length;
        }
        else if (samples.length <= this.readIndex) {
            // Can shift existing samples to the beginning to make room
            const subarray = this.buffer.subarray(this.readIndex, this.writeIndex);
            this.buffer.set(subarray);
            this.writeIndex -= this.readIndex;
            this.readIndex = 0;
            this.buffer.set(samples, this.writeIndex);
            this.writeIndex += samples.length;
        }
        else {
            // Need to grow the buffer
            let newLength = Math.max(spaceNeeded * 1.5, this.buffer.length * 2);
            
            // Cap at max size
            if (newLength > this.maxBufferSize) {
                newLength = this.maxBufferSize;
            }
            
            // Check if we can fit everything
            if (spaceNeeded > newLength) {
                // Can't fit everything - this is a real overflow
                // Keep most recent audio, drop oldest
                const samplesToKeep = newLength - samples.length;
                const dropCount = currentSamples - samplesToKeep;
                
                if (dropCount > 0) {
                    this.droppedSamplesTotal += dropCount;
                    if (this.droppedSamplesTotal % 10000 === 0) {
                        console.warn(`Buffer overflow: dropped ${this.droppedSamplesTotal} samples total`);
                    }
                    this.readIndex += dropCount;
                }
            }
            
            // Create new buffer and copy existing data
            const newBuffer = new Float32Array(newLength);
            const existingSamples = this.writeIndex - this.readIndex;
            newBuffer.set(this.buffer.subarray(this.readIndex, this.writeIndex));
            
            // Add new samples
            newBuffer.set(samples, existingSamples);
            
            this.buffer = newBuffer;
            this.readIndex = 0;
            this.writeIndex = existingSamples + samples.length;
        }
        
        if (this.writeIndex - this.readIndex >= this.initialBufferLength) {
            // Filled the initial buffer length, so we can start playback with some cushion
            this.isInitialBuffering = false;
        }
    }

    read(destination) {
        let copyLength = 0;
        if (!this.isInitialBuffering) {
            // Only start to play audio after we've built up some initial cushion
            copyLength = Math.min(destination.length, this.writeIndex - this.readIndex);
        }
        destination.set(this.buffer.subarray(this.readIndex, this.readIndex + copyLength));
        this.readIndex += copyLength;

        if (copyLength < destination.length) {
            // Not enough samples (buffer underflow). Fill the rest with silence.
            destination.fill(0, copyLength);
            this.underflowedSamples += destination.length - copyLength;
        }
        if (copyLength === 0) {
            // Ran out of audio, so refill the buffer to the initial length before playing more
            this.isInitialBuffering = true;
        }
    }

    clearBuffer() {
        this.readIndex = 0;
        this.writeIndex = 0;
        this.isInitialBuffering = true;
    }
}

class AudioPlayerProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.playbackBuffer = new ExpandableBuffer();
        this.port.onmessage = (event) => {
            if (event.data.type === "audio") {
                this.playbackBuffer.write(event.data.audioData);
            }
            else if (event.data.type === "initial-buffer-length") {
                // Override the current playback initial buffer length
                this.playbackBuffer.initialBufferLength = event.data.bufferLength;
            }
            else if (event.data.type === "barge-in") {
                this.playbackBuffer.clearBuffer();
            }
        };
    }

    process(inputs, outputs, parameters) {
        const output = outputs[0][0]; // Assume one output with one channel
        this.playbackBuffer.read(output);
        return true; // True to continue processing
    }
}

registerProcessor("audio-player-processor", AudioPlayerProcessor);
