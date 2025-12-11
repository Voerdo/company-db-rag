import os
import requests
from notion_client import Client
from chroma_utils import load_and_split_document, vectorstore, text_splitter, delete_doc_from_chroma
from db_utils import insert_document_record, delete_document_record, get_all_documents
import tempfile
import uuid
from langchain_core.documents import Document
from typing import List, Tuple

NOTION_SECRET = "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"
notion = Client(auth=NOTION_SECRET)

def delete_old_notion_data(): # функция для удаления старых данных Notion перед новой синхронизацией
    try:
        print("Deleting old Notion data...")

        all_documents = get_all_documents()
        notion_documents = [doc for doc in all_documents if doc['filename'].startswith('notion_')]
        
        deleted_count = 0
        
        # Удаляем каждый документ Notion из Chroma и базы данных
        for doc in notion_documents:
            try:
                chroma_success = delete_doc_from_chroma(doc['id'])

                if chroma_success:
                    db_success = delete_document_record(doc['id'])
                    if db_success:
                        deleted_count += 1
                        print(f"  Deleted old Notion document: {doc['filename']}")
                    else:
                        print(f"  Warning: Failed to delete from DB: {doc['filename']}")
                else:
                    print(f"  Warning: Failed to delete from Chroma: {doc['filename']}")
                    
            except Exception as e:
                print(f"  Error deleting document {doc['filename']}: {e}")
        
        print(f"Deleted {deleted_count} old Notion documents")
        return deleted_count
        
    except Exception as e:
        print(f"Error deleting old Notion data: {e}")
        return 0
    
def download_file(url, file_extension): # Скачивает файл по URL и возвращает временный путь к файлу
    try:
        response = requests.get(url)
        response.raise_for_status()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        print(f"Error downloading file from {url}: {e}")
        return None

def get_page_title(page): # фунция извлекает заголовок страницы Notion
    try:
        properties = page.get('properties', {})
        
        if 'title' in properties:
            title_prop = properties['title'].get('title', [])
            if title_prop and len(title_prop) > 0:
                return title_prop[0].get('text', {}).get('content', 'Untitled Page')
        
        if 'Name' in properties:
            name_prop = properties['Name'].get('title', [])
            if name_prop and len(name_prop) > 0:
                return name_prop[0].get('text', {}).get('content', 'Untitled Page')
        
        title_array = page.get('title', [])
        if title_array and len(title_array) > 0:
            return title_array[0].get('text', {}).get('content', 'Untitled Database')
        
        return "Untitled"
    except Exception as e:
        print(f"Error getting page title: {e}")
        return "Untitled"

def extract_text_from_block(block): # функция извлекает текст из блока Notion
    block_type = block.get('type')
    content = []

    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'to_do', 'quote', 'callout']:
        rich_text = block.get(block_type, {}).get('rich_text', [])
        for text_segment in rich_text:
            text_content = text_segment.get('text', {}).get('content', '')
            if text_content:
                content.append(text_content)
    
    elif block_type == 'code':
        code_text = block.get('code', {}).get('rich_text', [])
        for text_segment in code_text:
            text_content = text_segment.get('text', {}).get('content', '')
            if text_content:
                content.append(text_content)
    
    elif block_type == 'table':
        try:
            table_blocks = notion.blocks.children.list(block['id'])
            for row in table_blocks.get('results', []):
                if row.get('type') == 'table_row':
                    cells = row.get('table_row', {}).get('cells', [])
                    for cell in cells:
                        for text_segment in cell:
                            text_content = text_segment.get('text', {}).get('content', '')
                            if text_content:
                                content.append(text_content)
        except Exception as e:
            print(f"Error processing table: {e}")
    
    return ' '.join(content)

def process_notion_block(block, page_title): # функция обрабатывает отдельный блок Notion и извлекает файлы и текст
    try:
        block_type = block.get('type')
        file_paths = []
        text_content = []

        if block_type == 'file':
            file_data = block.get('file', {})
            file_url = file_data.get('url')
            if file_url:
                file_name = file_data.get('name', 'unknown_file')
                file_extension = os.path.splitext(file_name)[1].lower()
                
                if not file_extension:
                    file_extension = determine_file_extension(file_url)
                
                if file_extension in ['.pdf', '.docx']:
                    temp_path = download_file(file_url, file_extension)
                    if temp_path:
                        file_paths.append(temp_path)

        elif block_type == 'image':
            image_data = block.get('image', {})
            image_url = image_data.get('url')
            if image_url:
                file_extension = determine_file_extension(image_url)
                if file_extension in ['.pdf', '.docx']:
                    temp_path = download_file(image_url, file_extension)
                    if temp_path:
                        file_paths.append(temp_path)
                        
        text = extract_text_from_block(block)
        if text:
            text_content.append(text)

        # Рекурсивно обрабатываем дочерние блоки
        if block.get('has_children', False):
            try:
                child_blocks = notion.blocks.children.list(block['id'])
                for child_block in child_blocks.get('results', []):
                    child_file_paths, child_text = process_notion_block(child_block, page_title)
                    file_paths.extend(child_file_paths)
                    text_content.extend(child_text)
            except Exception as e:
                print(f"Error processing child blocks: {e}")

        return file_paths, text_content
    except Exception as e:
        print(f"Error processing notion block: {e}")
        return [], []

def process_notion_page_content(page_id, page_title): # функция обрабатывает контент страницы Notion и извлекает файлы и текст
    try:
        blocks = notion.blocks.children.list(page_id)
        file_paths = []
        text_content = []
        
        for block in blocks.get('results', []):
            block_file_paths, block_text = process_notion_block(block, page_title)
            file_paths.extend(block_file_paths)
            text_content.extend(block_text)
        
        return file_paths, text_content
    except Exception as e:
        print(f"Error processing notion page {page_title}: {e}")
        return [], []

