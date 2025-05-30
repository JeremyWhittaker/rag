"""Query one or many projects with a retrieval-augmented chain."""

from __future__ import annotations
import argparse
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL


def build_retriever(project: str, root: Path):
    """Open a project-specific Chroma collection and return its retriever."""
    db = Chroma(
        persist_directory=str(root / project),
        collection_name=project,
        embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
    )
    return db.as_retriever(search_kwargs={"k": 4})


def main() -> None:
    ap = argparse.ArgumentParser(description="Query one or multiple RAG projects")
    ap.add_argument("question", help="Natural-language prompt")
    ap.add_argument("--projects", nargs="+", required=True,
                    help="Project name(s) given at ingest time")
    ap.add_argument("--root-index", type=Path, default=INDEX_DIR)
    args = ap.parse_args()

    # 1️⃣  Build a merged retriever
    retrievers = [build_retriever(p, args.root_index) for p in args.projects]
    retriever = MergerRetriever(retrievers=retrievers)

    # 2️⃣  Build the combine-documents chain (LLM + prompt)
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
    prompt = ChatPromptTemplate.from_template(
        "Use the following context to answer the question.\n\n{context}\n\nQuestion: {input}"
    )
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)

    # 3️⃣  Assemble the full retrieval chain
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

    # 4️⃣  Invoke with a dict that matches the prompt keys
    result = rag_chain.invoke({"input": args.question})
    print("\nANSWER:\n" + result["answer"])


if __name__ == "__main__":
    main()
