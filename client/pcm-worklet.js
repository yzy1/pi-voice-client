// client/pcm-worklet.js
class PCMWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.inRate = sampleRate;        // 实际AudioContext采样率（48000）
    this.targetRate = 16000;         // 输出16k
    this._monoBuf = [];              // 临时缓冲（float32，原始采样率）
    this._resampleBuf = [];          // 重采样后（float32, 16k）
    this._phase = 0;                 // 重采样相位
    this._ratio = this.inRate / this.targetRate;

    // 输出20ms帧，16k * 0.02 = 320个样本
    this._chunk = new Float32Array(320);
    this._chunkPos = 0;
  }

  // 把本帧的多声道输入混成 mono
  _mixToMono(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return null;
    const numChannels = input.length;
    const chLen = input[0].length;
    if (chLen === 0) return null;

    const out = new Float32Array(chLen);
    if (numChannels === 1) {
      out.set(input[0]);
    } else {
      // 多声道取平均
      for (let i = 0; i < chLen; i++) {
        let sum = 0;
        for (let ch = 0; ch < numChannels; ch++) sum += input[ch][i];
        out[i] = sum / numChannels;
      }
    }
    return out;
  }

  // 线性重采样: inRate -> 16k。考虑跨帧相位连续性。
  _pushAndResample(monoFrame) {
    if (!monoFrame) return;

    // 一帧样本推入mono ring
    this._monoBuf.push(monoFrame);

    // monoBuf合并
    let total = 0;
    for (const b of this._monoBuf) total += b.length;
    const mono = new Float32Array(total);
    let o = 0;
    for (const b of this._monoBuf) { mono.set(b, o); o += b.length; }
    this._monoBuf.length = 0; // 清空

    // 保留相位线性插值
    let i = this._phase; // 以输入采样点为单位的上次剩余相
    while (i + this._ratio < mono.length) {
      const i0 = Math.floor(i);
      const i1 = i0 + 1;
      const t = i - i0;
      const s0 = mono[i0];
      const s1 = (i1 < mono.length) ? mono[i1] : s0;
      const y = s0 + (s1 - s0) * t;   // 线性插值
      this._resampleBuf.push(y);
      i += this._ratio;
    }
    this._phase = i - mono.length;   // 保存跨帧相位，负数，表示缺口
  }

  // 每凑320个16k样本就量化为PCM16发出
  _drainChunks() {
    while (this._resampleBuf.length >= 320 - this._chunkPos) {
      const need = 320 - this._chunkPos;
      for (let k = 0; k < need; k++) {
        this._chunk[this._chunkPos++] = this._resampleBuf.shift();
      }
      // 量化为PCM16，little-endian
      const pcm = new Int16Array(320);
      for (let i = 0; i < 320; i++) {
        let s = Math.max(-1, Math.min(1, this._chunk[i]));
        // 小增益，避免过小
        s = s * 0.95;
        pcm[i] = (s < 0 ? s * 32768 : s * 32767) | 0;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]); // 直接转ArrayBuffer
      this._chunkPos = 0;
    }
  }

  process(inputs) {
    const mono = this._mixToMono(inputs);
    this._pushAndResample(mono);
    this._drainChunks();

    // 不需要输出到喇叭，返回 true 维持处理循环
    return true;
  }
}

registerProcessor('pcm-processor', PCMWorklet);