def process_page_properties(page): # фунция обрабатывает свойства страницы Notion, ища файлы в Files & Media
    try:
        file_paths = []
        properties = page.get('properties', {})
        
        for prop_name, prop_value in properties.items():
            prop_type = prop_value.get('type')
            
            if prop_type == 'files':
                files = prop_value.get('files', [])
                for file_item in files:
                    file_type = file_item.get('type')
                    file_data = file_item.get('file', {}) if file_type == 'file' else file_item.get('external', {})
                    file_url = file_data.get('url')
                    
                    if file_url:
                        file_name = file_data.get('name', 'unknown_file')
                        file_extension = os.path.splitext(file_name)[1].lower()
                        
                        if not file_extension:
                            file_extension = determine_file_extension(file_url)
                        
                        if file_extension in ['.pdf', '.docx']:
                            temp_path = download_file(file_url, file_extension)
                            if temp_path:
                                file_paths.append(temp_path)
        
        return file_paths
    except Exception as e:
        print(f"Error processing page properties: {e}")
        return []

def process_single_page(page_id, page_title): # функция обрабатывает одну страницу Notion: извлекает файлы и текст
    print(f"  Processing page content: {page_title}")
    page_file_paths, page_text = process_notion_page_content(page_id, page_title)
    return page_file_paths, page_text

def process_database_pages(database_id, database_title): # функция обрабатывает все страницы в базе данных Notion
    try:
        pages = notion.databases.query(database_id)
        all_file_paths = []
        all_text_content = []
        
        for page in pages.get('results', []):
            page_title = get_page_title(page)
            print(f"  Processing database page: {page_title}")

            property_files = process_page_properties(page)
            all_file_paths.extend(property_files)

            page_file_paths, page_text = process_notion_page_content(page['id'], page_title)
            all_file_paths.extend(page_file_paths)
            all_text_content.extend(page_text)
        
        return all_file_paths, all_text_content
    except Exception as e:
        print(f"Error processing database pages {database_title}: {e}")
        return [], []

def determine_file_extension(url): # функция определяет расширение файла по URL
    try:
        path = requests.utils.urlparse(url).path
        extension = os.path.splitext(path)[1].lower()
        if extension in ['.pdf', '.docx', '.doc']:
            return extension
        
        try:
            response = requests.head(url, timeout=5)
            content_type = response.headers.get('content-type', '').lower()
            
            if 'pdf' in content_type:
                return '.pdf'
            elif 'word' in content_type or 'docx' in content_type:
                return '.docx'
            elif 'msword' in content_type:
                return '.doc'
        except:
            pass
        
        return '.bin'
    except:
        return '.bin'

def index_text_content(text_content, source_name): # функция индексирует текстовый контент в Chroma
    if not text_content:
        return 0
    
    try:
        full_text = "\n".join([text for text in text_content if text.strip()])
        if not full_text.strip():
            return 0

        text_doc = Document(
            page_content=full_text,
            metadata={
                'file_id': f"notion_text_{uuid.uuid4().hex[:8]}",
                'source': source_name
            }
        )

        splits = text_splitter.split_documents([text_doc])

        for i, split in enumerate(splits):
            split.metadata['chunk_id'] = i

        if splits:
            vectorstore.add_documents(splits)
            print(f"    Successfully indexed text from {source_name} ({len(splits)} chunks)")
            insert_document_record(f"notion_text_{source_name}_{uuid.uuid4().hex[:8]}")
            return 1
    
    except Exception as e:
        print(f"Error indexing text content for {source_name}: {e}")
    
    return 0

def index_notion(): # Основная функция для индексации данных из Notion
    try:
        print("Starting Notion indexing...")

        delete_old_notion_data()
        search_results = notion.search(query="")    
        all_file_paths = []
        indexed_count = 0

        for item in search_results.get('results', []):
            object_type = item.get('object')
            
            if object_type == 'page':
                page_title = get_page_title(item)
                print(f"Processing standalone page: {page_title}")
                page_files, page_text = process_single_page(item['id'], page_title)
                all_file_paths.extend(page_files)

                if page_text:
                    indexed_count += index_text_content(page_text, f"page_{page_title}")
                property_files = process_page_properties(item)
                all_file_paths.extend(property_files)
                
            elif object_type == 'database':
                database_title = get_page_title(item)
                print(f"Processing database: {database_title}")
                database_files, database_text = process_database_pages(item['id'], database_title)
                all_file_paths.extend(database_files)
                
                if database_text:
                    indexed_count += index_text_content(database_text, f"database_{database_title}")

        for file_path in all_file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    file_id = insert_document_record(f"notion_{os.path.basename(file_path)}_{uuid.uuid4().hex[:8]}")
                    splits = load_and_split_document(file_path)

                    for split in splits:
                        split.metadata['file_id'] = file_id
                        split.metadata['source'] = f"notion_{os.path.basename(file_path)}"

                    if splits:
                        vectorstore.add_documents(splits)
                        indexed_count += 1
                        print(f"Successfully indexed file: {os.path.basename(file_path)}")

                    os.unlink(file_path)
                    
                except Exception as e:
                    print(f"Error indexing file {file_path}: {e}")
                    if os.path.exists(file_path):
                        os.unlink(file_path)

        print(f"Notion indexing completed. Indexed {indexed_count} files and text documents.")
        return indexed_count
        
    except Exception as e:
        print(f"Error during Notion indexing: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return 0