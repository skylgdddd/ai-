import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from config import Config
from utils.logger import logger
import time
import shutil
import uuid

class MemoryManager:
    def __init__(self):
        self.memory_db_path = Config.MEMORY_DB_PATH
        self.model_path = Config.MEMORY_EMBEDDING_MODEL
        
        # 检查模型路径是本地路径还是Hugging Face模型ID
        if os.path.isdir(self.model_path):
            logger.info(f"使用本地嵌入模型: {self.model_path}")
            self.embedding_model = SentenceTransformer(
                self.model_path,
                cache_folder=os.path.dirname(Config.MEMORY_DB_PATH))
        else:
            logger.info(f"加载Hugging Face模型: {self.model_path}")
            self.embedding_model = SentenceTransformer(
                self.model_path,
                cache_folder=os.path.dirname(Config.MEMORY_DB_PATH))
        
        self.index = None
        self.memories = []  # 存储所有记忆
        self.new_memories = []  # 存储待索引的新记忆
        
        # 确保目录存在
        memory_dir = os.path.dirname(Config.MEMORY_DB_PATH)
        os.makedirs(memory_dir, exist_ok=True)

        # 使用完整路径
        self.memory_db_path = os.path.abspath(Config.MEMORY_DB_PATH)
        
        # 加载现有记忆
        self.load_memory()
        logger.info(f"记忆管理器初始化完成，当前记忆数量: {len(self.memories)}")

    def add_memory(self, memory_text: str, timestamp: float = None):
        """添加新记忆"""
        if not memory_text.strip():
            return
            
        timestamp = timestamp or time.time()
        
        # 创建记忆对象，添加唯一ID和重要性评分
        memory = {
            "id": str(uuid.uuid4()),  # 唯一标识符
            "text": memory_text,
            "timestamp": timestamp,
            "embedding": None,
            "importance": 1.0  # 默认重要性（可根据内容调整）
        }
        
        # 添加到内存列表和待索引列表
        self.memories.append(memory)
        self.new_memories.append(memory)
        
        # 增量更新索引
        self.update_index_incremental()
        
        # 增量保存新记忆
        self.save_new_memory(memory)
        
        logger.info(f"添加新记忆: {memory_text[:50]}...")
        return memory["id"]

    def retrieve_related_memories(self, query: str, top_k: int = None, threshold: float = 0.5) -> list:
        """检索相关记忆，添加相似度阈值"""
        if not self.memories or not query.strip():
            return []
        
        top_k = top_k or Config.MEMORY_RETRIEVAL_TOP_K
        top_k = min(top_k, len(self.memories))
    
        # 确保索引是最新的
        if self.new_memories:
            self.update_index_incremental()
    
        # 生成查询嵌入
        query_embedding = self.embedding_model.encode([query])[0]
        query_embedding = np.array([query_embedding]).astype('float32')
    
        # 在FAISS索引中搜索
        distances, indices = self.index.search(query_embedding, top_k)
    
        # 获取相关记忆
        related_memories = []
        for i, idx in enumerate(indices[0]):
            # 检查索引是否有效
            if idx < 0 or idx >= len(self.memories):
                logger.warning(f"FAISS返回无效索引: {idx} (位置 {i}), 当前记忆数量: {len(self.memories)}")
                continue
            
            # 计算相似度分数 (1 - 标准化距离)
            distance = distances[0][i]
            similarity = 1.0 - (distance / (1.0 + distance))  # 将距离转换为0-1的相似度
            
            # 应用阈值过滤
            if similarity < threshold:
                continue
                
            memory = self.memories[idx]
            related_memories.append({
                "id": memory["id"],
                "text": memory["text"],
                "timestamp": memory["timestamp"],
                "similarity": similarity,
                "importance": memory["importance"]
            })
    
        # 按相似度排序
        related_memories.sort(key=lambda x: x["similarity"], reverse=True)
        
        logger.info(f"检索到 {len(related_memories)} 条相关记忆 (阈值={threshold})")
        return related_memories

    def update_index_incremental(self):
        """增量更新FAISS索引，只处理新记忆"""
        if not self.new_memories:
            return
            
        logger.info(f"增量更新索引，新增 {len(self.new_memories)} 条记忆")
        
        # 获取新记忆的文本
        texts = [memory["text"] for memory in self.new_memories]
        
        # 批量生成嵌入向量
        embeddings = self.embedding_model.encode(texts)
    
        # 更新新记忆中的嵌入向量
        for i, memory in enumerate(self.new_memories):
            memory["embedding"] = embeddings[i]
    
        # 转换为numpy数组
        new_embeddings = np.array(embeddings).astype('float32')
        
        # 如果索引不存在，创建新索引
        if self.index is None:
            dimension = new_embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            logger.info(f"创建新FAISS索引，维度: {dimension}")
        
        # 添加新嵌入到索引
        self.index.add(new_embeddings)
        
        # 清空待处理记忆列表
        self.new_memories = []
    
        logger.info(f"索引更新完成，总向量数量: {self.index.ntotal}")

    def save_new_memory(self, memory: dict):
        """增量保存新记忆到文件"""
        try:
            save_path = f"{self.memory_db_path}.json"
            memory_data = {"text": memory["text"], "timestamp": memory["timestamp"], "id": memory["id"], "importance": memory["importance"]}
            
            # 追加模式写入新记忆
            with open(save_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(memory_data, ensure_ascii=False) + "\n")
                
            logger.debug(f"新记忆保存成功: {memory['text'][:30]}...")
        except Exception as e:
            logger.error(f"保存新记忆失败: {str(e)}")

    def load_memory(self):
        """从文件加载记忆，支持增量格式"""
        save_path = f"{self.memory_db_path}.json"
        if os.path.exists(save_path):
            try:
                self.memories = []
                with open(save_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            memory_data = json.loads(line.strip())
                            # 兼容旧格式
                            memory = {
                                "id": memory_data.get("id", str(uuid.uuid4())),
                                "text": memory_data["text"],
                                "timestamp": memory_data["timestamp"],
                                "embedding": None,
                                "importance": memory_data.get("importance", 1.0)
                            }
                            self.memories.append(memory)
                        except json.JSONDecodeError:
                            logger.warning("解析记忆行失败，跳过")
                
                logger.info(f"从文件加载 {len(self.memories)} 条记忆")
                
                # 将所有记忆标记为需要索引
                self.new_memories = self.memories.copy()
                
                # 更新索引
                self.update_index_incremental()
            except Exception as e:
                logger.error(f"加载记忆失败: {str(e)}")
                self.memories = []
                self.new_memories = []
        else:
            logger.info("未找到记忆文件，将创建新记忆库")

    def delete_memory(self, memory_id: str):
        """删除指定ID的记忆"""
        original_count = len(self.memories)
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        
        if len(self.memories) < original_count:
            # 重建索引（FAISS不支持删除单个向量）
            self.new_memories = self.memories.copy()
            self.index = None
            self.update_index_incremental()
            
            # 重新保存整个记忆库
            self.save_full_memory()
            logger.info(f"已删除记忆: {memory_id}")
            return True
        return False

    def save_full_memory(self):
        """保存完整记忆库（用于删除操作后）"""
        try:
            save_path = f"{self.memory_db_path}.json"
            # 临时文件路径
            temp_path = f"{save_path}.tmp"
            
            # 写入临时文件
            with open(temp_path, "w", encoding="utf-8") as f:
                for memory in self.memories:
                    memory_data = {
                        "id": memory["id"],
                        "text": memory["text"],
                        "timestamp": memory["timestamp"],
                        "importance": memory["importance"]
                    }
                    f.write(json.dumps(memory_data, ensure_ascii=False) + "\n")
            
            # 替换原文件
            shutil.move(temp_path, save_path)
            logger.info(f"完整记忆库保存到: {save_path}")
        except Exception as e:
            logger.error(f"保存完整记忆库失败: {str(e)}")

    def get_memory(self, memory_id: str):
        """获取指定ID的记忆"""
        for memory in self.memories:
            if memory["id"] == memory_id:
                return memory
        return None

    def list_memories(self, limit: int = 10, offset: int = 0):
        """分页列出记忆"""
        end_index = offset + limit
        return self.memories[offset:end_index]