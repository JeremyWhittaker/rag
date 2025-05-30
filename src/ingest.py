"""PDF → vector index builder for the RAG stack."""

from __future__ import annotations   # ← keep this the first live line!

# ── stdlib tweaks -----------------------------------------------------------
import os
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)   # silence colour-space spam
os.environ["SCARF_NO_ANALYTICS"] = "true"               # opt-out of Unstructured telemetry

# ── 3rd-party ---------------------------------------------------------------
import argparse
from pathlib import Path
from typing import Sequence

from tqdm import tqdm
from unstructured.partition.pdf import partition_pdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# ── local -------------------------------------------------------------------
from .config import INDEX_DIR, EMBED_MODEL
from .logger import get_logger

LOGGER = get_logger(__name__)

# ---------------------------------------------------------------------------


def load_pdf(path: Path, strategy: str = "fast") -> Sequence[str]:
    """
    Extract text from a PDF.  The 'fast' strategy uses pdfminer but
    *automatically* falls back to OCR for pages with no extractable text
    (Unstructured docs).  No manual detection needed.
    """
    return [
        el.text
        for el in partition_pdf(filename=str(path), strategy=strategy)
        if el.text and not el.text.isspace()
    ]


def ingest(pdf_dir: Path, *, index_dir: Path = INDEX_DIR, chunk_size: int = 800) -> None:
    """Walk `pdf_dir`, embed/chunk, and persist to a Chroma collection."""
    pdfs = list(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        LOGGER.error("No PDFs found in %s", pdf_dir)
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=120)
    docs = []

    for pdf in tqdm(pdfs, desc="Parsing PDFs"):
        for text in load_pdf(pdf):
            docs.append({"page_content": text, "metadata": {"source": pdf.name}})

    LOGGER.info("Splitting into %d total chunks …", len(docs))
    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    Chroma.from_documents(
        chunks,
        embedding_function=embeddings,
        persist_directory=str(index_dir),
        collection_name="pdf_kb",
    )
    LOGGER.info("✅ Index stored at %s", index_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest a directory of PDFs")
    ap.add_argument("--pdf-dir", type=Path, required=True)
    ap.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    args = ap.parse_args()
    ingest(args.pdf_dir, index_dir=args.index_dir)
