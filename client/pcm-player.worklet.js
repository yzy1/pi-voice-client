// client/pcm-player.worklet.js
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.readIndex = 0;
    this.port.onmessage = (e) => {
      const { type, data } = e.data || {};
      if (type === 'chunk' && data) {
        this.queue.push(data);
      } else if (type === 'flush') {
        this.queue.length = 0;
        this.readIndex = 0;
      }
    };
  }

  process(_, outputs) {
    const out = outputs[0][0]; // mono
    let off = 0, need = out.length;
    while (off < need) {
      if (!this.queue.length) {
        for (let i = off; i < need; i++) out[i] = 0;
        break;
      }
      const buf = this.queue[0];
      const remain = buf.length - this.readIndex;
      const copy = Math.min(remain, need - off);
      out.set(buf.subarray(this.readIndex, this.readIndex + copy), off);
      off += copy;
      this.readIndex += copy;
      if (this.readIndex >= buf.length) {
        this.queue.shift();
        this.readIndex = 0;
      }
    }
    return true;
  }
}
registerProcessor('pcm-player', PCMPlayerProcessor);
