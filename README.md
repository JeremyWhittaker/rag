# RAG — Chat with Your PDFs  
*Minimal Retrieval-Augmented Generation stack that runs locally.*

---

## ✨ What this repo does

1. **Parses** every PDF (text first, OCR fallback) with *unstructured*.  
2. **Chunks & embeds** the text (≈ 800 tokens) via OpenAI `text-embedding-3-large`.  
3. **Stores vectors** in a local **Chroma** index for fast semantic search.  
4. **Answers questions** with GPT-4o (or any LLM supported by LangChain).  
5. Ships a **FastAPI** server so you can chat in the browser at `/docs`.

---

## 🗂 Directory layout

```
rag/                    ← your project folder
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── ingest.py
│   ├── query.py
│   ├── server.py
│   └── …
└── index/              ← auto-created vector store
```

---

## ⚙️ Install

```bash
# clone or move into the folder you've named 'rag'
cd ~/projects/rag

# create & activate env
conda create -n rag python=3.11 -y
conda activate rag

# install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔑 Configuration

```bash
cp .env.example .env
$EDITOR .env          # add your OPENAI_API_KEY
```

---

## 📥 Build (or rebuild) the index

```bash
python -m src.ingest --pdf-dir /absolute/path/to/my_pdfs
```

*Uses `strategy="fast"` so pages with no embedded text are automatically OCR’d.*

---

## 💬 Ask questions (CLI)

```bash
python -m src.query "Give me the key findings from the 2024 audit report."
```

---

## 🌐 Run the chat API

```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/docs
```

---

## 🔄 Nightly re-index (optional)

```bash
# edit crontab
crontab -e
# add:
0 2 * * * source ~/miniconda3/etc/profile.d/conda.sh && \
          conda run -n rag python -m src.ingest --pdf-dir /path/to/pdfs
```

---

## 🛠 GitHub quick-push (one time)

```bash
cd ~/projects/rag
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:<USER>/rag.git
git push -u origin main
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: langchain_community` | `pip install -U langchain-community langchain-core` |
| pdfminer warning spam | Already silenced in `src/ingest.py`; raise level to CRITICAL if needed |
| Slow import on first run | Ensure `iso-639>=0.5.0` is installed |

---

MIT License — Happy indexing!
