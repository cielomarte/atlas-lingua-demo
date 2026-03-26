class PCM16WorkletProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetSampleRate = options?.processorOptions?.targetSampleRate || 16000;
    this.chunkSamples = Math.max(320, Math.round(this.targetSampleRate * 0.08));
    this.pending = [];
    this.pendingLength = 0;

    this.port.onmessage = (event) => {
      if (event.data?.type === 'flush') {
        this.flushPending();
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true;
    }

    const downsampled = this.downsampleToPCM16(input[0], sampleRate, this.targetSampleRate);
    if (downsampled.length > 0) {
      this.pending.push(downsampled);
      this.pendingLength += downsampled.length;
      this.drainChunks();
    }
    return true;
  }

  drainChunks() {
    while (this.pendingLength >= this.chunkSamples) {
      const chunk = new Int16Array(this.chunkSamples);
      let offset = 0;
      while (offset < chunk.length && this.pending.length > 0) {
        const head = this.pending[0];
        const take = Math.min(head.length, chunk.length - offset);
        chunk.set(head.subarray(0, take), offset);
        offset += take;
        if (take === head.length) {
          this.pending.shift();
        } else {
          this.pending[0] = head.subarray(take);
        }
        this.pendingLength -= take;
      }
      this.port.postMessage(chunk.buffer, [chunk.buffer]);
    }
  }

  flushPending() {
    if (this.pendingLength <= 0) {
      return;
    }
    const chunk = new Int16Array(this.pendingLength);
    let offset = 0;
    while (this.pending.length > 0) {
      const head = this.pending.shift();
      chunk.set(head, offset);
      offset += head.length;
    }
    this.pendingLength = 0;
    this.port.postMessage(chunk.buffer, [chunk.buffer]);
  }

  downsampleToPCM16(input, inputRate, targetRate) {
    if (!input || input.length === 0) {
      return new Int16Array(0);
    }

    if (inputRate === targetRate) {
      const pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, input[i]));
        pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      return pcm;
    }

    const ratio = inputRate / targetRate;
    const newLength = Math.max(1, Math.round(input.length / ratio));
    const pcm = new Int16Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < pcm.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accumulator = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < input.length; i += 1) {
        accumulator += input[i];
        count += 1;
      }
      const sample = count > 0 ? accumulator / count : input[Math.min(offsetBuffer, input.length - 1)];
      const clamped = Math.max(-1, Math.min(1, sample));
      pcm[offsetResult] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      offsetResult += 1;
      offsetBuffer = nextOffsetBuffer;
    }

    return pcm;
  }
}

registerProcessor('pcm16-worklet', PCM16WorkletProcessor);
