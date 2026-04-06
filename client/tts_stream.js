// client/tts_stream.js
(() => {
  const TTS_BASE = 'http://127.0.0.1:8080';   // 如需改端口/域名，只改这里
  const ENDPOINT_TTS   = `${TTS_BASE}/tts/stream`;
  const ENDPOINT_AGENT = `${TTS_BASE}/agent/tts/stream`;

  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  let playerNode = null;
  let connected = false;
  let currentAbort = null;

  async function ensurePlayer() {
    if (!playerNode) {
      await audioCtx.audioWorklet.addModule('/client/pcm-player.worklet.js');
      playerNode = new AudioWorkletNode(audioCtx, 'pcm-player', { numberOfOutputs: 1, outputChannelCount: [1] });
    }
    if (!connected) {
      playerNode.connect(audioCtx.destination);
      connected = true;
    }
  }

  function int16ToFloat32(int16) {
    const out = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) out[i] = Math.max(-1, Math.min(1, int16[i] / 32768));
    return out;
  }

  function stopStreamingPlayback() {
    if (playerNode) playerNode.port.postMessage({ type: 'flush' });
    if (currentAbort) {
      try { currentAbort.abort(); } catch {}
      currentAbort = null;
    }
  }

  async function pipePCMToWorklet(resBody) {
    const reader = resBody.getReader();
    const PRE_MS = 150;
    const PRE_FRAMES = Math.floor(16000 * (PRE_MS / 1000));
    let buffered = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const i16 = new Int16Array(value.buffer, value.byteOffset, value.byteLength / 2);
      const f32 = int16ToFloat32(i16);
      buffered += f32.length;
      playerNode.port.postMessage({ type: 'chunk', data: f32 }, [f32.buffer]);
      if (buffered < PRE_FRAMES) continue; // 起播前预缓冲
    }
  }

  // 公用：POST端点并把body流式喂入播放器
  async function _streamPostToWorklet(endpoint, payload) {
    await ensurePlayer();
    stopStreamingPlayback();
    if (audioCtx.state === 'suspended') { try { await audioCtx.resume(); } catch {} }

    currentAbort = new AbortController();
    let res;
    try {
      res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: currentAbort.signal
      });
    } catch (e) {
      currentAbort = null;
      throw new Error('网络错误或被中止');
    }
    if (!res.ok || !res.body) {
      currentAbort = null;
      let msg = '';
      try { const j = await res.json(); msg = j.detail || JSON.stringify(j); } catch { msg = await res.text().catch(()=> ''); }
      throw new Error(`HTTP ${res.status}: ${msg || 'unknown'}`);
    }
    try {
      await pipePCMToWorklet(res.body);
    } finally {
      currentAbort = null;
    }
  }

  // 文本做 TTS
  async function streamAgentTTS(text, voice = 'en_US-amy-medium.onnx') {
    return _streamPostToWorklet(ENDPOINT_TTS, { text, voice });
  }

  // 先问 Agent，再流式播放答案
  async function streamAgentReply(text, voice = 'en_US-amy-medium.onnx') {
    return _streamPostToWorklet(ENDPOINT_AGENT, { text, voice });
  }

  function stop() { stopStreamingPlayback(); }

  function setBaseUrl(url) {
    if (!/^https?:\/\//.test(url)) throw new Error('setBaseUrl 需要 http(s):// 前缀');
    window.TTS_BASE = url.replace(/\/+$/,'');
  }

  window.TTS = { streamAgentTTS, streamAgentReply, stopStreamingPlayback: stop, setBaseUrl,
                 ENDPOINT_TTS: ENDPOINT_TTS, ENDPOINT_AGENT: ENDPOINT_AGENT };
})();
