"""Query one or many projects."""

from __future__ import annotations
import argparse
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.retrievers.merger import MergerRetriever
from langchain.chains import create_retrieval_chain

from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL

def build_retriever(project: str, root_index: Path) -> MergerRetriever:
    vectordb = Chroma(
        persist_directory=str(root_index / project),
        collection_name=project,
        embedding_function=OpenAIEmbeddings(model=EMBED_MODEL),
    )
    return vectordb.as_retriever(search_kwargs={"k": 4})

def main() -> None:
    ap = argparse.ArgumentParser(description="Query one or several RAG projects")
    ap.add_argument("question", help="Your natural-language prompt")
    ap.add_argument("--projects", nargs="+", required=True, help="Project name(s) to search")
    ap.add_argument("--root-index", type=Path, default=INDEX_DIR)
    args = ap.parse_args()

    retrievers = [build_retriever(p, args.root_index) for p in args.projects]
    combo = MergerRetriever(retrievers=retrievers)

    chain = create_retrieval_chain(ChatOpenAI(model=CHAT_MODEL, temperature=0), combo)
    print(chain.invoke({"input": args.question})["answer"])

if __name__ == "__main__":
    main()
