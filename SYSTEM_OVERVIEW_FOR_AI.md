\# System Overview for AI

\## RAG + Ollama + Voice Interaction System (Windows, Local)



\---



\## 1. Purpose of the System



This system is a local, end-to-end question-answering application that supports text and voice input, document retrieval (RAG), local large language model inference via Ollama, and optional speech synthesis.



It is intended to run entirely on a local Windows machine and is suitable for museum guides, exhibitions, research demos, or offline knowledge assistants.



\---



\## 2. High-Level Capabilities



\- Accepts text or voice input from a browser

\- Converts speech to text using Vosk (optional)

\- Retrieves relevant documents using a vector database (ChromaDB)

\- Generates answers using a local LLM via Ollama

\- Optionally converts answers to speech using Piper

\- Provides a browser-based UI served by a FastAPI backend



\---



\## 3. Core Technologies



\- Backend framework: FastAPI

\- ASGI server: Uvicorn

\- Local LLM runtime: Ollama

\- LLM model: llama3.1:8b

\- RAG vector database: ChromaDB

\- Embedding model: sentence-transformers/all-MiniLM-L6-v2

\- Speech-to-text (ASR): Vosk

\- Text-to-speech (TTS): Piper (optional)

\- Configuration: python-dotenv



\---



\## 4. Folder Structure Overview



rag\_exhibition-main/



├─ server/                 Backend application  

│  ├─ main.py              FastAPI application entry point  

│  ├─ agent\_factory.py     Selects which agent implementation to use  

│  ├─ agent\_base.py        Abstract agent interface  

│  ├─ agent\_local.py       Simple local text-only agent  

│  ├─ agent\_openai.py      OpenAI-based agent (optional)  

│  ├─ rag\_main\_code.py     RAG + Ollama implementation  

│  ├─ stt\_vosk.py          Speech-to-text logic using Vosk  

│  ├─ tts\_piper.py         Text-to-speech using Piper  

│  ├─ requirements.txt     Python dependencies  

│  ├─ .env                 Runtime configuration (user-created)  

│  └─ .venv/               Python virtual environment  



├─ models/                 External models and binaries  

│  ├─ vosk-model-\*/        Offline ASR model  

│  └─ piper\_win64/         TTS binary and voice models  



├─ rag\_docs/               User knowledge base documents  

├─ chroma\_db/              Persistent RAG vector database  

└─ run.md                  Original execution instructions  



\---



\## 5. Configuration (.env file)



The system is configured entirely through environment variables loaded from a `.env` file in the server directory.



Example configuration for RAG + Ollama mode:



AGENT\_KIND=rag\_ollama  

OLLAMA\_MODEL=llama3.1:8b  

OLLAMA\_URL=http://127.0.0.1:11434/api/generate  

RAG\_DOC\_DIR=absolute\_path\_to\_rag\_docs  

RAG\_DB\_PATH=absolute\_path\_to\_chroma\_db  



\---



\## 6. Agent Architecture



The backend uses a modular agent system.



The agent\_factory module reads AGENT\_KIND and instantiates the appropriate agent.



Supported modes include:

\- local

\- openai

\- rag\_ollama



Each agent implements a common interface for processing queries.



\---



\## 7. RAG + Ollama Flow



1\. User submits a query (text or speech)

2\. Speech input is converted to text using Vosk (if enabled)

3\. Query text is embedded using a SentenceTransformer

4\. ChromaDB retrieves the most relevant document chunks

5\. Retrieved content is injected into a prompt

6\. Prompt is sent to Ollama's LLM endpoint

7\. Generated text is returned to the user

8\. Optional TTS converts text to audio



\---



\## 8. Text-to-Speech (Optional)



Text-to-speech is implemented using Piper, invoked as an external process.



Due to instability on Windows, TTS is optional and may be disabled without affecting core functionality.



\---



\## 9. Application Startup



The system is started using Uvicorn:



uvicorn main:app --host 127.0.0.1 --port 8080



This initializes:

\- Configuration loading

\- Agent selection

\- Document indexing (first run only)

\- API routes and WebSocket endpoints

\- Frontend UI hosting



\---



\## 10. Frontend Interface



The frontend is served directly by the FastAPI backend.



It provides:

\- Microphone selection

\- Audio recording

\- Text input

\- Display of answers

\- Optional streaming audio playback



No separate frontend build system is required.



\---



\## 11. Persistence and State



\- ChromaDB persists document embeddings across restarts

\- RAG indexing is idempotent

\- Ollama models persist locally

\- Configuration changes require a server restart



\---



\## 12. Summary for AI Systems



This project is a local, modular RAG-based question-answering system combining FastAPI, Ollama, and ChromaDB, with optional speech input and output. It is designed for experimentation, offline operation, and extensibility rather than production-scale deployment.

