import streamlit as st
from api_utils import  list_documents, delete_document, sync_notion, get_sync_status
import time

def display_sidebar():
    
    # Sidebar: Notion Integration
    st.sidebar.header("Интеграция с Notion")
    
    if st.sidebar.button("Синхронизировать с Notion"):
        with st.spinner("Запуск синхронизации с Notion..."):
            sync_response = sync_notion()
            if sync_response:
                task_id = sync_response.get('task_id')
                st.sidebar.success(f"Синхронизация запущена! Task ID: {task_id}")
                st.session_state.notion_task_id = task_id

                track_sync_status(task_id)
            else:
                st.sidebar.error("Не удалось запустить синхронизацию с Notion")

    # Показываем статус синхронизации, если есть активная задача
    if hasattr(st.session_state, 'notion_task_id'):
        st.sidebar.info(f"Active Notion sync task: {st.session_state.notion_task_id}")
        
        if st.sidebar.button("Проверить статус синхронизации"):
            status_response = get_sync_status(st.session_state.notion_task_id)
            if status_response:
                status = status_response.get('status', 'unknown')
                st.sidebar.write(f"Статус: {status}")
                
                if "completed" in status:
                    st.sidebar.success("Синхронизация завершена!")
                    # Обновляем список документов
                    st.session_state.documents = list_documents()
                elif "failed" in status:
                    st.sidebar.error("Синхронизация завершилась с ошибкой")
                elif "running" in status:
                    st.sidebar.info("Синхронизация в процессе...")

    # Sidebar: List Documents
    st.sidebar.header("Доступные документы")
    if st.sidebar.button("Обновить"):
        with st.spinner("Обновление.."):
            st.session_state.documents = list_documents()

    # Initialize document list if not present
    if "documents" not in st.session_state:
        st.session_state.documents = list_documents()

    documents = st.session_state.documents
    if documents:
        for doc in documents:
            st.sidebar.text(f"{doc['filename']} (ID: {doc['id']}, Uploaded: {doc['upload_timestamp']})")
        
        # Delete Document
        selected_file_id = st.sidebar.selectbox("Документы для удаления:", options=[doc['id'] for doc in documents], format_func=lambda x: next(doc['filename'] for doc in documents if doc['id'] == x))
        if st.sidebar.button("Удалить выбранный"):
            with st.spinner("Удаление.."):
                delete_response = delete_document(selected_file_id)
                if delete_response:
                    st.sidebar.success(f"Документ с ID {selected_file_id} успешно удалён.")
                    st.session_state.documents = list_documents()
                else:
                    st.sidebar.error(f"Ошибка удаления документы с ID {selected_file_id}.")

def track_sync_status(task_id): # Отслеживает статус синхронизации с Notion
    status_placeholder = st.sidebar.empty()
    
    for i in range(30):
        status_response = get_sync_status(task_id)
        if status_response:
            status = status_response.get('status', 'unknown')
            status_placeholder.info(f"Статус синхронизации: {status}")
            
            if "completed" in status or "failed" in status:
                break
        
        time.sleep(1)

    status_response = get_sync_status(task_id)
    if status_response:
        final_status = status_response.get('status', 'unknown')
        if "completed" in final_status:
            status_placeholder.success(f"Синхронизация завершена! {final_status}")
        elif "failed" in final_status:
            status_placeholder.error(f"Синхронизация завершилась с ошибкой: {final_status}")
        else:
            status_placeholder.warning(f"Статус: {final_status}")
