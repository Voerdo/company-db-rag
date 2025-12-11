import streamlit as st
from api_utils import get_api_response

def display_chat_interface():
    for message in st.session_state.messages:
        avatar = message.get("avatar")
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ваш вопрос"):
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt, 
            "avatar": "👤"
        })
        
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.spinner("Поиск ответа..."):
            response = get_api_response(prompt, st.session_state.session_id, st.session_state.model)
            
            if response:
                st.session_state.session_id = response.get('session_id')
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response['answer'], 
                    "avatar": "💬"
                })
                
                with st.chat_message("assistant", avatar="💬"):
                    st.markdown(response['answer'])
                    
                    with st.expander("Details"):
                        st.subheader("Generated Answer")
                        st.code(response['answer'])
                        st.subheader("Model Used")
                        st.code(response['model'])
                        st.subheader("Session ID")
                        st.code(response['session_id'])
            else:
                st.error("Failed to get a response from the API. Please try again.")