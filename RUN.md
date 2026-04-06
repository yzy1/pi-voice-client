# 如何运行博物馆语音机器人

## 一、环境要求

- **Python 3.10+**（建议 3.10 或 3.11）
- **浏览器**：Chrome / Edge（需支持麦克风、AudioWorklet）
- **麦克风**（用于语音识别）

---

## 二、后端依赖

在项目根目录执行：

```bash
cd server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

（Linux/macOS 用 `source venv/bin/activate`）

---

## 三、模型与资源

### 1. 语音识别（Vosk）

- 下载：<https://alphacephei.com/vosk/models>  
  选 **vosk-model-small-en-us-0.15**（约 40MB）
- 解压后把**解压出来的文件夹**放到项目的 `models` 下，最终路径为：
  ```
  museum-voice-bot/models/vosk-model-small-en-us-0.15/
  ```
  该目录下应有 `am`, `conf`, `graph` 等子目录。

### 2. 语音合成（Piper）

- 下载 Windows 版：<https://github.com/rhasspy/piper/releases>  
  或 <https://sourceforge.net/projects/piper-tts.mirror/files/>  
  得到 `piper_windows_amd64.zip`，解压。
- 在项目里建目录：`models/piper_win64/`
- 把解压得到的 **piper.exe** 放进 `models/piper_win64/`
- 下载英文语音模型（例如）：  
  **en_US-amy-medium**（.onnx + 同名的 .onnx.json）  
  放到同一目录 `models/piper_win64/`  
  语音模型列表：<https://github.com/rhasspy/piper/releases>

最终目录类似：

```
museum-voice-bot/
  models/
    vosk-model-small-en-us-0.15/   # Vosk 解压后的目录
    piper_win64/
      piper.exe
      en_US-amy-medium.onnx
      en_US-amy-medium.onnx.json
```

---

## 四、配置（选择 Agent 模式）

### 1) OpenAI 模式（原有）

在 `server/.env` 中确认包含：

- `OPENAI_API_KEY=sk-...`（你的 OpenAI API Key）
- `AGENT_KIND=openai`（默认）
- 可选：`OPENAI_MODEL=gpt-4o-mini` 等

### 2) RAG + Ollama 模式（新接入）

把 `AGENT_KIND` 改为：

```env
AGENT_KIND=rag_ollama
```

并按需增加以下配置（可选，未配置会使用默认值）：

```env
OLLAMA_MODEL=llama3.1:8b
OLLAMA_URL=http://127.0.0.1:11434/api/generate
RAG_DOC_DIR=E:\your\museum_docs
RAG_DB_PATH=E:\RAG\museum-voice-bot\chroma_db
RAG_TOP_K=5
RAG_MAX_DISTANCE=0.70
RAG_COLLECTION=rag_kb
RAG_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

说明：
- `RAG_DOC_DIR` 目录下放 `*.txt` / `*.md` 文档即可；
- 服务启动时会自动做幂等索引（重复启动不会重复入库）；
- 语音识别后的文本会走 RAG 检索和生成，再通过 `/agent/tts/stream` 直接流式播报。

---

## 五、启动服务

在 **server** 目录下、已激活 venv 时执行：

```bash
uvicorn main:app --host 127.0.0.1 --port 8080
```

或 Windows 下在项目根目录双击/运行：

```bash
run.bat
```

看到类似：

```
INFO:     Uvicorn running on http://127.0.0.1:8080
```

即表示后端已就绪。

---

## 六、打开前端

浏览器访问：

**http://127.0.0.1:8080/**

然后：

1. 点击「麦克风列表」确认设备，选好麦克风  
2. 勾选「识别出一句话后自动问Agent并播放」（可选）  
3. 点击「开始录音并识别」  
4. 对着麦克风说话，识别出句子后会自动问 Agent 并用 TTS 播放回答  

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `Vosk model directory not found` | 按上面把 Vosk 解压到 `models/vosk-model-small-en-us-0.15` |
| `piper.exe not found` | 确保 `models/piper_win64/piper.exe` 存在，且同目录有对应 .onnx 语音模型 |
| `[agent error]` | 检查 `.env` 中 `AGENT_KIND` 对应配置；`openai` 看 API Key，`rag_ollama` 看 Ollama 与 RAG 配置 |
| `No module named chromadb` | 重新执行 `pip install -r requirements.txt` 安装 RAG 依赖 |
| `连接不到 Ollama` | 先启动 Ollama 并确认 `OLLAMA_URL` 可访问（默认 `127.0.0.1:11434`） |
| 页面连不上 / WebSocket 失败 | 确认后端在 8080 端口运行，且前端地址为 http://127.0.0.1:8080 |
| 麦克风无权限 | 在浏览器里允许该站点使用麦克风 |
