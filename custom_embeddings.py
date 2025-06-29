#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义嵌入模块 - 避免LangChain版本冲突
直接使用SentenceTransformer和ChromaDB
"""

import logging
import os
from typing import List, Dict, Any
import numpy as np
import time

# 全局变量
embeddings_model = None
chroma_client = None
collection = None

def init_embeddings():
    """初始化嵌入模型和ChromaDB"""
    global embeddings_model, chroma_client, collection
    
    try:
        # 1. 初始化SentenceTransformer
        from sentence_transformers import SentenceTransformer
        logging.info("正在加载阿里巴巴嵌入模型...")
        embeddings_model = SentenceTransformer(
            'Alibaba-NLP/gte-multilingual-base', 
            trust_remote_code=True
        )
        logging.info("✅ 嵌入模型加载成功")
        
        # 2. 初始化ChromaDB
        import chromadb
        from chromadb.config import Settings
        
        # 使用持久化存储
        # 从配置文件读取数据库路径
        try:
            from gui_config import gui_config
            CHROMA_DB_PATH = gui_config.get('paths.database_directory', 'chroma_db_activity')
        except ImportError:
            CHROMA_DB_PATH = "chroma_db_activity"

        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        # 创建或获取集合
        collection = chroma_client.get_or_create_collection(
            name="screen_activity",
            metadata={"description": "Screen activity embeddings"}
        )
        logging.info("✅ ChromaDB初始化成功")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ 嵌入模型或ChromaDB初始化失败: {e}")
        embeddings_model = None
        chroma_client = None
        collection = None
        return False

def encode_text(text: str) -> List[float]:
    """编码单个文本"""
    if embeddings_model is None:
        raise RuntimeError("嵌入模型未初始化")
    
    embedding = embeddings_model.encode(text, normalize_embeddings=True)
    return embedding.tolist()

def encode_texts(texts: List[str]) -> List[List[float]]:
    """编码多个文本"""
    if embeddings_model is None:
        raise RuntimeError("嵌入模型未初始化")
    
    embeddings = embeddings_model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

def add_documents(documents: List[str], metadatas: List[Dict], ids: List[str]):
    """添加文档到向量数据库（分批处理）"""
    if collection is None:
        raise RuntimeError("ChromaDB集合未初始化")
    
    # 减小批次大小，提高稳定性
    batch_size = 10  # 每批处理10个文档（从50减少到10）
    total_docs = len(documents)
    
    logging.info(f"开始分批处理 {total_docs} 个文档，每批 {batch_size} 个")
    
    success_count = 0
    
    for i in range(0, total_docs, batch_size):
        end_idx = min(i + batch_size, total_docs)
        batch_docs = documents[i:end_idx]
        batch_metas = metadatas[i:end_idx]
        batch_ids = ids[i:end_idx]
        
        batch_num = i//batch_size + 1
        total_batches = (total_docs-1)//batch_size + 1
        
        try:
            # 生成当前批次的嵌入
            logging.info(f"🔄 正在处理第 {batch_num}/{total_batches} 批 ({len(batch_docs)} 个文档) - 进度: {i}/{total_docs}")
            
            # 逐个处理文档以避免内存问题
            batch_embeddings = []
            for j, doc in enumerate(batch_docs):
                try:
                    embedding = encode_text(doc)
                    batch_embeddings.append(embedding)
                    if j % 5 == 0:  # 每5个文档显示一次进度
                        logging.info(f"   - 已处理 {j+1}/{len(batch_docs)} 个文档")
                except Exception as e:
                    logging.error(f"❌ 处理文档 {j+1} 失败: {e}")
                    raise
            
            # 添加到集合
            logging.info(f"📊 正在将第 {batch_num} 批数据添加到数据库...")
            collection.add(
                documents=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids,
                embeddings=batch_embeddings
            )
            
            success_count += len(batch_docs)
            logging.info(f"✅ 第 {batch_num}/{total_batches} 批处理完成 (累计: {success_count}/{total_docs})")
            
            # 添加短暂延迟，避免资源竞争
            time.sleep(0.1)
            
        except Exception as e:
            logging.error(f"❌ 第 {batch_num} 批处理失败: {e}")
            logging.info(f"🔄 尝试重新处理第 {batch_num} 批...")
            
            # 尝试重新处理一次
            try:
                batch_embeddings = []
                for doc in batch_docs:
                    embedding = encode_text(doc)
                    batch_embeddings.append(embedding)
                
                collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids,
                    embeddings=batch_embeddings
                )
                
                success_count += len(batch_docs)
                logging.info(f"✅ 第 {batch_num} 批重试成功")
                
            except Exception as e2:
                logging.error(f"❌ 第 {batch_num} 批重试仍然失败: {e2}")
                # 继续处理下一批，不中断整个过程
                continue
    
    logging.info(f"🎉 批处理完成！成功处理 {success_count}/{total_docs} 个文档")

def search_similar(query: str, k: int = 25, where_filter: Dict = None) -> List[Dict]:
    """搜索相似文档"""
    if collection is None:
        raise RuntimeError("ChromaDB集合未初始化")
    
    # 编码查询
    query_embedding = encode_text(query)
    
    # 执行搜索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where_filter,
        include=['documents', 'metadatas', 'distances']
    )
    
    # 格式化结果
    formatted_results = []
    if results['documents'] and len(results['documents']) > 0:
        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        distances = results['distances'][0] if results['distances'] else []
        
        for i, doc in enumerate(documents):
            result = {
                'page_content': doc,
                'metadata': metadatas[i] if i < len(metadatas) else {},
                'distance': distances[i] if i < len(distances) else 0.0
            }
            formatted_results.append(result)
    
    return formatted_results

def clear_collection():
    """清空集合"""
    if collection is None:
        raise RuntimeError("ChromaDB集合未初始化")
    
    # 获取所有ID并删除
    existing_data = collection.get(include=[])
    if existing_data['ids']:
        collection.delete(ids=existing_data['ids'])
        logging.info(f"已清除 {len(existing_data['ids'])} 个文档")

def get_collection_count() -> int:
    """获取集合中的文档数量"""
    if collection is None:
        return 0
    
    try:
        result = collection.count()
        return result
    except:
        return 0

def get_all_documents() -> List[Dict]:
    """获取集合中的所有文档"""
    if collection is None:
        return []
    
    try:
        results = collection.get(include=['documents', 'metadatas'])
        documents = []
        
        if results['ids']:
            for i, doc_id in enumerate(results['ids']):
                doc = {
                    'id': doc_id,
                    'document': results['documents'][i] if i < len(results['documents']) else '',
                    'metadata': results['metadatas'][i] if i < len(results['metadatas']) else {}
                }
                documents.append(doc)
        
        return documents
    except Exception as e:
        logging.error(f"获取所有文档失败: {e}")
        return []

# 兼容性包装器，模拟LangChain的接口
class CustomEmbeddings:
    """自定义嵌入类，兼容原有接口"""
    
    def __init__(self):
        if not init_embeddings():
            raise RuntimeError("嵌入模型初始化失败")
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        return encode_text(text)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入多个文档"""
        return encode_texts(texts)

class CustomVectorStore:
    """自定义向量存储，兼容原有接口"""
    
    def __init__(self):
        if collection is None:
            raise RuntimeError("ChromaDB未初始化")
        self._collection = collection
    
    def similarity_search(self, query: str, k: int = 25, filter: Dict = None) -> List[Any]:
        """相似性搜索"""
        results = search_similar(query, k=k, where_filter=filter)
        
        # 转换为兼容格式
        docs = []
        for result in results:
            doc = type('Document', (), {
                'page_content': result['page_content'],
                'metadata': result['metadata']
            })()
            docs.append(doc)
        
        return docs

# 测试函数
def test_custom_embeddings():
    """测试自定义嵌入功能"""
    try:
        print("=== 测试自定义嵌入模块 ===")
        
        # 初始化
        success = init_embeddings()
        if not success:
            print("❌ 初始化失败")
            return False
        
        print("✅ 初始化成功")
        
        # 测试编码
        text = "这是一个测试文本"
        embedding = encode_text(text)
        print(f"✅ 编码测试成功，维度: {len(embedding)}")
        
        # 测试ChromaDB
        count = get_collection_count()
        print(f"✅ ChromaDB连接成功，当前文档数: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    test_custom_embeddings() 