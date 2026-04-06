// client/main.js

// 播放函数
async function playWavBlob(blob) {
  const audio = document.getElementById('ttsAudio');
  const url = URL.createObjectURL(blob);
  audio.src = url;
  try {
    await audio.play();
  } finally {
    // 播放结束后释放
    audio.onended = () => { URL.revokeObjectURL(url); };
  }
}

// askAndPlay：asr_vosk.js传入 text/system/voice
async function askAndPlay(params = {}, options = {}) {
  // params 可包含 { text, system, voice }
  const $text = document.getElementById('agentText');
  const $system = document.getElementById('systemPrompt');
  const $voice = document.getElementById('voice');
  const $status = document.getElementById('agentStatus');

  const text = (params.text ?? $text.value ?? '').trim();
  const system = (params.system ?? $system.value ?? '').trim();
  const voice = (params.voice ?? $voice.value ?? '').trim();

  if (!text) {
    if (!options.quiet) $status.textContent = '请输入要问 Agent 的内容';
    return;
  }

  if (!options.quiet) $status.textContent = '请求中…';

  try {
    const payload = { text };
    if (system) payload.system = system;
    if (voice) payload.voice = voice;

    const resp = await fetch('/agent/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const text = await resp.text();
      if (!options.quiet) {
        $status.textContent = `请求失败：${text || resp.status}`;
      } else {
        $status.textContent = `请求失败（自动）：${text || resp.status}`;
      }
      return;
    }

    const blob = await resp.blob();
    await playWavBlob(blob);
    if (!options.quiet) {
      $status.textContent = '已播放';
    } else {
      $status.textContent = '已播放（自动）';
    }
  } catch (err) {
    if (!options.quiet) {
      $status.textContent = `调用失败：${err?.message || err}`;
    } else {
      $status.textContent = `调用失败（自动）：${err?.message || err}`;
    }
  }
}

// 把askAndPlay给全局，供asr_vosk.js调用
window.askAndPlay = askAndPlay;

// 手动调试用
window.addEventListener('DOMContentLoaded', () => {
  const $btn = document.getElementById('btnAsk');
  if ($btn) {
    $btn.addEventListener('click', () => askAndPlay());
  }
});
