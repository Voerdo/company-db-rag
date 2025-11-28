from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from chroma_utils import vectorstore

retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

qa_prompt = ChatPromptTemplate.from_messages([
    (
            "system",
            "Answer ONLY based on the document snippets below. "
            "If the snippets do not contain the answer – say exactly: "
            "'I don't have enough information in the provided documents to answer this question.' "
            "Never use outside knowledge. Cite the source at the end [source: ...]\n\n"
            "Snippets:\n{context}",
        ),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}")
])

document_prompt = PromptTemplate.from_template(
    "Источник: {source}\n{page_content}"
)

def get_rag_chain(model="llama3.2"):
    llm = ChatOllama(model=model, temperature=0)
    history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt, document_prompt=document_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)    
    return rag_chain
