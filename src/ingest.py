"""PDF → vector-store indexer
   ------------------------------------------
   • Recursively crawls --pdf-dir
   • Extracts text via unstructured (strategy='fast')
       → auto-OCRs only pages with no text
   • Skips pdfminer colour-space spam + telemetry
   • Builds / updates a **project-scoped** Chroma collection
"""

from __future__ import annotations          # must stay first!

# ── stdlib ------------------------------------------------------------------
import argparse, hashlib, logging, os
from pathlib import Path
from typing import Sequence

# silence noisy libs & telemetry
logging.getLogger("pdfminer").setLevel(logging.ERROR)
os.environ["SCARF_NO_ANALYTICS"] = "true"

# ── third-party -------------------------------------------------------------
from tqdm import tqdm
from unstructured.partition.pdf import partition_pdf
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# ── local -------------------------------------------------------------------
from .config import INDEX_DIR, EMBED_MODEL
from .logger import get_logger

LOGGER = get_logger(__name__)

# ── helpers -----------------------------------------------------------------
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_pdf(path: Path, *, strategy: str = "fast") -> Sequence[str]:
    """Return text for a single PDF.  'fast' auto-OCRs scanned pages."""
    return [
        el.text
        for el in partition_pdf(filename=str(path), strategy=strategy)
        if el.text and not el.text.isspace()
    ]


# ── main ingest -------------------------------------------------------------
def ingest(*, pdf_dir: Path, project: str, root_index: Path = INDEX_DIR, chunk_size: int = 800) -> None:
    proj_dir = root_index / project          # e.g. ./index/smith_case/
    proj_dir.mkdir(parents=True, exist_ok=True)

    db = Chroma(
        persist_directory=str(proj_dir),
        collection_name=project,
        embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
    )

    existing = {
        m.get("sha256") for m in db.get()["metadatas"] if "sha256" in m
    }

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=120)
    new_docs: list[Document] = []

    pdfs = list(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        LOGGER.error("No PDFs found in %s", pdf_dir)
        return

    for pdf in tqdm(pdfs, desc="Parsing PDFs"):
        digest = sha256(pdf)
        if digest in existing:
            continue        # already embedded

        for text in load_pdf(pdf):
            new_docs.append(
                Document(
                    page_content=text,
                    metadata={"source": pdf.name, "sha256": digest},
                )
            )

    if not new_docs:
        LOGGER.info("No new PDFs to embed for project '%s'", project)
        return

    LOGGER.info("Splitting into chunks …")
    chunks = splitter.split_documents(new_docs)
    LOGGER.info("Embedding %d new chunks", len(chunks))

    db.add_documents(chunks)
    db.persist()
    LOGGER.info("✅ Finished ingest for %s (stored at %s)", project, proj_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest PDFs into a project collection")
    ap.add_argument("--pdf-dir", type=Path, required=True, help="Directory of PDFs (recursive)")
    ap.add_argument("--project", required=True, help="Project name (court_case, statutes, etc.)")
    ap.add_argument("--root-index", type=Path, default=INDEX_DIR, help="Folder holding all projects")
    args = ap.parse_args()

    ingest(pdf_dir=args.pdf_dir, project=args.project, root_index=args.root_index)
