import streamlit as st
from sidebar2 import display_sidebar
from chat_interface import display_chat_interface

st.title("RAG. База знаний компании.")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = None
    
if "model" not in st.session_state:
    st.session_state.model = "llama3.2"

with st.sidebar:
    display_sidebar()

display_chat_interface()

# uvicorn main:app --reload
# streamlit run streamlit_app.py