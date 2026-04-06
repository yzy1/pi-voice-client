from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import chromadb
import requests
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from agent_base import AgentInterface


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class RagOllamaAdapter(AgentInterface):
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
        self.doc_dir = Path(os.getenv("RAG_DOC_DIR", str(base_dir / "rag_docs")))
        self.top_k = int(os.getenv("RAG_TOP_K", "5"))
        self.max_distance = float(os.getenv("RAG_MAX_DISTANCE", "0.70"))
        self.collection_name = os.getenv("RAG_COLLECTION", "rag_kb")
        self.embed_model = os.getenv(
            "RAG_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        db_path = Path(os.getenv("RAG_DB_PATH", str(base_dir / "chroma_db")))

        print(f"[RAG] init chroma db: {db_path}")
        client = chromadb.PersistentClient(path=str(db_path))
        embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embed_model
        )
        self.collection = client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedder,
        )
        self.index_docs()

    def _all_doc_files(self) -> list[Path]:
        txt_files = list(self.doc_dir.rglob("*.txt")) if self.doc_dir.exists() else []
        md_files = list(self.doc_dir.rglob("*.md")) if self.doc_dir.exists() else []
        return sorted(txt_files + md_files)

    def index_docs(self) -> None:
        files = self._all_doc_files()
        print(f"[RAG] docs dir: {self.doc_dir}")

        if not files:
            self.doc_dir.mkdir(parents=True, exist_ok=True)
            sample_file = self.doc_dir / "sample.md"
            sample_file.write_text(
                "# Hello KB\nThis file is for RAG demo. Put your museum notes here.",
                encoding="utf-8",
            )
            files = [sample_file]
            print("[RAG] no docs found, sample.md created")
        else:
            print(f"[RAG] found docs: {len(files)}")

        ids: list[str] = []
        texts: list[str] = []
        metas: list[dict] = []
        for fp in files:
            content = fp.read_text(encoding="utf-8", errors="ignore")
            chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
            for i, chunk in enumerate(chunks):
                ids.append(f"{fp}::{i}")
                texts.append(chunk)
                metas.append({"source": str(fp), "chunk": i})

        if not ids:
            return

        existing_ids = set(self.collection.get(ids=ids).get("ids", []))
        to_add = [(i, t, m) for i, t, m in zip(ids, texts, metas) if i not in existing_ids]
        if not to_add:
            print("[RAG] no new chunks")
            return

        print(f"[RAG] adding chunks: {len(to_add)}")
        self.collection.add(
            ids=[x[0] for x in to_add],
            documents=[x[1] for x in to_add],
            metadatas=[x[2] for x in to_add],
        )

    def retrieve(self, query: str) -> list[tuple[str, dict, float]]:
        res = self.collection.query(
            query_texts=[query],
            n_results=self.top_k,
            include=["documents", "metadatas", "distances"],
        )
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        filtered: list[tuple[str, dict, float]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            if dist is not None and dist <= self.max_distance:
                filtered.append((doc, meta, float(dist)))
        return filtered

    def build_prompt(self, query: str, contexts: list[tuple[str, dict, float]]) -> str:
        if not contexts:
            return f"""You are a helpful assistant.

# Role and setting
You are a museum docent. Your job is to answer visitors' questions based on the museum's knowledge base. Use the same language as the visitor's input.

# Task
- No relevant information was found in the knowledge base for this question. Say so clearly and politely.
- You may suggest the visitor go to the information desk or check the museum catalog.
- Do not present guesses as if they came from the museum's records.

# Visitor question
{query}
"""

        context_block = "\n\n".join(
            [
                f"[{i+1}] {chunk}\n(Source: {meta['source']} #{meta['chunk']}; distance={dist:.3f})"
                for i, (chunk, meta, dist) in enumerate(contexts)
            ]
        )
        return f"""You are a helpful assistant.

# Role and setting
You are a museum docent. Use the museum knowledge base excerpts below when they are relevant. Use the same language as the visitor's input.

# Relevance and how to answer
1. **Judge relevance**: Is the visitor's question related to the topic of the Context below? If the question is clearly about something else (e.g. unrelated artist, unrelated museum), say that it was not found in the museum's records and do not invent an answer.

2. **When the Context directly answers the question**: Answer from the Context and cite excerpt numbers [1], [2] where appropriate.

3. **When you cannot give a valid answer from [2]** (e.g. the question asks "why" or "the reason" and the Context only says *that* something is so, not *why*): then follow this step instead:
   - First state what *is* in the knowledge base (with [number] if useful).
   - Then say clearly: "This is not stated in our museum's knowledge base" or "The records don't give the reason."
   - After that, you may add: "But one possible explanation is ..." or "I think a likely reason could be ..." and give a short, reasonable inference. Always make it obvious that this part is your own suggestion, not from the records.

# Guidelines
- Never present your own inference or guess as if it came from the knowledge base.
- Keep answers concise; cite [1], [2] for any claim that comes from the Context.

# Visitor question
{query}

# Museum knowledge base excerpts (ordered by relevance)
{context_block}
"""

    def call_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        final_prompt = prompt
        if system_prompt:
            final_prompt = f"{system_prompt}\n\n{prompt}"

        resp = requests.post(
            self.ollama_url,
            json={
                "model": self.ollama_model,
                "prompt": final_prompt,
                "stream": False,
                "options": {
                    "template": "{{ .Prompt }}",
                    "num_ctx": 4096,
                    "temperature": 0.2,
                },
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip()

    def reply(self, text: str, system_prompt: Optional[str] = None) -> str:
        contexts = self.retrieve(text)
        prompt = self.build_prompt(text, contexts)
        return self.call_ollama(prompt, system_prompt=system_prompt)
