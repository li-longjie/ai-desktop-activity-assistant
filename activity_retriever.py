# activity_retriever.py

import json
import os
import logging
from datetime import datetime, timedelta
import sqlite3
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions
from dateparser.search import search_dates

# 检查是否应该加载嵌入模型（可以通过环境变量控制）
LOAD_EMBEDDINGS = os.getenv('LOAD_EMBEDDINGS', 'true').lower() == 'true'

if LOAD_EMBEDDINGS:
    try:
        # 优先使用自定义嵌入模块（更稳定）
        from custom_embeddings import init_embeddings, search_similar, add_documents, clear_collection, get_collection_count, get_all_documents
        USE_LANGCHAIN = False
        logging.info("使用自定义嵌入模块")
    except ImportError:
        try:
            # 降级使用标准LangChain（Python 3.12+）
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma
            USE_LANGCHAIN = True
            logging.info("使用 langchain-huggingface (Python 3.12+)")
        except ImportError:
            USE_LANGCHAIN = False
            logging.error("无法导入任何嵌入模块")
else:
    USE_LANGCHAIN = False

from llm_service import LLMService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- File Paths and Constants ---
# 从配置文件读取路径
try:
    from gui_config import gui_config
    SCREENSHOT_DIR = gui_config.get('paths.screenshot_directory', 'screen_recordings')
    CHROMA_DB_PATH = gui_config.get('paths.database_directory', 'chroma_db_activity')
except ImportError:
    SCREENSHOT_DIR = "screen_recordings"
    CHROMA_DB_PATH = "chroma_db_activity"

DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db")
COLLECTION_NAME = "screen_activity"

# --- Global Variables (used for initialization) ---
embeddings = None
activity_vector_store = None
collection = None

# --- Initialization ---
if LOAD_EMBEDDINGS:
    try:
        if USE_LANGCHAIN:
            # 使用标准LangChain（Python 3.12+）
            embeddings = HuggingFaceEmbeddings(
                model_name="Alibaba-NLP/gte-multilingual-base",
                model_kwargs={'device': 'cpu', 'trust_remote_code': True},
                encode_kwargs={'normalize_embeddings': True}
            )
            logging.info("嵌入模型加载成功。")

            activity_vector_store = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
                persist_directory=CHROMA_DB_PATH
            )
            collection = activity_vector_store._collection
            logging.info(f"成功连接到ChromaDB并获取/创建集合: {COLLECTION_NAME} at {CHROMA_DB_PATH}")
        else:
            # 使用自定义嵌入模块
            success = init_embeddings()
            if success:
                embeddings = True  # 标记已初始化
                activity_vector_store = True  # 标记已初始化
                collection = True  # 标记已初始化
                logging.info("自定义嵌入模型和ChromaDB初始化成功")
            else:
                raise RuntimeError("自定义嵌入模块初始化失败")

    except Exception as e:
        logging.error(f"嵌入模型初始化失败: {e}", exc_info=True)
        # Reset globals on failure
        embeddings = None
        activity_vector_store = None
        collection = None
else:
    logging.info("跳过嵌入模型加载（LOAD_EMBEDDINGS=false）")

def create_db_connection():
    """Creates a connection to the SQLite database."""
    conn = None
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        logging.error(f"连接SQLite数据库失败 ({DATABASE_FILE}): {e}")
    return conn

