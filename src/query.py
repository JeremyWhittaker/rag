import argparse
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import create_retrieval_chain
from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL

def main():
    p=argparse.ArgumentParser(); p.add_argument("question"); args=p.parse_args()
    db=Chroma(persist_directory=str(INDEX_DIR), embedding_function=OpenAIEmbeddings(model=EMBED_MODEL))
    chain=create_retrieval_chain(ChatOpenAI(model=CHAT_MODEL, temperature=0), db.as_retriever(search_kwargs={"k":4}))
    print(chain.invoke({"input": args.question})["answer"])

if __name__=="__main__":
    main()
