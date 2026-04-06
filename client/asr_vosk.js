// client/asr_vosk.js
// 简单日志到页面 
const $out = document.getElementById('transcript');
const $start = document.getElementById('startBtn');
const $stop = document.getElementById('stopBtn');
const $micSelect = document.getElementById('micSelect');
const $btnRefresh = document.getElementById('btnRefresh');

const $voice = document.getElementById('ttsVoice'); // TTS voice
const $auto  = document.getElementById('autoAgent');     // 识别后自动 Agent→TTS

function append(line) {
  $out.textContent += line + '\n';
  $out.scrollTop = $out.scrollHeight;
}
function clearOut() { $out.textContent = ''; }

// WebSocket & 音频流 
let ws, stream, audioCtx, workletNode;
let devicesCache = [];
let speaking = false;

async function listMics() {
  try {
    const tmp = await navigator.mediaDevices.getUserMedia({ audio: true });
    tmp.getTracks().forEach(t => t.stop());
  } catch (e) {
    append(`[ASR] 授权失败: ${e.name} - ${e.message}`);
    throw e;
  }

  const devices = await navigator.mediaDevices.enumerateDevices();
  devicesCache = devices;
  const inputs = devices.filter(d => d.kind === 'audioinput');

  $micSelect.innerHTML = '';
  for (const d of inputs) {
    const opt = document.createElement('option');
    opt.value = d.deviceId;
    opt.textContent = d.label || `麦克风(${d.deviceId.slice(0,6)}…)`;
    $micSelect.appendChild(opt);
  }

  const savedId = localStorage.getItem('chosenMicId');
  if (savedId && inputs.some(d => d.deviceId === savedId)) {
    $micSelect.value = savedId;
  }
}

function connectWS() {
  ws = new WebSocket('ws://127.0.0.1:8080/ws/asr');
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    append('[ASR] ws open');
    ws.send(JSON.stringify({ type: 'start', sampleRate: 16000 }));
  };

  ws.onmessage = async (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === 'ack') {
        append(`[ack] sampleRate=${data.sampleRate}`);
      } else if (data.type === 'final') {
        const text = (data.text || '').trim();
        append(`[final] ${text}`);
        const shouldAuto = ($auto ? $auto.checked : true);
        if (text && shouldAuto && !speaking) {
          speaking = true;
          try {
            await speakWithAgent(text); // 先问 Agent，再流式播答案
          } catch (err) {
            append(`[TTS] 请求失败: ${err}`);
          } finally {
            speaking = false;
          }
        } else if (!text) {
          append('[Agent] 跳过（final 为空）');
        } else if ($auto && !$auto.checked) {
          append('[Agent] 已关闭自动Agent→TTS（未勾选）');
        }
      } else if (data.type === 'partial') {
        append(`[partial] ${data.text || ''}`);
      }
    } catch {
      // 非JSON忽略
    }
  };

  ws.onclose = () => append('[ASR] ws close');
  ws.onerror = (e) => append('[ASR] ws error ' + (e?.message || ''));
}

async function startRecording() {
  $start.disabled = true;
  $stop.disabled = false;
  clearOut();

  const chosenId = $micSelect.value || '';
  if (chosenId) localStorage.setItem('chosenMicId', chosenId);

  const constraints = {
    audio: {
      deviceId: chosenId ? { exact: chosenId } : undefined,
      channelCount: 1,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false
    }
  };

  try {
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (err) {
    append(`[ASR] mic error: ${err.name} - ${err.message}`);
    $start.disabled = false; $stop.disabled = true;
    return;
  }

  connectWS();

  audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  await audioCtx.audioWorklet.addModule('/client/pcm-worklet.js');

  const source = audioCtx.createMediaStreamSource(stream);
  workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor');

  workletNode.port.onmessage = (evt) => {
    const bytes = evt.data;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(bytes);
    }
  };

  // 不回放到本地，避免回声
  source.connect(workletNode);

  append('[ASR] mic started');
}

function stopRecording() {
  $start.disabled = false;
  $stop.disabled = true;

  try { if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify({ type: 'stop' })); ws.close(); } } catch {}
  try { if (workletNode) workletNode.disconnect(); } catch {}
  try { if (audioCtx) audioCtx.close(); } catch {}
  try { if (stream) stream.getTracks().forEach(t => t.stop()); } catch {}

  append('[ASR] stopped');
}

// 识别文本 -> Agent -> TTS（流式）
async function speakWithAgent(userText) {
  append(`[Agent] 请求: ${userText}`);
  const voice = $voice?.value?.trim() || 'en_US-amy-medium.onnx';
  try {
    if (window.TTS?.stopStreamingPlayback) window.TTS.stopStreamingPlayback();
    await window.TTS.streamAgentReply(userText, voice); 
    append('[TTS] 流式播放中…');
  } catch (err) {
    append(`[TTS] 请求失败: ${err?.message || err}`);
  }
}

// 事件绑定
document.getElementById('startBtn').onclick  = startRecording;
document.getElementById('stopBtn').onclick   = stopRecording;
document.getElementById('btnRefresh').onclick = listMics;

// 设备热插拔刷新
navigator.mediaDevices?.addEventListener?.('devicechange', () => listMics());
listMics().catch(() => {});