def load_and_index_activity_data() -> int:
    """Loads and indexes data from SQLite to ChromaDB on startup."""
    # 检查是否跳过数据索引（用于快速启动）
    SKIP_INDEXING = os.getenv('SKIP_INDEXING', 'false').lower() == 'true'
    if SKIP_INDEXING:
        logging.info("⏩ 跳过数据索引（SKIP_INDEXING=true），使用现有数据")
        return 0
    
    if not LOAD_EMBEDDINGS or collection is None or embeddings is None:
        logging.error("ChromaDB collection or embeddings not initialized. Cannot index data.")
        return 0

    conn = create_db_connection()
    if not conn:
        return 0

    new_records_count = 0
    try:
        # 检查现有数据
        if USE_LANGCHAIN:
            existing_count = len(collection.get(include=[])['ids'])
            existing_ids_set = set(collection.get(include=[])['ids'])
        else:
            existing_count = get_collection_count()
            existing_data = get_all_documents()
            existing_ids_set = set(doc.get('id', '') for doc in existing_data) if existing_data else set()
        
        # 强制重新索引的情况
        FORCE_REINDEX = os.getenv('FORCE_REINDEX', 'false').lower() == 'true'
        if FORCE_REINDEX:
            logging.info("🔄 强制重新索引所有数据...")
            
            if USE_LANGCHAIN:
                existing_ids = collection.get(include=[])['ids']
                if existing_ids:
                    collection.delete(ids=existing_ids)
            else:
                clear_collection()
            existing_ids_set = set()

        # 从SQLite加载所有记录
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, ocr_text, app_name, window_title, screenshot_path FROM activity_log WHERE ocr_text IS NOT NULL AND ocr_text != ''")
        records = cursor.fetchall()

        if not records:
            return 0

        # 找出新记录
        new_documents = []
        new_metadatas = []
        new_ids = []
        
        for row in records:
            record = dict(row)
            record_id = f"activity_{record['id']}"
            
            # 只处理新记录
            if record_id not in existing_ids_set:
                doc_text = f"应用: {record.get('app_name')} | 窗口: {record.get('window_title')} | 内容: {record.get('ocr_text')}"
                new_documents.append(doc_text)

                metadata = {k: str(v) for k, v in record.items() if v is not None}
                try:
                    if 'timestamp' in metadata:
                        metadata['timestamp'] = datetime.fromisoformat(record['timestamp']).timestamp()
                except (TypeError, ValueError):
                    logging.warning(f"Could not parse timestamp for record {record.get('id')}.")
                    if 'timestamp' in metadata:
                        del metadata['timestamp']
                
                new_metadatas.append(metadata)
                new_ids.append(record_id)

        # 只有新记录时才添加到ChromaDB
        if new_documents:
            if USE_LANGCHAIN:
                collection.add(documents=new_documents, metadatas=new_metadatas, ids=new_ids)
            else:
                add_documents(documents=new_documents, metadatas=new_metadatas, ids=new_ids)
            new_records_count = len(new_documents)

    except Exception as e:
        logging.error(f"Error during data indexing: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
    
    return new_records_count

def parse_time_range_from_query(query_text: str) -> tuple[datetime, datetime]:
    """Parses a time range from the user's query."""
    now = datetime.now()
    start_time, end_time = now - timedelta(days=1), now

    # 优先处理常见的中文时间表达
    if "今天" in query_text:
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
        logging.info(f"解析'今天': {start_time} 到 {end_time}")
        return start_time, end_time
    
    if "昨天" in query_text:
        yesterday = now - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        logging.info(f"解析'昨天': {start_time} 到 {end_time}")
        return start_time, end_time

    # 使用正则表达式处理 "最近X分钟/小时/天" 或 "过去X分钟/小时/天"
    # 支持数字和部分中文数字（一至十）
    num_map_chinese_to_int = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    # 匹配例如: "过去5分钟", "最近一小时", "过去十天", "最近五分钟"
    match_duration = re.search(r"(?:最近|过去)([\d一二三四五六七八九十]+)\s*(分钟|小时|天|周|月)", query_text)

    if match_duration:
        value_str = match_duration.group(1)
        unit = match_duration.group(2)
        value = 0

        if value_str in num_map_chinese_to_int:
            value = num_map_chinese_to_int[value_str]
        else:
            try:
                value = int(value_str)
            except ValueError:
                logging.warning(f"无法从 '{value_str}' 解析数字用于时间范围查询。")
                value = 0 
        
        if value > 0:
            if unit == "分钟":
                start_time = now - timedelta(minutes=value)
            elif unit == "小时":
                start_time = now - timedelta(hours=value)
            elif unit == "天":
                start_time = now - timedelta(days=value)
            elif unit == "周":
                start_time = now - timedelta(weeks=value)
            elif unit == "月": # 近似月份
                start_time = now - timedelta(days=value * 30)
            end_time = now
            logging.info(f"通过正则表达式解析时间: 值={value}, 单位='{unit}'. 计算时间范围: {start_time} 到 {end_time}")
    else:
        # 如果没有特定的时间表达式，默认使用过去24小时
        start_time = now - timedelta(days=1)
        end_time = now
        logging.info(f"使用默认时间范围(过去24小时): {start_time} 到 {end_time}")
    
    return start_time, end_time

# --- Main Class for Activity Retrieval ---
class ActivityRetriever:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        # Check if embeddings are initialized
        if not LOAD_EMBEDDINGS or embeddings is None:
            raise RuntimeError("ActivityRetriever cannot be initialized because the embeddings failed to load.")

    async def retrieve_and_answer(self, user_query: str) -> tuple[str, list]:
        """
        Retrieves relevant activities based on a user query and uses an LLM to answer.
        This is the core logic method.
        """
        start_time_dt, end_time_dt = parse_time_range_from_query(user_query)
        logging.info(f"Searching for activities between {start_time_dt} and {end_time_dt}")

        try:
            if USE_LANGCHAIN:
                # 使用LangChain模式搜索
                filter_dict = {
                    "$and": [
                        {"timestamp": {"$gte": start_time_dt.timestamp()}},
                        {"timestamp": {"$lte": end_time_dt.timestamp()}}
                    ]
                }
                
                search_results = activity_vector_store.similarity_search_with_score(
                    query=user_query,
                    k=25,
                    filter=filter_dict
                )
                
                docs = [doc for doc, score in search_results]
            else:
                # 使用自定义模块搜索
                where_filter = {
                    "$and": [
                        {"timestamp": {"$gte": start_time_dt.timestamp()}},
                        {"timestamp": {"$lte": end_time_dt.timestamp()}}
                    ]
                }
                
                results = search_similar(query=user_query, k=25, where_filter=where_filter)
                
                # Convert to document format
                docs = []
                for result in results:
                    doc = type('Document', (), {
                        'page_content': result['page_content'],
                        'metadata': result['metadata']
                    })()
                    docs.append(doc)

        except Exception as e:
            logging.error(f"Error during similarity search: {e}", exc_info=True)
            return "Failed to search for activities in the vector database.", []
        
        if not docs:
            return f"在时间范围 {start_time_dt.strftime('%Y-%m-%d %H:%M')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M')} 内没有找到相关的活动记录。", []

        screenshots = [doc.metadata.get('screenshot_path') for doc in docs if doc.metadata.get('screenshot_path')]
        
        context_parts = []
        for doc in docs:
            ts = doc.metadata.get('timestamp')
            # Format timestamp back to a readable string if it's a number
            try:
                readable_ts = datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                readable_ts = str(ts) # Fallback to original string if conversion fails
            
            context_parts.append(f"### {readable_ts}\n{doc.page_content}")

        context = "\n\n".join(context_parts)

        if not context.strip():
            return f"在时间范围 {start_time_dt.strftime('%Y-%m-%d %H:%M')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M')} 内找到了活动，但没有识别出的文本内容。", screenshots

        prompt_template = """你是一个智能个人助手。你的任务是基于以下由 OmniParser 生成的屏幕活动日志来回答用户的问题。
这些日志包含了通过视觉分析屏幕识别出的UI元素、文本和图标。请利用这些详细信息来提供精准的回答。

---
【屏幕活动日志】
{context}
---

【用户问题】
{query}
"""
        final_prompt = prompt_template.format(context=context, query=user_query)

        if self.llm_service:
            try:
                response = await self.llm_service.get_response(final_prompt)
                return response, screenshots
            except Exception as e:
                logging.warning(f"LLM服务调用失败: {e}，将返回原始数据摘要")
                # 如果LLM失败，返回简单的数据摘要
                return self._generate_simple_summary(docs, start_time_dt, end_time_dt), screenshots
        else:
            return self._generate_simple_summary(docs, start_time_dt, end_time_dt), screenshots
    
    def _generate_simple_summary(self, docs, start_time_dt, end_time_dt) -> str:
        """生成简单的数据摘要（当LLM不可用时使用）"""
        if not docs:
            return f"在时间范围 {start_time_dt.strftime('%Y-%m-%d %H:%M')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M')} 内没有找到相关记录。"
        
        # 统计应用使用情况
        apps = {}
        timestamps = []
        
        for doc in docs:
            metadata = doc.metadata
            app_name = metadata.get('app_name', 'Unknown')
            timestamp = metadata.get('timestamp', 0)
            
            if app_name != 'Unknown':
                apps[app_name] = apps.get(app_name, 0) + 1
            
            try:
                timestamps.append(float(timestamp))
            except (ValueError, TypeError):
                pass
        
        # 生成摘要
        time_range = f"{start_time_dt.strftime('%Y-%m-%d %H:%M')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M')}"
        summary_parts = [f"📅 时间范围: {time_range}", f"📊 找到 {len(docs)} 条活动记录"]
        
        if apps:
            summary_parts.append("🎯 主要应用:")
            for app, count in sorted(apps.items(), key=lambda x: x[1], reverse=True):
                summary_parts.append(f"   • {app}: {count} 次记录")
        
        if timestamps:
            timestamps.sort(reverse=True)
            latest_time = datetime.fromtimestamp(timestamps[0]).strftime('%H:%M:%S')
            earliest_time = datetime.fromtimestamp(timestamps[-1]).strftime('%H:%M:%S')
            summary_parts.append(f"⏰ 活动时间: {earliest_time} - {latest_time}")
        
        return "\n".join(summary_parts)

# --- Standalone Functions for API Endpoints ---
def get_all_activity_records(limit: int = 50) -> list:
    """Retrieves all activity records from the SQLite database."""
    conn = create_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if conn: conn.close()

async def get_application_usage_summary(start_time_dt: datetime, end_time_dt: datetime) -> dict:
    """Calculates application usage summary within a given time range."""
    conn = create_db_connection()
    if not conn: return {"error": "Database connection failed."}

    summary = defaultdict(timedelta)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, app_name FROM activity_log WHERE timestamp BETWEEN ? AND ? AND app_name IS NOT NULL ORDER BY timestamp ASC",
            (start_time_dt.isoformat(), end_time_dt.isoformat())
        )
        events = [dict(row) for row in cursor.fetchall()]

        if not events: return {"usage": {}}

        for i, event in enumerate(events):
            start = datetime.fromisoformat(event['timestamp'])
            end = datetime.fromisoformat(events[i+1]['timestamp']) if i + 1 < len(events) else end_time_dt
            duration = end - start
            if duration.total_seconds() > 0:
                summary[event['app_name']] += duration
        
        return {"usage": dict(summary)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn: conn.close()