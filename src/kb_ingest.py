import re
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
CHROMA_PATH = str(ROOT / "chroma_db")


def chunk_markdown(text: str, fname: str):
    """H2 headers pe split karo, har chunk ke aage H1 title lagao."""
    text = text.strip()
    m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if not text or not m:
        print(f"[SKIP] {fname}: khali hai ya '# Title' wali line nahi mili")
        return []
    title = m.group(1).strip()

    parts = re.split(r"\n(?=## )", text)
    chunks = []
    for p in parts:
        p = p.strip()
        if len(p) < 30:
            continue
        chunks.append(p if p.startswith("# ") else f"# {title}\n{p}")
    return chunks


def ingest():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection("support_kb")
    except Exception:
        pass
    col = client.create_collection("support_kb")

    docs, metas, ids = [], [], []
    for f in sorted(KB_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8-sig")  # BOM ho to hata deta hai
        for i, chunk in enumerate(chunk_markdown(text, f.name)):
            docs.append(chunk)
            metas.append({"source": f.name})
            ids.append(f"{f.stem}-{i}")

    if not docs:
        print("Koi KB doc nahi mila. data/kb/ mein .md files banao.")
        return

    col.add(documents=docs, metadatas=metas, ids=ids)
    print(f"Ingested {len(docs)} chunks from {len(set(m['source'] for m in metas))} files")


if __name__ == "__main__":
    ingest()