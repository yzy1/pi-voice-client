// client/chat.js — 文字提问：调用 Agent，展示回复，可选 TTS 播放
(function () {
  const CHAT_API = 'http://127.0.0.1:8080/agent/reply';
  const $input = document.getElementById('chatInput');
  const $send = document.getElementById('chatSend');
  const $playTTS = document.getElementById('chatPlayTTS');
  const $log = document.getElementById('chatLog');

  function timeStr() {
    const d = new Date();
    return d.toTimeString().slice(0, 8);
  }

  function appendMsg(role, text) {
    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    const strong = role === 'user' ? 'You' : 'Assistant';
    div.innerHTML = '<span class="time">' + timeStr() + '</span><strong>' + strong + '</strong><br>' + escapeHtml(text);
    $log.appendChild(div);
    $log.scrollTop = $log.scrollHeight;
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function getVoice() {
    const $v = document.getElementById('ttsVoice');
    return ($v && $v.value && $v.value.trim()) ? $v.value.trim() : 'en_US-amy-medium.onnx';
  }

  async function sendQuestion() {
    const text = ($input.value || '').trim();
    if (!text) return;

    $input.value = '';
    $send.disabled = true;
    appendMsg('user', text);

    try {
      const res = await fetch(CHAT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      const data = await res.json().catch(() => ({}));
      const reply = (data.reply != null ? data.reply : (res.ok ? '' : (data.detail || res.statusText))).trim() || '(无回复)';
      appendMsg('assistant', reply);

      if ($playTTS && $playTTS.checked && reply !== '(无回复)' && window.TTS && window.TTS.streamAgentTTS) {
        try {
          await window.TTS.streamAgentTTS(reply, getVoice());
        } catch (e) {
          console.warn('TTS play failed', e);
        }
      }
    } catch (err) {
      appendMsg('assistant', '[请求失败] ' + (err.message || String(err)));
    } finally {
      $send.disabled = false;
      $input.focus();
    }
  }

  $send.addEventListener('click', sendQuestion);
  $input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  });
})();
