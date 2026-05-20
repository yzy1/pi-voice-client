# PHASE 3 — CAR MANUAL RAG & BUTTON EXPANSION

Date: May 2026

================================================================================

## 1. PURPOSE

Phase 3 transitions the RAG knowledge base from a museum exhibit (Guanyin
sculpture) to a car sales assistant. It also expands the physical button
support from one button to three buttons, and updates all system prompts
to reflect the new use case.

---

## 2. CHANGES OVERVIEW

| Component | Before (Phase 2) | After (Phase 3) |
|---|---|---|
| RAG knowledge base | Guanyin museum docs (.txt) | Car manual + review docs (.md) |
| System prompt (server) | Museum docent | Car sales assistant |
| System prompt (Pi) | Voice assistant | Car sales assistant |
| Physical buttons | 1 button (GPIO 17) | 3 buttons (GPIO 17, 27, 22) |
| Button questions | Guanyin museum questions | Car feature questions |

---

## 3. RAG KNOWLEDGE BASE UPDATE

### 3.1 New Documents
Two new `.md` files were added to the `rag_docs/` folder:
- A structured knowledge base generated from car review transcripts
- A car manual document (converted from PDF using MinerU Desktop)

Location on Windows server:
```
C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\rag_docs\
```

### 3.2 PDF Conversion
The 500-page car manual PDF was converted to Markdown using MinerU Desktop.
MinerU removes headers, footers, page numbers and preserves document structure.
Output: a single `.md` file placed in `rag_docs/`.

### 3.3 ChromaDB Batch Size Fix
The 500-page manual generated 12,377 chunks, exceeding ChromaDB's default
batch limit of 5,461. Fix applied in `rag_main_code.py`:

```python
print(f"[RAG] adding chunks: {len(to_add)}")
BATCH_SIZE = 5000
for i in range(0, len(to_add), BATCH_SIZE):
    batch = to_add[i:i + BATCH_SIZE]
    self.collection.add(
        ids=[x[0] for x in batch],
        documents=[x[1] for x in batch],
        metadatas=[x[2] for x in batch],
    )
    print(f"[RAG] indexed batch {i//BATCH_SIZE + 1}: chunks {i} to {i + len(batch)}")
```

### 3.4 Resetting the ChromaDB Index
When replacing RAG documents, always delete the old ChromaDB folder first:
```
C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\chroma_db\
```
Delete the entire folder. It will be rebuilt automatically on next server start.

---

## 4. SERVER PROMPT UPDATE

File: `rag_main_code.py`
Location: `C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\server\`

### 4.1 No-results prompt (when RAG finds nothing relevant)
```python
if not contexts:
    return f"""You are a helpful assistant.

# Role and setting
You are a car manual assistant. Your job is to answer questions based on the
vehicle's owner manual. Use the same language as the user's input.

# Task
- No relevant information was found in the manual for this question. Say so
  clearly and politely.
- You may suggest the user check the relevant section of the owner's manual
  directly.
- Do not present guesses as if they came from the manual.

# User question
{query}
"""
```

### 4.2 Main prompt (when RAG finds relevant chunks)
```python
return f"""You are a helpful assistant.

# Role and setting
You are a car manual assistant. Use the vehicle owner's manual excerpts below
to answer the user's question. Use the same language as the user's input.

# Relevance and how to answer
1. **Judge relevance**: Is the user's question related to the content in the
   Context below? If clearly unrelated, say it was not found in the manual.

2. **When the Context directly answers the question**: Answer from the Context
   and cite excerpt numbers [1], [2] where appropriate.

3. **When you cannot give a complete answer from the Context**: 
   - First state what is in the manual (with [number] if useful).
   - Then say clearly: "This is not fully covered in the manual."
   - You may add a short reasonable inference, clearly marked as your own.

# Guidelines
- Never present your own inference as if it came from the manual.
- Keep answers concise; cite [1], [2] for claims from the Context.

# User question
{query}

# Owner's manual excerpts (ordered by relevance)
{context_block}
"""
```

---

## 5. PI CLIENT PROMPT UPDATE

File: `voice_client.py`
Location: `/home/admin/voice-client/`

### Old prompt:
```python
json={"text": text, "system": "Keep your answers concise and under 3 sentences. You are a voice assistant — your responses will be spoken aloud."}
```

### New prompt:
```python
json={"text": text, "system": "You are a car sales assistant helping customers understand the features and functions of their vehicle. Keep your answers concise and under 3 sentences. Your responses will be spoken aloud."}
```

---

## 6. BUTTON EXPANSION

### 6.1 Hardware Added
Two additional momentary push buttons added to the Raspberry Pi 5.

| Button | GPIO (BCM) | Physical Pin | Ground Pin |
|---|---|---|---|
| Button 1 | GPIO 17 | Pin 11 | Pin 6 |
| Button 2 | GPIO 27 | Pin 13 | Pin 14 |
| Button 3 | GPIO 22 | Pin 15 | Pin 14 |

Buttons 2 and 3 share Ground Pin 14.

### 6.2 Button Questions
Updated in `voice_client.py`:

```python
BUTTON_QUESTIONS = {
    17: "Tell me something about the trunk space of this vehicle",
    27: "What is the fuel economy of this vehicle?",
    22: "What are the safety features of this vehicle?",
}

BUTTON_BOUNCE_TIME = 0.3
```

### 6.3 Testing Procedure
Each button was tested individually using `test_button.py` before being
added to `voice_client.py`. To test a button:

```bash
cd ~/voice-client
source .venv/bin/activate
nano ~/voice-client/test_button.py  # change GPIO number to match button
python test_button.py               # press button, verify output
```

Test script (`test_button.py`):
```python
from gpiozero import Button
from signal import pause

button = Button(17, pull_up=True, bounce_time=0.3)  # change 17 to 27 or 22

def on_press():
    print("Button pressed!")

def on_release():
    print("Button released!")

button.when_pressed = on_press
button.when_released = on_release

print("Waiting for button press... (Ctrl+C to exit)")
pause()
```

---

## 7. KNOWN ISSUES & NOTES

- Windows server IP changes every session (DHCP). Always run `ipconfig` on
  Windows and update `SERVER_URL` in `voice_client.py` on the Pi if needed.
- Last known IP: `192.168.68.119`
- When replacing RAG docs, always delete `chroma_db` folder first or the
  server will use stale indexed data.
- Car manual content answers technical how-to questions well. For owner
  experience questions (MPG, trunk space feel, etc.) consider adding
  review articles or spec sheets to `rag_docs/`.
- The `[RAG] no new chunks` message on server start means ChromaDB already
  has the data indexed — this is normal and means fast startup.

---

## 8. STARTUP PROCEDURE (UPDATED QUICK REFERENCE)

### Windows Server
```
cd "C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\server"
.venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Check IP (new terminal)
```
ipconfig
```
Note the IPv4 Address under Wi-Fi.

### Raspberry Pi
```
cd ~/voice-client
source .venv/bin/activate
nano voice_client.py   # update SERVER_URL if IP changed
python voice_client.py
```

---

## 9. FILE CHANGE SUMMARY

| File | Location | What Changed |
|---|---|---|
| `rag_main_code.py` | Windows server | Batch indexing fix + updated prompts |
| `voice_client.py` | Raspberry Pi | Updated system prompt + 3 button questions |
| `rag_docs/` | Windows server | Replaced museum .txt files with car .md files |
| `chroma_db/` | Windows server | Deleted and rebuilt with new car content |

================================================================================
END OF PHASE 3 DOCUMENTATION
================================================================================
