RAG — Chat with Your PDFs
Minimal Retrieval-Augmented Generation stack that runs locally and lets you keep completely separate projects (court cases, statutes library, personal brief style, etc.).

✨ What this repo does
Parses every PDF (text first, OCR fallback) with unstructured — strategy="fast" extracts embedded text and auto-OCRs pages that lack it. 
Unstructured

Chunks & embeds the text (~800 tokens) via OpenAI text-embedding-3-large ( $0.13 / M tokens ). 
OpenAI Platform

Stores vectors in a per-project Chroma collection on disk for millisecond retrieval. 
LangChain Python API

Answers questions with GPT-4o (or any LangChain-compatible LLM).

Ships a FastAPI server so you can chat in the browser at /docs.

🗂 Directory layout
sql
Copy
Edit
rag/                   ← repo root
├── src/
│   ├── ingest.py      ← build/update one project
│   ├── query.py       ← query one OR many projects
│   └── server.py
├── index/             ← parent folder for all projects
│   ├── smith_case/    ← vectors for project “smith_case”
│   └── statutes/      ← vectors for project “statutes”
├── requirements.txt
├── .env.example
└── README.md
⚙️ Install
bash
Copy
Edit
cd ~/projects/rag
conda create -n rag python=3.11 -y
conda activate rag
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
1️⃣ Ingest (project-scoped)
bash
Copy
Edit
# first time
python -m src.ingest --pdf-dir ~/cases/Smith_v_Jones --project smith_case

# incremental: add one PDF, run same command → SHA-256 dedup skips re-embedding
ingest.py creates (or re-opens) index/<project>/ and stores a SHA-256 hash in metadata; duplicates are skipped using a where filter. 
Reddit

Text splitter now expects langchain.schema.Document objects, preventing the AttributeError you saw. 
LangChain

2️⃣ Query
bash
Copy
Edit
# ask one project
python -m src.query "What did the judge decide on Rule 56?" \
                    --projects smith_case

# ask multiple projects at once
python -m src.query "Does anything override Smith v. Jones?" \
                    --projects statutes smith_case
query.py builds a MergerRetriever that merges results from each project’s retriever. 
LangChain
LangChain Python API

⚖️ Authority weighting (statutes > filings)
Hierarchical – query statutes first; if docs are returned, skip others.

Metadata weight – store priority=2 vs 1 and switch to EnsembleRetriever for weighted voting. 
Stack Overflow

Prompt rule – system message: “If statutes conflict with filings, statutes prevail.” 
GitHub

Combine 2 + 3 for highest reliability.

🌐 Run the chat service
bash
Copy
Edit
uvicorn src.server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/docs
🔄 Nightly cron (example)
cron
Copy
Edit
0 2 * * * source ~/miniconda3/etc/profile.d/conda.sh && \
          conda run -n rag python -m src.ingest \
          --pdf-dir /data/statutes --project statutes \
          --root-index ~/projects/rag/index
🛠 GitHub quick-push
bash
Copy
Edit
git add README.md src/ingest.py src/query.py
git commit -m "feat: project flag, multi-project querying, README update"
git push   # first push?  git push -u origin main
(Each repo’s .git/ folder is isolated, so this won’t affect your other project.) 
Python documentation

Troubleshooting
Issue	Fix
ModuleNotFoundError: langchain_community	pip install -U langchain-community langchain-core 
Stack Overflow
pdfminer colour-space spam	Already silenced in src/ingest.py; raise to CRITICAL if needed.
Slow first import	Ensure iso-639>=0.5.0 (cached TSV). 
Python documentation

MIT License — Happy indexing!