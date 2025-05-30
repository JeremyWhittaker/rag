from fastapi import FastAPI, Query
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import create_retrieval_chain
from .config import INDEX_DIR, CHAT_MODEL, EMBED_MODEL
app=FastAPI(title="PDF Chat")
chain=create_retrieval_chain(ChatOpenAI(model=CHAT_MODEL, temperature=0), Chroma(persist_directory=str(INDEX_DIR), embedding_function=OpenAIEmbeddings(model=EMBED_MODEL)).as_retriever(search_kwargs={"k":4}))
@app.get("/ask")
async def ask(q: str = Query(...)):
    return {"answer": chain.invoke({"input": q})["answer"]}
