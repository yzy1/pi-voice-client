from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI

from agent_base import AgentInterface


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class RagOllamaAdapter(AgentInterface):
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.top_k = int(os.getenv("RAG_TOP_K", "5"))
        self.max_distance = float(os.getenv("RAG_MAX_DISTANCE", "0.50"))
        self.collection_name = os.getenv("RAG_COLLECTION", "rag_kb")
        self.embed_model = os.getenv(
            "RAG_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.doc_dir = Path(os.getenv("RAG_DOC_DIR", str(base_dir / "rag_docs")))
        db_path = Path(os.getenv("RAG_DB_PATH", str(base_dir / "chroma_db")))

        # Initialize DeepSeek client
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if not self.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set (check server/.env or Railway variables).")

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
                "# Hello KB\nThis file is for RAG demo. Put your car manuals here.",
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
            return f"""You are a car sales assistant.

# Strict Rule
You ONLY answer questions based on the documents provided to you. You have searched the knowledge base and found NO relevant information for this question.

# Response
Politely tell the user that this information is not available in your knowledge base. Do NOT use any outside knowledge. Do NOT guess or infer.

# User question
{query}
"""

        context_block = "\n\n".join(
            [
                f"[{i+1}] {chunk}\n(Source: {meta['source']} #{meta['chunk']}; distance={dist:.3f})"
                for i, (chunk, meta, dist) in enumerate(contexts)
            ]
        )
        return f"""You are a car sales assistant.

# Strict Rules
- You ONLY answer from the Context below. Nothing else.
- If the Context does not contain enough information to answer, say clearly: "I don't have that information in my knowledge base."
- Do NOT use any outside knowledge, general knowledge, or training data.
- Do NOT guess, infer, or make up information.
- If the question is unrelated to the documents, say: "I can only answer questions about the vehicles in my knowledge base."

# User question
{query}

# Knowledge base excerpts (ordered by relevance)
{context_block}
"""

    def call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call DeepSeek API with the prompt."""
        client = OpenAI(
            api_key=self.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.deepseek_model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    def reply(self, text: str, system_prompt: Optional[str] = None) -> str:
        contexts = self.retrieve(text)
        prompt = self.build_prompt(text, contexts)
        return self.call_llm(prompt, system_prompt=system_prompt)
