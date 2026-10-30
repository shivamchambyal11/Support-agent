from pathlib import Path

import chromadb
from llm import generate  # src/llm.py se aata hai (pichle message wali file)

# Project root se chroma_db ka path (kisi bhi folder se chalao, chalega)
ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = str(ROOT / "chroma_db")

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection("support_kb")  # kb_ingest.py ne ye banaya tha

SYSTEM = """You are a customer support assistant for an e-commerce store.
Answer ONLY using the provided context.
If the answer is not in the context, say: "I don't have that information."
Be concise. Mention the source file name(s) you used."""


def retrieve(question: str, k: int = 4):
    """Top-k relevant chunks (text, source) return karta hai."""
    result = collection.query(query_texts=[question], n_results=k)
    docs = result["documents"][0]
    sources = [m["source"] for m in result["metadatas"][0]]
    return list(zip(docs, sources))


def answer(question: str):
    """Retrieve karo, context banao, LLM se answer lo."""
    hits = retrieve(question)
    context = "\n\n".join(f"[{src}]\n{doc}" for doc, src in hits)
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"
    reply = generate(SYSTEM, user_prompt)
    return reply, sorted({src for _, src in hits})


if __name__ == "__main__":
    print("Support bot ready. Exit ke liye 'q' likho.\n")
    while True:
        q = input("Q: ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if not q:
            continue
        reply, sources = answer(q)
        print(f"\n{reply}\nSources: {', '.join(sources)}\n")